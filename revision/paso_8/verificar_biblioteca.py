"""Comprueba fuentes ESP-DSP v1.8.2 y deriva el presupuesto seleccionado.

Lee copias oficiales descargadas; no instala ni ejecuta firmware.
"""
from pathlib import Path
import argparse
import ctypes
import hashlib
import json
import re

RAIZ = Path(__file__).resolve().parents[2]
ARCHIVOS = {
    "bitrev.c": "modules/fft/float/dsps_fft2r_bitrev_tables_fc32.c",
    "fft_ansi.c": "modules/fft/float/dsps_fft2r_fc32_ansi.c",
    "fft.h": "modules/fft/include/dsps_fft2r.h",
    "fir_init.c": "modules/fir/float/dsps_fir_init_f32.c",
    "fir_ansi.c": "modules/fir/float/dsps_fir_f32_ansi.c",
    "fir_ae32.S": "modules/fir/float/dsps_fir_f32_ae32.S",
    "fir.h": "modules/fir/include/dsps_fir.h",
    "idf_component.yml": "idf_component.yml",
    "Kconfig": "Kconfig",
    "LICENSE": "LICENSE",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fuentes", required=True, type=Path)
    args = parser.parse_args()
    textos = {nombre: (args.fuentes/nombre).read_text() for nombre in ARCHIVOS}
    match = re.search(r"bitrev2r_table_1024_fc32_size\s*=\s*(\d+)", textos["bitrev.c"])
    if not match:
        raise ValueError("No se encuentra el tamaño de la tabla de 1024.")
    pares = int(match[1])
    cuerpo = re.search(r"bitrev2r_table_1024_fc32\[\]\s*=\s*\{(.*?)\}", textos["bitrev.c"], re.S)[1]
    if len(re.findall(r"\d+", cuerpo)) != 2*pares:
        raise ValueError("La tabla no coincide con el número de pares.")
    for nombre, patron in [
        ("fft_ansi.c", r"table_size\s*\*\s*sizeof\(float\)"),
        ("fft_ansi.c", r"2\s*\*\s*dsps_fft2r_rev_tables_fc32_size"),
        ("fir_init.c", r"coeffs_len\s*\+\s*4"),
        ("idf_component.yml", r'idf:\s*">=4\.2"'),
        ("Kconfig", r"config DSP_MAX_FFT_SIZE_1024"),
        ("LICENSE", r"Apache License"),
    ]:
        if not re.search(patron, textos[nombre]):
            raise ValueError(f"La fuente {nombre} no contiene el requisito esperado.")

    # Modelo ABI ESP32 de 32 bits; sizeof real se comprobará en firmware.
    class Fir32(ctypes.Structure):
        _fields_ = [("coeffs", ctypes.c_uint32), ("delay", ctypes.c_uint32),
                    ("N", ctypes.c_int32), ("pos", ctypes.c_int32),
                    ("decim", ctypes.c_int32), ("use_delay", ctypes.c_int16),
                    ("delay_size", ctypes.c_int32), ("interp", ctypes.c_int32),
                    ("interp_pos", ctypes.c_int32), ("start_pos", ctypes.c_int32)]

    p7 = RAIZ / "revision/paso_7/presupuesto_esp32.json"
    previo = json.loads(p7.read_text())
    n = previo["parametros"]["N_fft"]
    if n != 1024 or pares != 496:
        raise ValueError("Este presupuesto está verificado para N=1024 y 496 pares.")
    tablas = n*4 + 2*pares*2
    m = previo["memoria_espectral"]
    subtotal = m["subtotal_dsp_bytes"]-m["componentes_bytes"]["Reserva provisional tablas/workspace FFT"]+tablas
    total = subtotal+m["reserva_auxiliar_bytes"]
    fir = 37*4+41*4+ctypes.sizeof(Fir32)
    resultado = {
        "fecha_consulta": "2026-10-12",
        "estado": "fuentes_y_calculos_verificados_sin_compilacion_ESP32",
        "seleccion": {"biblioteca": "ESP-DSP", "version": "1.8.2",
            "commit_tag": "a53a0756833c045311ea1d79a2badf495cdfde4c", "licencia": "Apache-2.0",
            "idf_minimo_manifest": "4.2", "target": "esp32", "precision": "float32"},
        "fuentes": [{"archivo": nombre, "url": f"https://raw.githubusercontent.com/espressif/esp-dsp/v1.8.2/{ruta}",
                     "sha256": hashlib.sha256((args.fuentes/nombre).read_bytes()).hexdigest()} for nombre,ruta in ARCHIVOS.items()],
        "sha256_presupuesto_paso_7": hashlib.sha256(p7.read_bytes()).hexdigest(),
        "memoria_fft": {"buffer_complejo_bytes": 2*n*4, "twiddles_bytes": n*4,
            "pares_bit_reversal": pares, "copia_bit_reversal_bytes": 2*pares*2,
            "tablas_ram_bytes": tablas, "nota": "Payload de tablas; metadatos, alineación y allocator siguen en reservas."},
        "memoria_espectral": {"subtotal_dsp_bytes": subtotal, "reserva_auxiliar_bytes": m["reserva_auxiliar_bytes"],
            "total_provisional_bytes": total, "total_KiB": total/1024,
            "objetivo_bytes": m["objetivo_bytes"], "margen_bytes": m["objetivo_bytes"]-total},
        "memoria_fir_biblioteca": {"coeficientes_bytes": 37*4, "delay_bytes": 41*4,
            "estructura_ABI32_bytes_estimados": ctypes.sizeof(Fir32), "nucleo_estimado_bytes": fir,
            "subtotal_con_io_y_control_bytes": previo["memoria_temporal"]["subtotal_dsp_bytes"]-292+fir,
            "nota": "sizeof(fir_f32_t) pendiente en el compilador destino; control separado de la estructura."},
    }
    destino = Path(__file__).with_name("seleccion_bibliotecas.json")
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2)+"\n")
    print(f"Tablas FFT: {tablas} bytes; espectral provisional: {total} bytes ({total/1024:.2f} KiB).")
    print(f"FIR ESP-DSP: núcleo estimado {fir} bytes; configuración y licencia contrastadas.")


if __name__ == "__main__":
    main()
