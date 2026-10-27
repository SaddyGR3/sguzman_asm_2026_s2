"""Protocolo binario entre nodos: paquetes con cabecera, CRC-32 y COBS."""
import struct
import zlib

import numpy as np

# --- Cabecera ---
MAGIC = 0x5341
VERSION = 1
MAX_BYTES_CABLE = 4150
MUESTRAS_POR_PAQUETE = 512

# --- Tipos de paquete ---
TIPO_INPUT = 1
TIPO_INPUT_REF = 2
TIPO_FIR_OUT = 3
TIPO_DIAG = 4
TIPO_CONTROL = 5

# --- Banderas ---
FLAG_REFERENCIA = 0x0001
FLAG_CALENTAMIENTO = 0x0002
FLAG_REINICIO = 0x0004
FLAG_SATURACION = 0x0008
FLAG_DISCONTINUIDAD = 0x0010
FLAG_VENTANA_PARCIAL = 0x0020

# --- Formato de datos ---
FORMATO_METADATOS = 0
FORMATO_FLOAT32 = 1

# --- Opcodes de CONTROL ---
OPCODE_CONFIG = 1
OPCODE_START = 2
OPCODE_STOP = 3
OPCODE_STATUS = 4
OPCODE_ACK = 5

# --- Método del nodo 3 ---
METODO_PASA_TODO = 0
METODO_PICOS = 1
METODO_RESTA = 2
METODO_TOP_K = 3

# --- Tipo de ruido ---
RUIDO_NINGUNO = 0
RUIDO_TONAL = 1
RUIDO_RED = 2  # 50 o 60 Hz y armónicos
RUIDO_BANDA_ANCHA = 3
RUIDO_BANDA_LIMITADA = 4
RUIDO_IMPULSIVO = 5

# --- Filtro del nodo 2 ---
FILTRO_PASA_TODO = 0
FILTRO_FIR = 1  # FIR de la banda protegida
FILTRO_NOTCH = 2
FILTRO_PEINE = 3

# Origen: proyecto1/tarea1/revision/paso_9/calcular_comunicacion.py (Tarea 1), sin cambios.
HEADER = struct.Struct("<HBBBBHIIQHBBI")
CLAVES_HEADER = ("magic", "version", "type", "src", "dst", "flags", "session_id", "sequence",
                 "first_sample", "sample_count", "format", "channels", "payload_bytes")

ESTRUCTURA_DIAG = struct.Struct("<IHHBBBBffffffIIIIQI")
CLAVES_DIAG = ("fs", "N", "H", "metodo", "calentamiento", "tipo_ruido", "filtro_n2",
               "pico_Hz", "banda_lo", "banda_hi", "piso_resumen", "DC", "energia",
               "tiempo_us", "overruns", "perdidas", "saturaciones", "inicio_ventana", "config_id")

ESTRUCTURA_CONTROL = struct.Struct("<IHHBBHIQff")
CLAVES_CONTROL = ("fs", "N", "H", "metodo", "opcode", "status", "config_id",
                  "indice_efectivo", "banda_lo", "banda_hi")

# tipo -> (payload_bytes, sample_count, format, channels)
TABLA_TIPOS = {
    TIPO_INPUT: (4 * MUESTRAS_POR_PAQUETE, MUESTRAS_POR_PAQUETE, FORMATO_FLOAT32, 1),
    TIPO_INPUT_REF: (8 * MUESTRAS_POR_PAQUETE, MUESTRAS_POR_PAQUETE, FORMATO_FLOAT32, 2),
    TIPO_FIR_OUT: (4 * MUESTRAS_POR_PAQUETE, MUESTRAS_POR_PAQUETE, FORMATO_FLOAT32, 1),
    TIPO_DIAG: (ESTRUCTURA_DIAG.size, 0, FORMATO_METADATOS, 0),
    TIPO_CONTROL: (ESTRUCTURA_CONTROL.size, 0, FORMATO_METADATOS, 0),
}


class ErrorPaquete(Exception):
    """Paquete inválido. `causa` es una de: tamano, cobs, corto, crc, magic, version,
    tipo, longitud, formato, no_finito, destino."""

    def __init__(self, causa, mensaje):
        super().__init__(mensaje)
        self.causa = causa


# Origen: proyecto1/tarea1/revision/paso_9/calcular_comunicacion.py (Tarea 1), sin cambios.
def cobs_encode(data):
    out = bytearray([0])
    start, code = 0, 1
    for value in data:
        if value == 0:
            out[start] = code
            start = len(out)
            out.append(0)
            code = 1
        else:
            out.append(value)
            code += 1
            if code == 255:
                out[start] = code
                start = len(out)
                out.append(0)
                code = 1
    out[start] = code
    return bytes(out)


# Origen: proyecto1/tarea1/revision/paso_9/calcular_comunicacion.py (Tarea 1), sin cambios.
def cobs_decode(data):
    out = bytearray()
    i = 0
    while i < len(data):
        code = data[i]
        if code == 0 or i+code > len(data):
            raise ValueError("Trama COBS incompleta o inválida.")
        out.extend(data[i+1:i+code])
        i += code
        if code != 255 and i < len(data):
            out.append(0)
    return bytes(out)


