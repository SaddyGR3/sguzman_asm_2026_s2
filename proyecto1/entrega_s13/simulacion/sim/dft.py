"""DFT desde su definición y comparación numérica y temporal con la FFT de NumPy."""
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from sim import senales


def dft_directa(x):
    """Calcula X[k] = suma de x[n] exp(-2j*pi*k*n/N), en complex128.

    Es la definición con N² multiplicaciones complejas, sin algoritmo rápido.
    Calcula una frecuencia a la vez y reutiliza un vector de términos.
    Arreglos principales: entrada, salida y términos complex128, e índices
    float64; suman 56*N bytes, sin objetos Python ni trabajo interno de NumPy.
    """
    x = np.asarray(x, dtype=np.complex128)
    if x.ndim != 1 or x.size == 0:
        raise ValueError("La señal debe ser un vector no vacío.")
    indices = np.arange(x.size, dtype=np.float64)
    espectro = np.empty(x.size, dtype=np.complex128)
    terminos = np.empty(x.size, dtype=np.complex128)
    for k in range(x.size):
        # out reutiliza el mismo arreglo para el exponente, el factor y x[n]*factor.
        np.multiply(indices, -2j * np.pi * k / x.size, out=terminos)
        np.exp(terminos, out=terminos)
        np.multiply(x, terminos, out=terminos)
        espectro[k] = np.sum(terminos)
    return espectro


def comparar_dft_fft(x, repeticiones):
    """Compara resultados y medianas de tiempos, incluyendo los factores de la DFT.

    El conteo de la FFT es el modelo radix-2, no un conteo interno de NumPy.
    Los tiempos incluyen el bucle Python y las llamadas a NumPy de cada método.
    Para la señal nula se define error relativo cero: ambas salidas son cero.
    """
    x = np.asarray(x, dtype=np.complex128)
    if x.ndim != 1 or x.size < 2 or x.size & (x.size - 1):
        raise ValueError("N debe ser una potencia de 2 mayor o igual a 2.")
    if not isinstance(repeticiones, (int, np.integer)) or repeticiones < 1:
        raise ValueError("Las repeticiones deben ser un entero mayor o igual a 1.")

    tiempos_dft, tiempos_fft = [], []
    for _ in range(repeticiones):
        inicio = perf_counter()
        espectro_dft = dft_directa(x)
        tiempos_dft.append(perf_counter() - inicio)
        inicio = perf_counter()
        espectro_fft = np.fft.fft(x)
        tiempos_fft.append(perf_counter() - inicio)

    amplitud_maxima = np.max(np.abs(espectro_fft))
    error = np.max(np.abs(espectro_dft - espectro_fft))
    tiempo_dft = float(np.median(tiempos_dft))
    tiempo_fft = float(np.median(tiempos_fft))
    N = x.size
    operaciones_dft = N ** 2
    operaciones_fft = (N // 2) * (N.bit_length() - 1)
    return {
        "N": N,
        "error_max_rel": float(error / amplitud_maxima) if amplitud_maxima else 0.0,
        "tiempo_dft_s": tiempo_dft,
        "tiempo_fft_s": tiempo_fft,
        "aceleracion": tiempo_dft / tiempo_fft,
        "operaciones_dft": operaciones_dft,
        "operaciones_fft": operaciones_fft,
        "cociente_operaciones": operaciones_dft / operaciones_fft,
    }


def senal_p1(config):
    """Selecciona N muestras de P1 desde el segundo 1, con su primera semilla."""
    N = config["global"]["N"]
    inicio = config["global"]["fs_Hz"]  # Un segundo, fuera de la rampa inicial.
    semilla = config["pruebas"]["P1"]["semillas"][0]
    caso = senales.generar_caso(config, "P1", semilla)
    senal_p1 = caso["x"][inicio:inicio + N]
    if senal_p1.size != N:
        raise ValueError("P1 no tiene N muestras disponibles después del primer segundo.")
    return senal_p1


def generar_dft(config, salida):
    """Compara ambas señales, guarda el JSON e imprime los resultados."""
    N = config["global"]["N"]
    # Cinco mediciones y semilla cero: condiciones del experimento comparativo.
    resultados = {
        "P1": comparar_dft_fft(senal_p1(config), 5),
        "aleatoria": comparar_dft_fft(np.random.default_rng(0).standard_normal(N), 5),
    }
    destino = Path(salida) / "dft_fft.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8") as archivo:
        json.dump(resultados, archivo, indent=2, ensure_ascii=False, allow_nan=False)
        archivo.write("\n")

    print("\nDFT directa frente a FFT (mediana de 5 mediciones)\n")
    encabezado = (f"{'Señal':<10} | {'Error relativo':>14} | {'DFT (ms)':>10} | "
                  f"{'FFT (ms)':>10} | {'Aceleración':>12} | {'Op. DFT/FFT':>11}")
    print(encabezado)
    print("-" * len(encabezado))
    for nombre, fila in resultados.items():
        print(f"{nombre:<10} | {fila['error_max_rel']:>14.3e} | "
              f"{1000 * fila['tiempo_dft_s']:>10.3f} | "
              f"{1000 * fila['tiempo_fft_s']:>10.4f} | "
              f"{fila['aceleracion']:>11.2f}x | {fila['cociente_operaciones']:>11.2f}")
    print("\nAceleración: razón de tiempos medidos; op. DFT/FFT: razón teórica de operaciones.")
    return resultados


if __name__ == "__main__":
    generar_dft(senales.cargar_config(), Path(__file__).resolve().parents[1] / "resultados")
