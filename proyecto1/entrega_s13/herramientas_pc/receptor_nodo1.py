"""Receptor del nodo 1 en la PC (herramienta de la PC, no es firmware).

Recibe y valida los paquetes que envía el emisor (nodo 1) por un adaptador USB-serie, o
desde una captura cruda guardada antes. Revisa decodificación, cabecera, secuencia, orden,
DIAG y, sobre el tramo continuo más largo, el espectro de x (y la SNR en el enlace N3).

Uso, un enlace a la vez:
    python receptor_nodo1.py --puerto /dev/ttyUSB1 --enlace n3 --segundos 60 --guardar cap.bin
    python receptor_nodo1.py --archivo cap.bin --enlace n3

Termina con código 0 si el resultado es OK y con 1 si es FALLA.
"""
import argparse
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True  # no crear __pycache__ en proyecto1/simulacion/ (carpeta de otro equipo)
RAIZ_SIM = Path(__file__).resolve().parents[1] / "simulacion"
sys.path.insert(0, str(RAIZ_SIM))
from sim import protocolo  # noqa: E402

FS = 8000.0
HOP = protocolo.MUESTRAS_POR_PAQUETE        # 512 muestras por bloque
MAX_CABLE = protocolo.MAX_BYTES_CABLE       # 4150 B, incluido el 0x00
TROZO = 4096                                # bytes por lectura

# Por enlace: destino, tipo de los datos y canales que debe traer.
ENLACES = {
    "n2": {"dst": 2, "tipo_datos": protocolo.TIPO_INPUT, "canales": 1},
    "n3": {"dst": 3, "tipo_datos": protocolo.TIPO_INPUT_REF, "canales": 2},
}
NOMBRE_TIPO = {protocolo.TIPO_INPUT: "INPUT", protocolo.TIPO_INPUT_REF: "INPUT_REF",
               protocolo.TIPO_DIAG: "DIAG"}

# Causas de decodificación: pueden ser errores de transición de sesión (reinicio del emisor).
CAUSAS_TRANSICION = ("tamano", "cobs", "corto", "crc", "trama")

# Contadores que cuentan para el veredicto.
ERRORES = (
    "err_tamano", "err_cobs", "err_corto", "err_crc", "err_trama",
    "err_magic", "err_version", "err_tipo", "err_longitud", "err_formato",
    "err_no_finito", "err_destino", "err_src", "err_tipo_paridad", "err_cable",
    "err_banderas", "err_secuencia_retroceso", "err_primer_bloque", "err_first_sample",
    "err_diag", "err_diag_first_sample", "err_energia",
    "paquetes_perdidos", "inicio_sesion_perdido",
)

# Valores fijos del DIAG que envía este emisor.
DIAG_ESPERADO = {
    "fs": 8000, "N": 1024, "H": 512, "metodo": 0, "calentamiento": 0, "tipo_ruido": 0,
    "filtro_n2": 0, "pico_Hz": -1.0, "banda_lo": -1.0, "banda_hi": -1.0,
    "piso_resumen": -1.0, "DC": 0.0, "overruns": 0, "perdidas": 0, "saturaciones": 0,
    "config_id": 0,
}
TOL_ENERGIA = 1e-4

# Picos de x esperados: (frecuencia en Hz, nivel en dB relativo al pico de 2150 Hz).
PICOS_ESPERADOS = ((300.0, -1.44), (700.0, -6.63), (1100.0, -11.90), (2150.0, 0.0))
TOL_FREC_HZ = 1.0
TOL_NIVEL_DB = 0.5
SEPARACION_PICOS_HZ = 20.0
TOL_SNR_DB = 0.2


class Sesion:
    """Estado de una sesión del emisor (un session_id)."""

    def __init__(self, session_id, desde_inicio):
        self.id = session_id
        self.desde_inicio = desde_inicio    # su primer paquete visto tiene sequence = 0
        self.primera_seq = None
        self.ultima_seq = None
        self.por_tipo = Counter()
        self.perdidos = 0
        self.fallas_bandera = 0
        self.datos_prev = None              # último paquete de datos: seq, first, energía
        self.tramo_x = []                   # bloques del tramo continuo en curso
        self.tramo_s = []


