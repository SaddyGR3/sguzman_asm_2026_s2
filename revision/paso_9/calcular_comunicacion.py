"""Dimensiona enlaces y memoria y produce una trama binaria de referencia.

Modelo de diseño; no mide UART ni ejecuta filtros de firmware.
"""
from pathlib import Path
import hashlib
import json
import struct
import zlib
import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
HEADER = struct.Struct("<HBBBBHIIQHBBI")
BAUD = 921600


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


def max_wire(payload):
    raw = HEADER.size+payload+4
    return raw+raw//254+2  # COBS y delimitador 0x00; cota conservadora.


def main():
    p7_path = RAIZ/"revision/paso_7/presupuesto_esp32.json"
    p8_path = RAIZ/"revision/paso_8/seleccion_bibliotecas.json"
    p7, p8 = json.loads(p7_path.read_text()), json.loads(p8_path.read_text())
    fs, n, h = (p7["parametros"][key] for key in ("fs_Hz", "N_fft", "hop"))
    if HEADER.size != 32 or (fs,n,h) != (8000,1024,512):
        raise ValueError("El diseño está definido para cabecera 32, fs=8000, N=1024, H=512.")
    packets = {name: {"payload_bytes": size, "raw_bytes": HEADER.size+size+4,
                      "wire_max_bytes": max_wire(size)}
               for name,size in {"INPUT": h*4, "INPUT_REF": h*8, "FIR_OUT": h*4,
                                 "DIAG": 64, "CONTROL": 32}.items()}
    links = []
    for name, types in [("N1→N2", ("INPUT", "DIAG")),
                        ("N1→N3_con_referencia", ("INPUT_REF", "DIAG")),
                        ("N1→N3_sin_referencia", ("INPUT", "DIAG")),
                        ("N2→N3", ("FIR_OUT",))]:
        size = sum(packets[t]["wire_max_bytes"] for t in types)
        rate = size*10*fs/h  # UART 8N1: 10 bits por byte.
        links.append({"enlace": name, "paquetes_por_avance": list(types),
                      "bytes_max_por_avance": size, "baud_minimo_teorico": rate,
                      "baud_con_reserva_control": rate+7000,
                      "ocupacion_pct": 100*rate/BAUD,
                      "ocupacion_con_control_pct": 100*(rate+7000)/BAUD,
                      "serializacion_ms": 1000*size*10/BAUD})

    # Presupuestos por dispositivo, sin compartir buffers entre placas.
    n1 = {"FFT": 8192, "tablas_FFT": 6080, "ventana": 4096,
          "historial_x": 4096, "magnitudes": 2052, "scratch": 124,
          "doble_buffer_adquisicion_x_s": 8192, "dos_paquetes_TX_COBS": 6244,
          "control": 1024, "UART_pilas_DMA_colas_reserva": 32768}
    n2 = {"FIR_biblioteca": p8["memoria_fir_biblioteca"]["nucleo_estimado_bytes"],
          "buffers_IO": 8192, "dos_decodificadores_RX": 2084+68,
          "dos_paquetes_TX_COBS": 2094+70, "control": 1024,
          "UART_pilas_DMA_colas_reserva": 32768}
    n3 = {"DSP_y_buffers_paso_8": p8["memoria_espectral"]["subtotal_dsp_bytes"],
          "FIFO_referencia_4H": 4*h*4, "FIFO_FIR_4H": 4*h*4,
          "dos_decodificadores_RX": 4132+2084, "dos_paquetes_CONTROL_TX": 2*70,
          "DC_referencia_historial": n*4, "OLA_util": n*4,
          "FIR_referencia_biblioteca": p8["memoria_fir_biblioteca"]["nucleo_estimado_bytes"],
          "UART_pilas_DMA_colas_reserva": 40960}
    memories = {name: {"componentes_bytes": values, "total_provisional_bytes": sum(values.values()),
                       "total_KiB": sum(values.values())/1024, "objetivo_bytes": quota*1024,
                       "margen_bytes": quota*1024-sum(values.values())}
                for name,values,quota in [("N1",n1,96),("N2",n2,64),("N3",n3,160)]}

    source = RAIZ/"seccion_2_2/2_2_generacionsenales/pruebas/caso_1/muestras_exactas.npz"
    with np.load(source) as z:
        payload = np.column_stack((z["contaminada"][:h],z["limpia"][:h])).astype("<f4").tobytes()
    header = HEADER.pack(0x5341,1,2,1,3,1,1,0,0,h,1,2,len(payload))
    body = header+payload
    raw = body+struct.pack("<I",zlib.crc32(body))
    wire = cobs_encode(raw)+b"\0"
    decoded = cobs_decode(wire[:-1])
    if decoded != raw or len(wire)>max_wire(len(payload)):
        raise ValueError("La trama no conserva los bytes o excede la cota.")
    if zlib.crc32(b"123456789") != 0xCBF43926:
        raise ValueError("Variante CRC incorrecta.")
    # Vectores externos simples y límites de stuffing, incluidos ceros.
    if cobs_encode(b"\x11\x00\x22") != b"\x02\x11\x02\x22":
        raise ValueError("No coincide el vector COBS conocido.")
    for size in (0,1,253,254,255,2084,4132):
        for data in (b"\x01"*size,b"\x00"*size):
            encoded = cobs_encode(data)
            if cobs_decode(encoded)!=data or len(encoded)+1>size+size//254+2:
                raise ValueError("Fallo en un límite COBS.")
    bad = bytearray(decoded)
    bad[100] ^= 1
    if zlib.crc32(bad[:-4]) == struct.unpack("<I",bad[-4:])[0]:
        raise ValueError("La corrupción no fue detectada.")

    spectral_link = next(x for x in links if x["enlace"]=="N1→N3_con_referencia")
    control_ms = 1000*max_wire(32)*10/BAUD
    t_spectral = 128+spectral_link["serializacion_ms"]+control_ms+48+1
    fir_link = next(x for x in links if x["enlace"]=="N1→N2")
    y_link = next(x for x in links if x["enlace"]=="N2→N3")
    t_fir_aligned = 128+fir_link["serializacion_ms"]+48+y_link["serializacion_ms"]+2*control_ms+2
    result = {"estado": "arquitectura_y_modelo_verificados_sin_hardware", "fs_Hz": fs,
        "N": n, "H": h, "avance_ms": 1000*h/fs, "baud_propuesto": BAUD, "UART": "8N1",
        "header_struct": HEADER.format, "header_bytes": HEADER.size,
        "crc": "CRC-32/ISO-HDLC; poly 0x04C11DB7; refin/refout true; init/xorout 0xFFFFFFFF; check 0xCBF43926",
        "paquetes": packets, "enlaces": links, "memoria_por_nodo": memories,
        "control_por_sentido_max": {"tramas_por_segundo": 10, "bytes_por_trama_max": max_wire(32),
                              "baud_requerido": 10*10*max_wire(32)},
        "latencia_modelo": {"retardo_reproduccion_ms": 256, "margen_lanzamiento_TX_ms": 1,
            "disponibilidad_espectral_ms": t_spectral,
            "disponibilidad_FIR_alineado_ms": t_fir_aligned,
            "nota": "Incluye DSP objetivo 48 ms, un control por avance/enlace y 1 ms de lanzamiento por enlace; sin otra cola. No es una medición."},
        "ejemplo": {"tipo": "INPUT_REF", "caso": 1, "muestras": h,
            "wire_bytes_reales": len(wire), "sha256_trama": hashlib.sha256(wire).hexdigest(),
            "sha256_fuente": hashlib.sha256(source.read_bytes()).hexdigest(),
            "nota": "Conversión a float32 solo para la trama; las fuentes originales no cambian."},
        "fuentes_sha256": {str(p.relative_to(RAIZ)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (p7_path,p8_path)},
    }
    folder = Path(__file__).parent
    (folder/"trama_ejemplo.bin").write_bytes(wire)
    (folder/"presupuesto_comunicacion.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    for l in links:
        print(f"{l['enlace']}: {l['bytes_max_por_avance']} B, mínimo {l['baud_minimo_teorico']:.1f} baud, ocupación {l['ocupacion_pct']:.2f}%.")
    for name,m in memories.items():
        print(f"{name}: {m['total_provisional_bytes']} B ({m['total_KiB']:.2f} KiB), reserva objetivo {m['objetivo_bytes']//1024} KiB.")
    print("Cabecera, CRC conocido, límites COBS, trama oficial y corrupción de un bit: correctos.")


if __name__ == "__main__":
    main()
