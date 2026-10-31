import struct
import zlib

import numpy as np
import pytest

from sim import protocolo as p

METODOS = (p.METODO_PASA_TODO, p.METODO_PICOS, p.METODO_RESTA, p.METODO_TOP_K)
RUIDOS = (p.RUIDO_NINGUNO, p.RUIDO_TONAL, p.RUIDO_RED, p.RUIDO_BANDA_ANCHA,
          p.RUIDO_BANDA_LIMITADA, p.RUIDO_IMPULSIVO)
FILTROS = (p.FILTRO_PASA_TODO, p.FILTRO_FIR, p.FILTRO_NOTCH, p.FILTRO_PEINE)
OPCODES = (p.OPCODE_CONFIG, p.OPCODE_START, p.OPCODE_STOP, p.OPCODE_STATUS, p.OPCODE_ACK)
FLAGS = (p.FLAG_REFERENCIA, p.FLAG_CALENTAMIENTO, p.FLAG_REINICIO, p.FLAG_SATURACION,
         p.FLAG_DISCONTINUIDAD, p.FLAG_VENTANA_PARCIAL)
TODAS_LAS_BANDERAS = sum(FLAGS)

# Valores exactos en float32 para comparar con ==.
DIAG_EJEMPLO = {
    "fs": 8000, "N": 1024, "H": 512, "metodo": p.METODO_PICOS, "calentamiento": 0,
    "tipo_ruido": p.RUIDO_TONAL, "filtro_n2": p.FILTRO_NOTCH,
    "pico_Hz": 2150.0, "banda_lo": -1.0, "banda_hi": -1.0, "piso_resumen": 0.25,
    "DC": 0.0, "energia": 12.5, "tiempo_us": 1234, "overruns": 1, "perdidas": 2,
    "saturaciones": 3, "inicio_ventana": 512, "config_id": 7,
}
CONTROL_EJEMPLO = {
    "fs": 8000, "N": 1024, "H": 512, "metodo": p.METODO_RESTA, "opcode": p.OPCODE_CONFIG,
    "status": 0, "config_id": 7, "indice_efectivo": 4096, "banda_lo": 100.0, "banda_hi": 1200.0,
}


def _muestras():
    return np.linspace(-0.5, 0.5, p.MUESTRAS_POR_PAQUETE, dtype=np.float32)


def _datos(tipo):
    if tipo in (p.TIPO_INPUT, p.TIPO_FIR_OUT):
        return p.muestras_a_bytes(_muestras())
    if tipo == p.TIPO_INPUT_REF:
        return p.muestras_a_bytes(np.column_stack((_muestras(), 2 * _muestras())))
    if tipo == p.TIPO_DIAG:
        return p.empaquetar_diag(DIAG_EJEMPLO)
    return p.empaquetar_control(CONTROL_EJEMPLO)


def _crudo(tipo=p.TIPO_INPUT, magic=p.MAGIC, version=p.VERSION, dst=2, payload_bytes=None,
           sample_count=None, formato=None, canales=None, datos=None):
    """Trama (sin 0x00 final) con CRC válido y campos de cabecera a voluntad."""
    payload, cuenta, fmt, can = p.TABLA_TIPOS.get(tipo, (0, 0, 0, 0))
    datos = bytes(payload) if datos is None else datos
    cabecera = p.HEADER.pack(
        magic, version, tipo, 1, dst, 0, 0, 0, 0,
        cuenta if sample_count is None else sample_count,
        fmt if formato is None else formato,
        can if canales is None else canales,
        len(datos) if payload_bytes is None else payload_bytes)
    cuerpo = cabecera + datos
    return p.cobs_encode(cuerpo + struct.pack("<I", zlib.crc32(cuerpo)))


def _causa(trama, **kwargs):
    with pytest.raises(p.ErrorPaquete) as e:
        p.leer_paquete(trama, **kwargs)
    return e.value.causa


def test_crc32_vector():
    assert zlib.crc32(b"123456789") == 0xCBF43926


def test_cobs_ejemplo():
    assert p.cobs_encode(b"\x11\x00\x22") == b"\x02\x11\x02\x22"


@pytest.mark.parametrize("n", (0, 1, 253, 254, 255, 2084, 4132))
@pytest.mark.parametrize("relleno", (b"\x01", b"\x00"))
def test_cobs_limites(n, relleno):
    d = relleno * n
    codificado = p.cobs_encode(d)
    assert p.cobs_decode(codificado) == d
    assert len(codificado) + 1 <= n + n // 254 + 2


def test_tamanos_de_estructuras():
    assert p.HEADER.size == 32
    assert p.ESTRUCTURA_DIAG.size == 64
    assert p.ESTRUCTURA_CONTROL.size == 32


@pytest.mark.parametrize("tipo, esperado", (
    (p.TIPO_INPUT, 2094), (p.TIPO_FIR_OUT, 2094), (p.TIPO_INPUT_REF, 4150),
    (p.TIPO_DIAG, 102), (p.TIPO_CONTROL, 70)))
def test_max_wire(tipo, esperado):
    datos = _datos(tipo)
    assert p.max_wire(len(datos)) == esperado
    assert len(p.armar_paquete(tipo, 1, 2, datos)) <= esperado


def test_magic_en_el_cable():
    wire = p.armar_paquete(p.TIPO_INPUT, 1, 2, _datos(p.TIPO_INPUT))
    assert p.cobs_decode(wire[:-1])[:2] == b"\x41\x53"


