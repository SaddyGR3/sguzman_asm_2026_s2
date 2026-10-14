"""Presupuesto de diseño, no medición de tiempo ni RAM de un ESP32."""
from pathlib import Path
import hashlib
import json
import math

RAIZ = Path(__file__).resolve().parents[2]


def main():
    protocolo = RAIZ / "revision/paso_2/protocolo.json"
    p = json.loads(protocolo.read_text())
    fs, n, h = p["fs_Hz"], p["espectral"]["N"], p["espectral"]["hop"]
    k, w, b = n//2+1, 8, 4
    taps = p["temporal"]["orden"]+1
    componentes = [
        ("Historial de señal centrada", n*b),
        ("Historial DC para restauración alineada", n*b),
        ("FFT/IFFT compleja in-place", 2*n*b),
        ("Ventana sqrt-Hann", n*b),
        ("Acumulador overlap-add", n*b),
        ("Magnitud actual", k*b),
        ("Historial de magnitudes, W=8", w*k*b),
        ("Perfil mediano", k*b),
        ("Piso suavizado", k*b),
        ("Ganancia por bin", k*b),
        ("Máscara protegida uint8", k),
        ("Scratch mediana temporal/frecuencial", 31*b),
        ("Reserva provisional tablas/workspace FFT", 2*n*b),
        ("Dos buffers de entrada y dos de salida, H float32", 4*h*b),
        ("Reserva control, contadores y alineación", 1024),
    ]
    dsp = sum(v for _, v in componentes)
    auxiliares = 16*1024
    objetivo = 96*1024
    temporal_nucleo = (taps+taps-1)*b
    salida = {
        "estado": "propuesta_sin_validacion_en_hardware",
        "sha256_protocolo": hashlib.sha256(protocolo.read_bytes()).hexdigest(),
        "parametros": {"fs_Hz": fs, "N_fft": n, "hop": h, "bins_rfft": k,
                       "float_bytes": b, "tramas_historial": w, "tau_dc_s": 1.0,
                       "beta_dc": 1-math.exp(-1/fs), "limite_dsp_propuesto_ms": 0.75*1000*h/fs},
        "alternativas_fft": [{"N": m, "delta_f_Hz": fs/m, "ventana_ms": 1000*m/fs,
                              "hop_ms": 1000*(m//2)/fs} for m in (256, 512, 1024)],
        "tiempos_derivados": {"periodo_muestra_us": 1e6/fs, "ventana_ms": 1000*n/fs,
            "hop_ms": 1000*h/fs, "tramas_por_segundo": fs/h,
            "span_historial_completo_ms": 1000*(n+(w-1)*h)/fs,
            "retardo_fir_ms": 1000*p["temporal"]["retardo_muestras"]/fs,
            "retardo_programado_espectral_ms": 1000*(n+h)/fs},
        "memoria_espectral": {"componentes_bytes": dict(componentes), "subtotal_dsp_bytes": dsp,
            "reserva_auxiliar_bytes": auxiliares, "total_provisional_bytes": dsp+auxiliares,
            "objetivo_bytes": objetivo, "margen_objetivo_bytes": objetivo-dsp-auxiliares,
            "nota": "Auxiliares: provisión para DMA, pilas y colas; no es toda la RAM del firmware. Biblioteca e interfaz pendientes."},
        "memoria_temporal": {"coeficientes_y_estado_float32_bytes": temporal_nucleo,
            "coeficientes_y_estado_q15_bytes": temporal_nucleo//2,
            "buffers_io_float32_bytes": 4*h*b, "control_bytes": 1024,
            "subtotal_dsp_bytes": temporal_nucleo+4*h*b+1024},
        "operaciones": {"fir_mac_por_hop": taps*h, "fir_mac_por_segundo": taps*fs,
            "fft_compleja_radix2_butterflies_por_transformada": n//2*int(math.log2(n)),
            "fft_mas_ifft_butterflies_por_hop": n*int(math.log2(n)),
            "nota": "Conteos algorítmicos de referencia; no son ciclos CPU ni incluyen medianas, magnitudes, ventanas, E/S o métricas."},
    }
    destino = Path(__file__).with_name("presupuesto_esp32.json")
    destino.write_text(json.dumps(salida, indent=2, ensure_ascii=False)+"\n")
    print(f"DSP espectral: {dsp} bytes; con reserva: {dsp+auxiliares} bytes.")
    print(f"FIR coeficientes/estado: {temporal_nucleo} bytes; DSP con E/S: {temporal_nucleo+4*h*b+1024} bytes.")
    print(f"Plazo por hop: {1000*h/fs:g} ms; objetivo DSP: {0.75*1000*h/fs:g} ms.")


if __name__ == "__main__":
    main()