class Troceador:
    """Corta el flujo de bytes en tramas, separadas por 0x00."""

    def __init__(self):
        self.buf = bytearray()
        self.inicio_pendiente = True    # lo anterior al primer 0x00 es un inicio parcial
        self.descartando = False        # tras un búfer desbordado, se tira hasta el siguiente 0x00
        self.fragmento_inicial = 0

    def alimentar(self, datos):
        """Agrega bytes y devuelve las tramas completas (str 'trama' si el búfer se desbordó)."""
        self.buf += datos
        salida = []
        while True:
            i = self.buf.find(0)
            if i < 0:
                break
            trama = bytes(self.buf[:i])
            del self.buf[:i + 1]
            if self.inicio_pendiente:
                self.inicio_pendiente = False
                self.fragmento_inicial = len(trama)
            elif self.descartando:
                self.descartando = False
            else:
                salida.append(trama)
        if self.descartando:
            self.buf.clear()
        elif len(self.buf) > MAX_CABLE:
            salida.append("trama")      # error de trama: demasiado largo sin 0x00
            self.buf.clear()
            self.descartando = True
        return salida


class Receptor:
    """Valida los paquetes de un enlace y acumula contadores, sesiones y muestras."""

    def __init__(self, enlace):
        self.cfg = ENLACES[enlace]
        self.enlace = enlace
        self.troceador = Troceador()
        self.err = Counter()
        self.info = Counter()
        self.detalles = []
        self.pendientes = Counter()     # errores de decodificación desde el último paquete válido
        self.sesion = None
        self.sesiones = []
        self.mejor = None               # (session_id, bloques x, bloques s) del tramo más largo
        self.mejor_n = 0
        self.tiempo_min = None
        self.tiempo_max = None
        self.paquetes = 0

    # --- entrada de bytes ---

    def alimentar(self, datos):
        """Recibe bytes del puerto o del archivo y procesa las tramas completas."""
        for trama in self.troceador.alimentar(datos):
            if trama == "trama":
                self._error_trama("trama")
            else:
                self._procesar_trama(trama)

    def _procesar_trama(self, trama):
        """Descarta tramas vacías, decodifica y valida el paquete."""
        if not trama:
            self.info["tramas_vacias"] += 1
            return
        try:
            cab, datos = protocolo.leer_paquete(trama, destino_esperado=self.cfg["dst"])
        except protocolo.ErrorPaquete as e:
            self._error_trama(e.causa, str(e))
            return
        self._registrar_paquete(cab, datos, len(trama) + 1)

    def _error(self, nombre, detalle):
        """Suma un error que cuenta para el veredicto y guarda su detalle."""
        self.err[nombre] += 1
        if len(self.detalles) < 20:
            self.detalles.append(f"{nombre}: {detalle}")

    def _error_trama(self, causa, detalle=""):
        """Errores de decodificación quedan pendientes; los de cabecera cuentan ya."""
        if causa in CAUSAS_TRANSICION:
            self.pendientes[causa] += 1
        else:
            self._error("err_" + causa, detalle)

    def _resolver_pendientes(self, session_id):
        """Al llegar un paquete válido: los pendientes son de transición si cambió la sesión."""
        if not self.pendientes:
            return
        transicion = self.sesion is not None and session_id != self.sesion.id
        for causa, n in self.pendientes.items():
            if transicion:
                self.info["errores_transicion_sesion"] += n
            else:
                self.err["err_" + causa] += n
        self.pendientes.clear()

    # --- sesión y secuencia ---

    def _nueva_sesion(self, cab):
        """Cierra la sesión anterior (si hay) y abre la del paquete."""
        seq = cab["sequence"]
        anterior = self.sesion is not None
        if anterior:
            self._cerrar_tramo(self.sesion)
            self.info["reinicios_sesion"] += 1
        self.sesion = Sesion(cab["session_id"], desde_inicio=(seq == 0))
        self.sesiones.append(self.sesion)
        if anterior and seq != 0:
            # Toda sesión nueva debe empezar en sequence 0: lo anterior se perdió.
            self.err["inicio_sesion_perdido"] += 1
            self.err["paquetes_perdidos"] += seq
            self.sesion.perdidos += seq
            self._detalle(f"sesión {cab['session_id']:#010x} empieza en sequence {seq}")

    def _detalle(self, texto):
        if len(self.detalles) < 20:
            self.detalles.append(texto)

    def _revisar_secuencia(self, s, seq):
        """sequence = anterior + 1; un salto suma las pérdidas y corta el tramo."""
        if s.ultima_seq is not None:
            esperado = (s.ultima_seq + 1) & 0xFFFFFFFF
            if seq != esperado:
                salto = (seq - esperado) & 0xFFFFFFFF
                if salto > 0x7FFFFFFF:
                    self._error("err_secuencia_retroceso", f"{s.ultima_seq} -> {seq}")
                else:
                    self.err["paquetes_perdidos"] += salto
                    s.perdidos += salto
                self._cerrar_tramo(s)
        s.ultima_seq = seq

    def _revisar_banderas(self, s, cab):
        """0x0001 siempre en INPUT_REF; 0x0004 solo en sequence 0 de una sesión vista desde su inicio."""
        esperado = protocolo.FLAG_REFERENCIA if cab["type"] == protocolo.TIPO_INPUT_REF else 0
        if s.desde_inicio and cab["sequence"] == 0:
            esperado |= protocolo.FLAG_REINICIO
        if cab["flags"] != esperado:
            s.fallas_bandera += 1
            self._error("err_banderas", f"sequence {cab['sequence']}: flags {cab['flags']:#06x}, "
                                        f"esperado {esperado:#06x}")

    # --- paquetes ---

    def _registrar_paquete(self, cab, datos, largo_cable):
        """Validaciones de un paquete válido: sesión, secuencia, banderas, paridad y contenido."""
        self._resolver_pendientes(cab["session_id"])
        if self.sesion is None or cab["session_id"] != self.sesion.id:
            self._nueva_sesion(cab)
        s = self.sesion
        seq = cab["sequence"]
        tipo = cab["type"]
        self.paquetes += 1
        s.por_tipo[NOMBRE_TIPO.get(tipo, str(tipo))] += 1
        if s.primera_seq is None:
            s.primera_seq = seq

        self._revisar_secuencia(s, seq)
        self._revisar_banderas(s, cab)
        if cab["src"] != 1:
            self._error("err_src", f"sequence {seq}: src {cab['src']}")
        if largo_cable > protocolo.max_wire(cab["payload_bytes"]):
            self._error("err_cable", f"sequence {seq}: {largo_cable} B en el cable")

        # Orden por paridad: datos con sequence par, DIAG con sequence impar.
        esperado = self.cfg["tipo_datos"] if seq % 2 == 0 else protocolo.TIPO_DIAG
        if tipo != esperado:
            self._error("err_tipo_paridad", f"sequence {seq}: tipo {tipo}, esperado {esperado}")
            return
        if tipo == protocolo.TIPO_DIAG:
            self._revisar_diag(s, cab, datos)
        else:
            self._revisar_datos(s, cab, datos)

    def _revisar_datos(self, s, cab, datos):
        """Avance de 512 en first_sample, primer bloque en 0 y tramo continuo de muestras."""
        seq, first = cab["sequence"], cab["first_sample"]
        muestras = protocolo.bytes_a_muestras(datos, cab["channels"])
        if cab["channels"] == 2:
            x, sref = np.array(muestras[:, 0]), np.array(muestras[:, 1])
        else:
            x, sref = np.array(muestras), None

        if s.desde_inicio and seq == 0 and first != 0:
            self._error("err_primer_bloque", f"first_sample {first} en sequence 0")
        prev = s.datos_prev
        consecutivo = prev is not None and seq == prev["seq"] + 2
        if not (consecutivo and first == prev["first"] + HOP):
            if consecutivo:
                self._error("err_first_sample", f"sequence {seq}: first_sample {first}, "
                                                f"esperado {prev['first'] + HOP}")
            self._cerrar_tramo(s)
        s.tramo_x.append(x)
        if sref is not None:
            s.tramo_s.append(sref)
        energia = float(np.sum(np.square(x), dtype=np.float32))     # Σx² en float32
        s.datos_prev = {"seq": seq, "first": first, "energia": energia}

    def _revisar_diag(self, s, cab, datos):
        """Valores fijos del DIAG y comparación con los datos del mismo bloque."""
        d = protocolo.desempaquetar_diag(datos)
        fallas = [k for k, v in DIAG_ESPERADO.items() if d[k] != v]
        if d["inicio_ventana"] != cab["first_sample"]:
            fallas.append("inicio_ventana")
        if d["tiempo_us"] <= 0:
            fallas.append("tiempo_us")
        if fallas:
            self._error("err_diag", f"sequence {cab['sequence']}: {', '.join(fallas)}")
        self.tiempo_min = d["tiempo_us"] if self.tiempo_min is None else min(self.tiempo_min, d["tiempo_us"])
        self.tiempo_max = d["tiempo_us"] if self.tiempo_max is None else max(self.tiempo_max, d["tiempo_us"])

        prev = s.datos_prev
        if prev is None or prev["seq"] != cab["sequence"] - 1:
            self.info["diag_sin_datos"] += 1        # informativo: la pérdida ya se contó
            return
        if cab["first_sample"] != prev["first"]:
            self._error("err_diag_first_sample", f"sequence {cab['sequence']}")
        referencia = prev["energia"]
        if abs(d["energia"] - referencia) > TOL_ENERGIA * max(abs(referencia), 1e-30):
            self._error("err_energia", f"sequence {cab['sequence']}: DIAG {d['energia']:.6g}, "
                                       f"datos {referencia:.6g}")

    # --- tramo continuo ---

    def _cerrar_tramo(self, s):
        """Si el tramo en curso es el más largo hasta ahora, lo guarda; luego lo vacía."""
        n = len(s.tramo_x) * HOP
        if n > self.mejor_n:
            self.mejor_n = n
            self.mejor = (s.id, s.tramo_x, s.tramo_s)
        s.tramo_x, s.tramo_s = [], []

    # --- fin de la captura ---

    def terminar(self):
        """Pendientes a errores normales, cierra el tramo, analiza e imprime. Devuelve el código."""
        for causa, n in self.pendientes.items():
            self.err["err_" + causa] += n
        self.pendientes.clear()
        if self.sesion is not None:
            self._cerrar_tramo(self.sesion)

        fallas = [f"{k} = {n}" for k, n in self.err.items() if n]
        self._imprimir_sesiones()
        self._imprimir_contadores()
        lineas, fallas_analisis = analizar_tramo(self.mejor, self.mejor_n, self.enlace)
        print("\nANÁLISIS")
        for linea in lineas:
            print("  " + linea)
        fallas += fallas_analisis
        if self.paquetes == 0:
            fallas.append("no se recibió ningún paquete válido")

        if fallas:
            print("\nRESULTADO: FALLA")
            for f in fallas:
                print("  - " + f)
            for det in self.detalles[:10]:
                print("    detalle: " + det)
            return 1
        print("\nRESULTADO: OK")
        return 0

    def _imprimir_sesiones(self):
        print("\nSESIONES")
        if not self.sesiones:
            print("  (ninguna)")
        for i, s in enumerate(self.sesiones, 1):
            origen = "desde su inicio" if s.desde_inicio else "a medias"
            tipos = ", ".join(f"{k} {v}" for k, v in sorted(s.por_tipo.items()))
            reinicio = "FALLA" if s.fallas_bandera else "OK"
            print(f"  sesión {i} ({s.id:#010x}, observada {origen}): {tipos}; "
                  f"sequence {s.primera_seq}..{s.ultima_seq}; perdidos {s.perdidos}; "
                  f"banderas/0x0004 {reinicio}")

    def _imprimir_contadores(self):
        print("\nCONTADORES (cuentan para el veredicto)")
        for k in ERRORES:
            print(f"  {k:26s} {self.err[k]}")
        for k in self.err:
            if k not in ERRORES:
                print(f"  {k:26s} {self.err[k]}")
        print("\nINFORMATIVOS (no cuentan para el veredicto)")
        print(f"  {'fragmento_inicial (B)':26s} {self.troceador.fragmento_inicial}")
        for k in ("tramas_vacias", "errores_transicion_sesion", "reinicios_sesion", "diag_sin_datos"):
            print(f"  {k:26s} {self.info[k]}")
        if self.tiempo_min is not None:
            print(f"  {'tiempo_us (min, max)':26s} {self.tiempo_min}, {self.tiempo_max}")
        print(f"  {'paquetes válidos':26s} {self.paquetes}")

    def resumen_progreso(self, t):
        """Una línea de avance para la captura en vivo."""
        return (f"[{t:5.1f} s] paquetes {self.paquetes} | errores {sum(self.err.values())} | "
                f"transición {self.info['errores_transicion_sesion']} | sesiones {len(self.sesiones)}")