# Origen: proyecto1/tarea1/revision/paso_9/calcular_comunicacion.py (Tarea 1), sin cambios.
def max_wire(payload):
    raw = HEADER.size+payload+4
    return raw+raw//254+2  # COBS y delimitador 0x00; cota conservadora.


def armar_paquete(tipo, src, dst, datos, flags=0, session_id=0, sequence=0, first_sample=0):
    """Devuelve los bytes para el cable, con el 0x00 final."""
    if tipo not in TABLA_TIPOS:
        raise ValueError(f"Tipo de paquete desconocido: {tipo}")
    payload, cuenta, formato, canales = TABLA_TIPOS[tipo]
    if len(datos) != payload:
        raise ValueError(f"El tipo {tipo} exige {payload} bytes de datos y recibió {len(datos)}.")
    cabecera = HEADER.pack(MAGIC, VERSION, tipo, src, dst, flags, session_id,
                           sequence & 0xFFFFFFFF, first_sample, cuenta, formato, canales,
                           len(datos))
    cuerpo = cabecera + datos
    return cobs_encode(cuerpo + struct.pack("<I", zlib.crc32(cuerpo))) + b"\x00"


def leer_paquete(trama, destino_esperado=None):
    """Recibe la trama sin el 0x00 final. Devuelve (cabecera, datos) o lanza ErrorPaquete."""
    if len(trama) + 1 > MAX_BYTES_CABLE:
        raise ErrorPaquete("tamano", f"La trama supera {MAX_BYTES_CABLE} bytes.")
    try:
        crudo = cobs_decode(trama)
    except ValueError as e:
        raise ErrorPaquete("cobs", str(e)) from e
    if len(crudo) < HEADER.size + 4:
        raise ErrorPaquete("corto", "La trama es menor que cabecera más CRC.")
    cuerpo, crc = crudo[:-4], struct.unpack("<I", crudo[-4:])[0]
    if zlib.crc32(cuerpo) != crc:
        raise ErrorPaquete("crc", "El CRC-32 no coincide.")
    cabecera = dict(zip(CLAVES_HEADER, HEADER.unpack(cuerpo[:HEADER.size])))
    datos = cuerpo[HEADER.size:]
    if cabecera["magic"] != MAGIC:
        raise ErrorPaquete("magic", f"Magic inválido: {cabecera['magic']:#06x}.")
    if cabecera["version"] != VERSION:
        raise ErrorPaquete("version", f"Versión no soportada: {cabecera['version']}.")
    if cabecera["type"] not in TABLA_TIPOS:
        raise ErrorPaquete("tipo", f"Tipo desconocido: {cabecera['type']}.")
    payload, cuenta, formato, canales = TABLA_TIPOS[cabecera["type"]]
    if cabecera["payload_bytes"] != len(datos) or len(datos) != payload:
        raise ErrorPaquete("longitud", "payload_bytes no coincide con los datos ni con el tipo.")
    if (cabecera["sample_count"], cabecera["format"], cabecera["channels"]) != (cuenta, formato, canales):
        raise ErrorPaquete("formato", "sample_count, format o channels no coinciden con el tipo.")
    if formato == FORMATO_FLOAT32 and not np.isfinite(np.frombuffer(datos, dtype="<f4")).all():
        raise ErrorPaquete("no_finito", "Hay muestras float32 no finitas.")
    if destino_esperado is not None and cabecera["dst"] != destino_esperado:
        raise ErrorPaquete("destino", f"Destino {cabecera['dst']}, se esperaba {destino_esperado}.")
    return cabecera, datos


def muestras_a_bytes(x):
    """(512,) o (512, 2) -> float32 little-endian; con 2 canales intercala x0, s0, x1, s1, ..."""
    return np.asarray(x, dtype="<f4").tobytes()


def bytes_a_muestras(datos, canales):
    """Inversa de muestras_a_bytes: forma (512,) o (512, 2)."""
    muestras = np.frombuffer(datos, dtype="<f4")
    return muestras.reshape(-1, 2) if canales == 2 else muestras


def _valores(campos, claves):
    faltan = [k for k in claves if k not in campos]
    sobran = [k for k in campos if k not in claves]
    if faltan or sobran:
        raise ValueError(f"Claves faltantes: {faltan}; claves sobrantes: {sobran}.")
    return [campos[k] for k in claves]


def empaquetar_diag(campos):
    return ESTRUCTURA_DIAG.pack(*_valores(campos, CLAVES_DIAG))


def desempaquetar_diag(datos):
    return dict(zip(CLAVES_DIAG, ESTRUCTURA_DIAG.unpack(datos)))


def empaquetar_control(campos):
    valores = _valores(campos, CLAVES_CONTROL)
    if campos["opcode"] != OPCODE_CONFIG and (campos["banda_lo"] != 0 or campos["banda_hi"] != 0):
        raise ValueError("banda_lo y banda_hi solo se usan con OPCODE_CONFIG; deben ser 0.")
    return ESTRUCTURA_CONTROL.pack(*valores)


def desempaquetar_control(datos):
    return dict(zip(CLAVES_CONTROL, ESTRUCTURA_CONTROL.unpack(datos)))
