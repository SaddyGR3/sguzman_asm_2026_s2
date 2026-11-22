"""Guarda mediciones de la ESP32 y permite calibrar el servo con flechas.

Uso: python3 registrar_ensayo.py /dev/ttyUSB0
Cerrar cualquier otro monitor que tenga abierto el mismo puerto.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import math
import os
from pathlib import Path
import select
import sys
import threading
import time

import serial


ENCABEZADO = ("tiempo_ms", "rpm", "servo_cmd_grados")


class Registro:
    def __init__(self, datos, eventos):
        self.datos = datos
        self.eventos = eventos
        self.escritor_datos = csv.writer(datos)
        self.escritor_eventos = csv.writer(eventos)
        self.escritor_datos.writerow(ENCABEZADO)
        self.escritor_eventos.writerow(("tiempo_ms", "tipo", "valor"))
        self.datos.flush()
        self.eventos.flush()
        self.ultimo_tiempo = -1
        self.ultima_impresion = 0.0

    def procesar(self, linea: str) -> None:
        linea = linea.strip()
        if not linea:
            return
        if linea == ",".join(ENCABEZADO):
            return
        if linea.startswith("#EVENT,"):
            partes = linea.split(",", 3)
            if len(partes) == 4:
                try:
                    tiempo = int(partes[1])
                    valor = int(partes[3])
                except ValueError:
                    print(f"Evento ilegible: {linea}")
                    return
                self.escritor_eventos.writerow((tiempo, partes[2], valor))
                self.eventos.flush()
                print(f"\nEvento {partes[2]}: t={tiempo} ms, valor={valor}")
            return
        if linea.startswith("#"):
            print(f"\n{linea}")
            return

        partes = next(csv.reader([linea]))
        if len(partes) != 3:
            print(f"\nFila ignorada: {linea}")
            return
        try:
            tiempo = int(partes[0])
            rpm = float(partes[1])
            angulo = int(partes[2])
        except ValueError:
            print(f"\nFila ignorada: {linea}")
            return
        if tiempo < self.ultimo_tiempo or tiempo < 0 or not math.isfinite(rpm) or rpm < 0 or not 0 <= angulo <= 90:
            print(f"\nFila fuera de rango: {linea}")
            return

        self.escritor_datos.writerow((tiempo, partes[1], angulo))
        self.datos.flush()
        self.ultimo_tiempo = tiempo
        if time.monotonic() - self.ultima_impresion >= 0.25:
            print(f"\rt={tiempo:>7} ms  RPM={rpm:>8.2f}  servo={angulo:>2}°", end="", flush=True)
            self.ultima_impresion = time.monotonic()


def leer_tecla_posix() -> str | None:
    if not select.select([sys.stdin], [], [], 0.1)[0]:
        return None
    caracter = os.read(sys.stdin.fileno(), 1).decode("ascii", errors="ignore")
    if caracter != "\x1b":
        return caracter
    if not select.select([sys.stdin], [], [], 0.05)[0]:
        return None
    segundo = os.read(sys.stdin.fileno(), 1)
    if segundo != b"[" or not select.select([sys.stdin], [], [], 0.05)[0]:
        return None
    tercero = os.read(sys.stdin.fileno(), 1)
    return {b"A": "+", b"C": "+", b"B": "-", b"D": "-"}.get(tercero)


def leer_tecla_windows() -> str | None:
    import msvcrt

    if not msvcrt.kbhit():
        time.sleep(0.05)
        return None
    caracter = msvcrt.getwch()
    if caracter in ("\x00", "\xe0"):
        return {"H": "+", "M": "+", "P": "-", "K": "-"}.get(msvcrt.getwch())
    return caracter


def enviar(puerto: serial.Serial, comando: str) -> None:
    puerto.write((comando + "\n").encode("ascii"))
    puerto.flush()


def teclado_interactivo(puerto: serial.Serial, terminar: threading.Event) -> None:
    if os.name == "nt":
        leer_tecla = leer_tecla_windows
        restaurar = None
    else:
        if not sys.stdin.isatty():
            raise RuntimeError("Las flechas requieren una terminal interactiva")
        import termios
        import tty

        descriptor = sys.stdin.fileno()
        anterior = termios.tcgetattr(descriptor)
        tty.setcbreak(descriptor)
        restaurar = lambda: termios.tcsetattr(descriptor, termios.TCSADRAIN, anterior)
        leer_tecla = leer_tecla_posix

    pendiente = ""
    try:
        print("Flechas derecha/arriba: +1°; izquierda/abajo: -1°; c/f: marcar contacto; m: fuente apagada; v: pulsos")
        print("Escriba g75 + Enter para ir a 75°, p5 + Enter para paso de 5°, q para salir")
        while not terminar.is_set():
            tecla = leer_tecla()
            if tecla is None:
                continue
            if tecla in ("+", "-") and not pendiente:
                enviar(puerto, tecla)
            elif tecla in ("c", "f", "m", "v") and not pendiente:
                enviar(puerto, tecla)
            elif tecla == "q" and not pendiente:
                break
            elif tecla in ("\r", "\n"):
                if pendiente:
                    enviar(puerto, pendiente)
                    print(f"\nComando enviado: {pendiente}")
                    pendiente = ""
            elif tecla in ("\x7f", "\b"):
                pendiente = pendiente[:-1]
                print(f"\rComando: {pendiente:<23}", end="", flush=True)
            elif tecla.isprintable() and len(pendiente) < 23:
                pendiente += tecla
                print(f"\rComando: {pendiente:<23}", end="", flush=True)
    finally:
        if restaurar is not None:
            restaurar()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("puerto", help="Ejemplo: /dev/ttyUSB0 o COM3")
    parser.add_argument("--salida", type=Path, default=Path(__file__).resolve().parents[1] / "capturas")
    args = parser.parse_args()

    args.salida.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    ruta_datos = args.salida / f"datos_{marca}.csv"
    ruta_eventos = args.salida / f"eventos_{marca}.csv"

    try:
        puerto = serial.Serial(args.puerto, 115200, timeout=0.2)
    except serial.SerialException as error:
        print(f"No se pudo abrir {args.puerto}: {error}", file=sys.stderr)
        return 1

    # Muchas placas ESP32 se reinician al abrir el puerto. Esperar el arranque y
    # enviar r garantiza un origen nuevo aunque esa placa no se reinicie.
    print("Esperando a la ESP32 y reiniciando el reloj de esta captura...")
    time.sleep(2)
    puerto.reset_input_buffer()
    enviar(puerto, "r")

    terminar = threading.Event()
    with puerto, ruta_datos.open("w", newline="", encoding="utf-8") as datos, ruta_eventos.open(
        "w", newline="", encoding="utf-8"
    ) as eventos:
        registro = Registro(datos, eventos)

        def recibir() -> None:
            while not terminar.is_set():
                try:
                    linea = puerto.readline().decode("utf-8", errors="replace")
                except serial.SerialException as error:
                    print(f"\nError del puerto: {error}", file=sys.stderr)
                    terminar.set()
                    break
                if linea:
                    registro.procesar(linea)

        lector = threading.Thread(target=recibir, daemon=True)
        lector.start()
        print(f"Datos: {ruta_datos}\nEventos: {ruta_eventos}")
        try:
            teclado_interactivo(puerto, terminar)
        except (KeyboardInterrupt, RuntimeError) as error:
            if isinstance(error, RuntimeError):
                print(error, file=sys.stderr)
        finally:
            terminar.set()
            lector.join(timeout=1)
            print("\nCaptura terminada; archivos guardados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