# --- análisis de datos ---

def hann_periodica(n):
    """Ventana de Hann periódica de longitud L = n: w[k] = 0.5 - 0.5·cos(2πk/L)."""
    k = np.arange(n)
    return 0.5 - 0.5 * np.cos(2.0 * np.pi * k / n)


def buscar_picos(mag_db, df, cantidad=4, separacion_hz=SEPARACION_PICOS_HZ):
    """Los `cantidad` máximos locales más altos, separados al menos `separacion_hz`."""
    centro = mag_db[1:-1]
    locales = np.nonzero((centro >= mag_db[:-2]) & (centro > mag_db[2:]))[0] + 1
    locales = locales[np.argsort(mag_db[locales])[::-1]]
    elegidos = []
    for k in locales:
        if all(abs(int(k) - j) * df >= separacion_hz for j in elegidos):
            elegidos.append(int(k))
            if len(elegidos) == cantidad:
                break
    return elegidos


def analizar_tramo(mejor, mejor_n, enlace):
    """FFT de x (y SNR en N3) sobre el tramo más largo, recortado a segundos enteros."""
    n = int(mejor_n // FS) * int(FS)
    if mejor is None or n == 0:
        return [f"tramo continuo de {mejor_n} muestras: menos de {int(FS)}, no se analiza"], \
               ["sin análisis: el tramo continuo más largo tiene menos de 8000 muestras"]
    _, bloques_x, bloques_s = mejor
    x = np.concatenate(bloques_x)[:n].astype(np.float64)
    lineas = [f"tramo analizado: {n / FS:.0f} s ({n} muestras, de un tramo continuo de "
              f"{mejor_n / FS:.2f} s)"]
    fallas = []

    mag = 20.0 * np.log10(np.abs(np.fft.rfft(x * hann_periodica(n))) + 1e-30)
    df = FS / n
    picos = buscar_picos(mag, df)
    ref = next((p for p in picos if abs(p * df - 2150.0) <= TOL_FREC_HZ), None)
    for f_esp, nivel_esp in PICOS_ESPERADOS:
        p = next((q for q in picos if abs(q * df - f_esp) <= TOL_FREC_HZ), None)
        if p is None or ref is None:
            lineas.append(f"{f_esp:6.0f} Hz: pico no encontrado  FAIL")
            fallas.append(f"pico de {f_esp:.0f} Hz no encontrado")
            continue
        rel = float(mag[p] - mag[ref])
        ok = abs(rel - nivel_esp) <= TOL_NIVEL_DB
        lineas.append(f"{f_esp:6.0f} Hz: pico en {p * df:8.2f} Hz, nivel {rel:+6.2f} dB "
                      f"(esperado {nivel_esp:+6.2f} ± {TOL_NIVEL_DB})  {'PASS' if ok else 'FAIL'}")
        if not ok:
            fallas.append(f"nivel del pico de {f_esp:.0f} Hz: {rel:+.2f} dB")

    if enlace == "n3":
        s = np.concatenate(bloques_s)[:n].astype(np.float64)
        snr = 10.0 * np.log10(np.sum(s * s) / np.sum((x - s) ** 2))
        ok = abs(snr) <= TOL_SNR_DB
        lineas.append(f"SNR = {snr:+.3f} dB (esperado 0.0 ± {TOL_SNR_DB})  {'PASS' if ok else 'FAIL'}")
        if not ok:
            fallas.append(f"SNR de {snr:+.3f} dB")
    return lineas, fallas


# --- entrada ---

def capturar_en_vivo(args, receptor):
    """Lee el puerto serie durante --segundos; opcionalmente guarda los bytes crudos."""
    import serial  # solo hace falta en vivo
    destino = open(args.guardar, "wb") if args.guardar else None
    try:
        with serial.Serial(args.puerto, args.baudios, bytesize=8, parity="N", stopbits=1,
                           timeout=0.05) as ser:
            ser.reset_input_buffer()    # descarta lo que haya quedado en el búfer del sistema
            t0 = time.monotonic()
            proximo = t0 + 5.0
            while time.monotonic() - t0 < args.segundos:
                datos = ser.read(TROZO)
                if datos:
                    if destino:
                        destino.write(datos)
                    receptor.alimentar(datos)
                if time.monotonic() >= proximo:
                    print(receptor.resumen_progreso(time.monotonic() - t0), flush=True)
                    proximo += 5.0
    finally:
        if destino:
            destino.close()


def leer_archivo(ruta, receptor):
    """Procesa una captura cruda guardada antes, en trozos como si viniera del puerto."""
    crudo = Path(ruta).read_bytes()
    for i in range(0, len(crudo), TROZO):
        receptor.alimentar(crudo[i:i + TROZO])


def leer_argumentos():
    p = argparse.ArgumentParser(description="Receptor y validador de los paquetes del nodo 1.")
    fuente = p.add_mutually_exclusive_group(required=True)
    fuente.add_argument("--puerto", help="por ejemplo /dev/ttyUSB1")
    fuente.add_argument("--archivo", help="captura cruda previa")
    p.add_argument("--enlace", choices=sorted(ENLACES), required=True)
    p.add_argument("--segundos", type=float, default=60.0, help="duración en vivo (60 por defecto)")
    p.add_argument("--baudios", type=int, default=921600)
    p.add_argument("--guardar", help="guarda los bytes crudos recibidos (solo en vivo)")
    args = p.parse_args()
    if args.guardar and args.archivo:
        p.error("--guardar solo se usa con --puerto")
    return args


def main():
    args = leer_argumentos()
    receptor = Receptor(args.enlace)
    if args.puerto:
        capturar_en_vivo(args, receptor)
    else:
        leer_archivo(args.archivo, receptor)
    return receptor.terminar()


if __name__ == "__main__":
    sys.exit(main())
