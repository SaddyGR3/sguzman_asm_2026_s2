"""Guarda mediciones de la ESP32 y permite calibrar el servo con flechas.

Uso: python3 registrar_ensayo.py /dev/ttyUSB0
Cerrar cualquier otro monitor que tenga abierto el mismo puerto.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
from pathlib import Path
import select
import sys
import threading
import time



ENCABEZADO = ("tiempo_ms", "rpm", "servo_cmd_grados")
ENCABEZADO_DIAGNOSTICO_ANTERIOR = (
    "tiempo_ms", "rpm_cruda", "rpm_validada", "estado_medicion", "antiguedad_us",
    "periodo_us", "pulsos_aceptados", "pulsos_rechazados", "saltos_rechazados",
    "perdidos_cola", "ultimo_periodo_rechazado_us", "modo", "motor_encendido",
    "tiempo_ensayo_ms", "referencia_rpm", "error_rpm", "u_solicitada", "u_aplicada",
)

ENCABEZADO_DIAGNOSTICO = ENCABEZADO_DIAGNOSTICO_ANTERIOR + (
    "pid_u_limitada", "pid_p", "pid_i", "pid_d", "pid_estado", "pid_dt_us",
    "pid_omitidos", "pid_tiempo_calculo_us",
)


def siguiente_numero(carpeta: Path) -> int:
    """Asigna 1, 2, 3... sin sobrescribir ninguno de los dos CSV."""
    usados = set()
    for prefijo in ("datos_", "eventos_", "diagnostico_"):
        for ruta in carpeta.glob(f"{prefijo}*.csv"):
            identificador = ruta.stem[len(prefijo):]
            if identificador.isdecimal():
                usados.add(int(identificador))
    return max(usados, default=0) + 1


class Registro:
    def __init__(self, datos, eventos, diagnostico=None, silencioso=False):
        self.silencioso = silencioso
        self.diagnostico = diagnostico
        self.escritor_diagnostico = csv.writer(diagnostico) if diagnostico else None
        if self.escritor_diagnostico:
            self.escritor_diagnostico.writerow(ENCABEZADO_DIAGNOSTICO)
            diagnostico.flush()
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

    def imprimir(self, *args, **kwargs):
        if not self.silencioso:
            print(*args, **kwargs)

    def procesar(self, linea: str) -> None:
        linea = linea.strip()
        if not linea:
            return
        if linea == ",".join(ENCABEZADO):
            return
        if linea.startswith("#DIAG,"):
            self.procesar_diagnostico(linea)
            return
        if linea.startswith("#EVENT,"):
            partes = linea.split(",", 3)
            if len(partes) == 4:
                try:
                    tiempo = int(partes[1])
                    valor = int(partes[3])
                except ValueError:
                    self.imprimir(f"Evento ilegible: {linea}")
                    return
                if partes[2] == "REINICIO":
                    self.ultimo_tiempo = -1
                self.escritor_eventos.writerow((tiempo, partes[2], valor))
                self.eventos.flush()
                self.imprimir(f"\nEvento {partes[2]}: t={tiempo} ms, valor={valor}")
            return
        if linea.startswith("#"):
            self.imprimir(f"\n{linea}")
            return

        partes = next(csv.reader([linea]))
        if len(partes) != 3:
            self.imprimir(f"\nFila ignorada: {linea}")
            return
        try:
            tiempo = int(partes[0])
            rpm = float(partes[1])
            angulo = int(partes[2])
        except ValueError:
            self.imprimir(f"\nFila ignorada: {linea}")
            return
        if tiempo < self.ultimo_tiempo or tiempo < 0 or not math.isfinite(rpm) or rpm < 0 or not 0 <= angulo <= 90:
            self.imprimir(f"\nFila fuera de rango: {linea}")
            return

        self.escritor_datos.writerow((tiempo, partes[1], angulo))
        self.datos.flush()
        self.ultimo_tiempo = tiempo
        if time.monotonic() - self.ultima_impresion >= 0.25:
            self.imprimir(f"\rt={tiempo:>7} ms  RPM={rpm:>8.2f}  servo={angulo:>2}°", end="", flush=True)
            self.ultima_impresion = time.monotonic()

    def procesar_diagnostico(self, linea: str) -> None:
        if not self.escritor_diagnostico:
            return
        campos = next(csv.reader([linea]))[1:]
        try:
            if len(campos) == len(ENCABEZADO_DIAGNOSTICO_ANTERIOR):
                campos.extend(["nan", "nan", "nan", "nan", "NO_DISPONIBLE", "", "", ""])
            elif len(campos) != len(ENCABEZADO_DIAGNOSTICO):
                raise ValueError("cantidad de columnas")
            tiempo = int(campos[0])
            cruda, validada = float(campos[1]), float(campos[2])
            estado = campos[3]
            estados = {"SIN_PULSOS", "UNA_MARCA", "RECIENTE", "ANTIGUA",
                       "SIN_SENAL", "SOSPECHOSA", "DESBORDAMIENTO"}
            if tiempo < -1 or estado not in estados:
                raise ValueError("tiempo o estado")
            if not (math.isnan(cruda) or math.isfinite(cruda) and cruda >= 0):
                raise ValueError("RPM cruda")
            if estado == "RECIENTE":
                if not math.isfinite(validada) or validada <= 0:
                    raise ValueError("RPM validada")
            elif not math.isnan(validada):
                raise ValueError("una lectura invalida debe tener RPM validada NaN")
            if any(int(campos[i]) < 0 for i in range(4, 11)):
                raise ValueError("diagnostico negativo")
            if campos[11] not in {"REPOSO", "PREPARACION", "FIJO", "PID", "FINALIZADO", "CANCELADO", "FALLO"}:
                raise ValueError("modo desconocido")
            if int(campos[12]) not in (0, 1) or int(campos[13]) < 0:
                raise ValueError("motor o tiempo de ensayo")
            if any(not (math.isfinite(float(c)) or math.isnan(float(c))) for c in campos[14:22]):
                raise ValueError("campos de control")
            if campos[22] not in {
                "NO_DISPONIBLE", "INACTIVO", "SIN_CONFIGURAR", "GANANCIAS_CERO",
                "OBSERVACION", "CONTROLANDO", "MEDICION_INVALIDA", "ENTRADA_INVALIDA",
                "TIEMPO_EXCEDIDO", "ERROR_NUMERICO",
            }:
                raise ValueError("estado PID")
            if any(c != "" and int(c) < 0 for c in campos[23:]):
                raise ValueError("temporizacion PID")
            if not (math.isnan(float(campos[17])) or 0 <= float(campos[17]) <= 1):
                raise ValueError("accion aplicada")
            if not (math.isnan(float(campos[18])) or 0 <= float(campos[18]) <= 1):
                raise ValueError("accion limitada")
        except (ValueError, OverflowError):
            self.imprimir(f"\nDiagnostico ignorado por formato invalido: {linea}")
            return
        # NaN conserva que referencia y PID aun no estan calculados.
        self.escritor_diagnostico.writerow(campos)
        self.diagnostico.flush()


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
        print("Flechas derecha/arriba: +1°; izquierda/abajo: -1°. Los comandos se envian con Enter.")
        print("g75, p5, c/f/m/v, preparar, fijo47, cancelar, estado + Enter. q sale de la captura.")
        while not terminar.is_set():
            tecla = leer_tecla()
            if tecla is None:
                continue
            if tecla in ("+", "-") and not pendiente:
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
    import serial
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("puerto", help="Ejemplo: /dev/ttyUSB0 o COM3")
    parser.add_argument("--salida", type=Path, default=Path(__file__).resolve().parents[1] / "capturas")
    args = parser.parse_args()

    args.salida.mkdir(parents=True, exist_ok=True)
    numero = siguiente_numero(args.salida)
    ruta_datos = args.salida / f"datos_{numero}.csv"
    ruta_eventos = args.salida / f"eventos_{numero}.csv"
    ruta_diagnostico = args.salida / f"diagnostico_{numero}.csv"

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
    with puerto, ruta_datos.open("x", newline="", encoding="utf-8") as datos, ruta_eventos.open(
        "x", newline="", encoding="utf-8"
    ) as eventos, ruta_diagnostico.open("x", newline="", encoding="utf-8") as diagnostico:
        registro = Registro(datos, eventos, diagnostico)

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
        print(f"Ensayo {numero} (ID {numero})\nDatos: {ruta_datos}\nEventos: {ruta_eventos}\nDiagnostico: {ruta_diagnostico}")
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
