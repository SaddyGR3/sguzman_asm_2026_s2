"""Estimaciones de multiplicaciones reales, memoria y latencia algorítmica.

Son modelos de costo, no mediciones del tiempo ni de la RAM de Python o del ESP32.
No cuentan sumas, cálculo de coeficientes, asignaciones ni todo el estimador de ruido.
memoria_valores expresa unidades equivalentes a float32, no el tipo de cada arreglo.
"""
import csv
from math import log2
from pathlib import Path
from shutil import get_terminal_size
from textwrap import fill

from sim import analogico, nodo2, nodo3, senales


def _fila(metodo, multiplicaciones, memoria, latencia, fs, nota):
    # Un float32 ocupa cuatro bytes; el factor 1000 convierte segundos a ms.
    return {
        "metodo": metodo,
        "mult_por_segundo": multiplicaciones,
        "memoria_valores": memoria,
        "memoria_bytes": 4 * memoria,
        "latencia_muestras": latencia,
        "latencia_ms": 1000 * latencia / fs,
        "nota": nota,
    }


def costo_fir(n_coef, fs_salida, fs_entrada=None):
    """FIR simétrico: costo por salida y retardo medido a la tasa de entrada."""
    fs = fs_salida if fs_entrada is None else fs_entrada
    return _fila(
        "FIR", n_coef * fs_salida, n_coef + n_coef - 1, (n_coef - 1) / 2, fs,
        "Mult/s=L*fs_salida; memoria=L+(L-1); retardo=(L-1)/2 a "
        f"{fs:g} Hz; se calcula solo cada salida conservada.",
    )


def costo_notch(fs):
    """Biquad en forma directa II transpuesta, con denominador normalizado."""
    # Un biquad normalizado usa cinco coeficientes y dos valores de estado.
    return _fila(
        "Notch IIR", 5 * fs, 5 + 2, 0, fs,
        "Mult/s=5*fs; memoria=5+2; alineación=0 muestras; introduce desfase "
        "y retardo de grupo dependiente de la frecuencia, no un retardo fijo.",
    )


def costo_dft_trama(N, fs, H):
    """Arreglos de dft_directa: entrada, salida, términos e índices.

    Excluye objetos Python, escalares y espacio de trabajo interno de NumPy.
    No es una medición del pico de RAM ni del proceso completo de comparación.
    """
    # Una multiplicación compleja convencional equivale a cuatro reales.
    # Tres arreglos complex128 (16 B) y uno float64 (8 B): 56 B por muestra,
    # equivalentes a catorce valores float32. El vector de términos se reutiliza.
    memoria = 14 * N
    return _fila(
        "DFT directa", 4 * N ** 2 * fs / H, memoria, 0, fs,
        "Mult/s=4*N²*fs/H; memoria base=56*N bytes: entrada, salida y términos "
        "complex128 e índices float64; excluye objetos y trabajo interno de NumPy; "
        "no es pico de RAM; "
        "latencia=0 solo como referencia, no tiempo de ejecución.",
    )


def costo_espectral(N, H, fs, historial_tramas):
    """FFT/IFFT radix-2, ventanas, ganancias y buffers del modelo espectral.

    Omite el costo de medianas y detección, temporales y espacio de trabajo FFT.
    El retardo de H muestras no incluye el tiempo de cómputo.
    """
    bins = N // 2 + 1  # Espectro unilateral real: incluye continua y Nyquist.
    # Dos transformadas, cuatro multiplicaciones reales por compleja,
    # dos ventanas y una ganancia real por cada parte del espectro complejo.
    mult_trama = 2 * (2 * N * log2(N)) + 2 * N + 2 * bins
    memoria = N + N + 2 * bins + bins + historial_tramas * bins + N
    return _fila(
        "Espectral", mult_trama * fs / H, memoria, H, fs,
        "Mult/s=(4*N*log2(N)+2*N+2*B)*fs/H; memoria=3*N+(3+historial)*B, "
        "B=N/2+1; retardo=H; excluye medianas, detección y temporales.",
    )


def tabla_costo(cfg_pruebas, cfg_n2, cfg_analogica):
    """Cuatro filas independientes de la configuración del nodo 3."""
    glob = cfg_pruebas["global"]
    fs = glob["fs_Hz"]
    fs_adc = cfg_analogica["tasas"]["fs_adc_Hz"]
    decimacion = cfg_analogica["decimacion"]
    fila_decimacion = costo_fir(
        decimacion["coeficientes"], fs_adc / decimacion["factor"], fs_entrada=fs_adc,
    )
    fila_decimacion["metodo"] = "FIR decimación nodo 1"
    fila_nodo2 = costo_fir(cfg_n2["fir_banda_protegida"]["coeficientes"], fs)
    fila_nodo2["metodo"] = "FIR banda protegida nodo 2"
    return [fila_decimacion, fila_nodo2, costo_notch(fs),
            costo_dft_trama(glob["N"], fs, glob["H"])]


def generar_costo(cfg_pruebas, cfg_n2, cfg_analogica, cfg_n3, salida):
    """Exporta e imprime los cinco métodos, incluido el nodo 3."""
    filas = tabla_costo(cfg_pruebas, cfg_n2, cfg_analogica)
    glob = cfg_pruebas["global"]
    espectral = costo_espectral(glob["N"], glob["H"], glob["fs_Hz"],
                                cfg_n3["historial_tramas"])
    espectral["metodo"] = "Espectral nodo 3"
    filas.append(espectral)
    destino = Path(salida) / "costo.csv"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]), lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)

    print("\nCosto estimado por método\n")
    ancho_metodo = max(len("Método"), *(len(fila["metodo"]) for fila in filas))
    encabezado = (f"{'Método':<{ancho_metodo}} | {'Mult./s':>15} | {'Equiv. f32':>10} | "
                  f"{'Bytes':>8} | {'Retardo (m)':>11} | {'Retardo (ms)':>12}")
    print(encabezado)
    print("-" * len(encabezado))
    for fila in filas:
        multiplicaciones = f"{fila['mult_por_segundo']:,.2f}".replace(",", " ")
        valores = f"{fila['memoria_valores']:,}".replace(",", " ")
        memoria = f"{fila['memoria_bytes']:,}".replace(",", " ")
        print(f"{fila['metodo']:<{ancho_metodo}} | {multiplicaciones:>15} | {valores:>10} | "
              f"{memoria:>8} | {fila['latencia_muestras']:>11g} | "
              f"{fila['latencia_ms']:>12.3f}")
    print("\nm = muestras; equiv. f32 = unidades de memoria de 4 bytes.")
    print("\nSupuestos de las estimaciones:")
    ancho = max(40, min(100, get_terminal_size().columns))
    for fila in filas:
        print(f"\n{fila['metodo']}:")
        print(fill(fila["nota"], width=ancho, initial_indent="  ", subsequent_indent="  "))
    return filas


if __name__ == "__main__":
    generar_costo(senales.cargar_config(), nodo2.cargar_config_nodo2(),
                  analogico.cargar_config_analogica(), nodo3.cargar_config_nodo3(),
                  Path(__file__).resolve().parents[1] / "resultados")