@pytest.mark.parametrize("tipo", sorted(p.TABLA_TIPOS))
def test_ida_y_vuelta(tipo):
    datos = _datos(tipo)
    wire = p.armar_paquete(tipo, 1, 2, datos, flags=TODAS_LAS_BANDERAS, session_id=9,
                           sequence=5, first_sample=1024)
    assert wire[-1] == 0 and wire.count(b"\x00") == 1
    cabecera, recibidos = p.leer_paquete(wire[:-1], destino_esperado=2)
    payload, cuenta, formato, canales = p.TABLA_TIPOS[tipo]
    assert recibidos == datos
    assert cabecera == {
        "magic": p.MAGIC, "version": p.VERSION, "type": tipo, "src": 1, "dst": 2,
        "flags": TODAS_LAS_BANDERAS, "session_id": 9, "sequence": 5, "first_sample": 1024,
        "sample_count": cuenta, "format": formato, "channels": canales, "payload_bytes": payload}


def test_input_ref_intercalado():
    x, s = _muestras(), 2 * _muestras()
    datos = p.muestras_a_bytes(np.column_stack((x, s)))
    plano = np.frombuffer(datos, dtype="<f4")
    assert np.array_equal(plano[0::2], x) and np.array_equal(plano[1::2], s)
    m = p.bytes_a_muestras(datos, 2)
    assert m.shape == (512, 2)
    assert np.array_equal(m[:, 0], x) and np.array_equal(m[:, 1], s)
    assert p.bytes_a_muestras(p.muestras_a_bytes(x), 1).shape == (512,)


def test_diag_ida_y_vuelta_con_constantes():
    for metodo in METODOS:
        for ruido in RUIDOS:
            for filtro in FILTROS:
                campos = dict(DIAG_EJEMPLO, metodo=metodo, tipo_ruido=ruido, filtro_n2=filtro)
                assert p.desempaquetar_diag(p.empaquetar_diag(campos)) == campos


def test_control_ida_y_vuelta_con_opcodes():
    for opcode in OPCODES:
        banda = (100.0, 1200.0) if opcode == p.OPCODE_CONFIG else (0.0, 0.0)
        campos = dict(CONTROL_EJEMPLO, opcode=opcode, banda_lo=banda[0], banda_hi=banda[1])
        assert p.desempaquetar_control(p.empaquetar_control(campos)) == campos


def test_control_banda_fuera_de_config():
    with pytest.raises(ValueError):
        p.empaquetar_control(dict(CONTROL_EJEMPLO, opcode=p.OPCODE_START))


def test_empaquetar_exige_claves_exactas():
    with pytest.raises(ValueError):
        p.empaquetar_diag({k: v for k, v in DIAG_EJEMPLO.items() if k != "DC"})
    with pytest.raises(ValueError):
        p.empaquetar_control(dict(CONTROL_EJEMPLO, extra=1))


def test_sequence_modulo_2_32():
    for sequence, esperado in ((2**32, 0), (2**32 + 5, 5)):
        wire = p.armar_paquete(p.TIPO_INPUT, 1, 2, _datos(p.TIPO_INPUT), sequence=sequence)
        assert p.leer_paquete(wire[:-1])[0]["sequence"] == esperado


def test_armar_rechaza_longitud_y_tipo():
    with pytest.raises(ValueError):
        p.armar_paquete(p.TIPO_INPUT, 1, 2, bytes(100))
    with pytest.raises(ValueError):
        p.armar_paquete(9, 1, 2, b"")


def test_crudo_valido():
    cabecera, datos = p.leer_paquete(_crudo())
    assert cabecera["type"] == p.TIPO_INPUT and len(datos) == 2048


def test_error_crc_por_un_bit():
    crudo = bytearray(p.cobs_decode(p.armar_paquete(p.TIPO_INPUT, 1, 2, _datos(p.TIPO_INPUT))[:-1]))
    crudo[p.HEADER.size + 10] ^= 0x01
    assert _causa(p.cobs_encode(bytes(crudo))) == "crc"


def test_error_tamano():
    assert _causa(b"\x01" * p.MAX_BYTES_CABLE) == "tamano"


@pytest.mark.parametrize("trama", (b"\x00\x11\x22", b"\x05\x11\x22"))
def test_error_cobs(trama):
    assert _causa(trama) == "cobs"


def test_error_corto():
    assert _causa(p.cobs_encode(bytes(10))) == "corto"


def test_error_magic():
    assert _causa(_crudo(magic=0x1234)) == "magic"


def test_error_version():
    assert _causa(_crudo(version=2)) == "version"


@pytest.mark.parametrize("tipo", (0, 6, 9))
def test_error_tipo(tipo):
    assert _causa(_crudo(tipo=tipo)) == "tipo"


def test_error_longitud():
    assert _causa(_crudo(payload_bytes=100)) == "longitud"
    assert _causa(_crudo(payload_bytes=100, datos=bytes(100))) == "longitud"


def test_error_formato():
    assert _causa(_crudo(sample_count=256)) == "formato"
    assert _causa(_crudo(formato=p.FORMATO_METADATOS)) == "formato"
    assert _causa(_crudo(canales=2)) == "formato"


@pytest.mark.parametrize("valor", (np.nan, np.inf, -np.inf))
def test_error_no_finito(valor):
    x = _muestras().copy()
    x[10] = valor
    wire = p.armar_paquete(p.TIPO_INPUT, 1, 2, p.muestras_a_bytes(x))
    assert _causa(wire[:-1]) == "no_finito"


def test_error_destino():
    wire = p.armar_paquete(p.TIPO_INPUT, 1, 2, _datos(p.TIPO_INPUT))
    assert _causa(wire[:-1], destino_esperado=3) == "destino"
