#!/usr/bin/env python3

from pathlib import Path
import csv
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


SECCION = Path(__file__).resolve().parents[1]
FIGURAS = SECCION / "resultados" / "figuras"
TABLAS = SECCION / "resultados" / "tablas"
RESULTADOS_JSON = SECCION / "resultados" / "resultados_2_1.json"

FIGURAS.mkdir(parents=True, exist_ok=True)
TABLAS.mkdir(parents=True, exist_ok=True)


def dft_directa(x):
    """DFT implementada directamente a partir de su definición."""
    x = np.asarray(x, dtype=float)
    N = x.size
    n = np.arange(N)
    k = n[:, None]
    W = np.exp(-2j * np.pi * k * n / N)
    return W @ x


def inciso_a():
    N = 32
    n = np.arange(N)

    x = (
        np.cos(2 * np.pi * 3 * n / N)
        + 0.5 * np.cos(2 * np.pi * 7 * n / N + 0.4)
    )

    X_directa = dft_directa(x)
    X_fft = np.fft.fft(x)

    error = float(np.max(np.abs(X_directa - X_fft)))

    print("=" * 60)
    print("2.1(a) DFT DIRECTA VS FFT")
    print("=" * 60)
    print(f"N = {N}")
    print(f"Error máximo = {error:.6e}")

    return {
        "N": N,
        "error_max_dft_vs_fft": error,
    }


def inciso_b(fs=8000.0):
    tamanos = [256, 512, 1024, 2048]
    filas = []

    for N in tamanos:
        T = N / fs
        df = fs / N

        entrada_float32 = N * 4
        espectro_complex64 = N * 8

        filas.append({
            "N": N,
            "T_s": T,
            "T_ms": 1000 * T,
            "df_Hz": df,
            "entrada_float32_bytes": entrada_float32,
            "espectro_complex64_bytes": espectro_complex64,
            "total_bytes": entrada_float32 + espectro_complex64,
        })

    ruta_csv = TABLAS / "resolucion_frecuencial.csv"
    with ruta_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=filas[0].keys())
        writer.writeheader()
        writer.writerows(filas)

    print("\n" + "=" * 60)
    print("2.1(b) RESOLUCIÓN FRECUENCIAL")
    print("=" * 60)
    print("fs = 8000 Hz")
    print()
    print("   N       T [ms]      Δf [Hz]    memoria básica [KiB]")
    for fila in filas:
        print(
            f"{fila['N']:4d}"
            f"{fila['T_ms']:12.3f}"
            f"{fila['df_Hz']:13.6f}"
            f"{fila['total_bytes']/1024:20.3f}"
        )

    ref = next(f for f in filas if f["N"] == 1024)

    return {
        "fs_Hz": fs,
        "tabla": filas,
        "referencia_N_1024": ref,
    }


def espectro_ventana(x, ventana, fs):
    xw = x * ventana
    X = np.fft.rfft(xw)
    f = np.fft.rfftfreq(x.size, d=1 / fs)

    # Normalización por ganancia coherente para comparar amplitudes.
    escala = np.sum(ventana)
    mag = 2.0 * np.abs(X) / escala

    # DC y Nyquist no deben duplicarse.
    mag[0] *= 0.5
    if x.size % 2 == 0:
        mag[-1] *= 0.5

    fase = np.angle(X)

    return f, mag, fase


def inciso_c(fs=8000.0, N=1024):
    n = np.arange(N)
    df = fs / N

    k_exact = 128
    f_exact = k_exact * df
    f_off = (k_exact + 0.5) * df

    fase0 = 0.37
    x_exact = np.cos(2 * np.pi * f_exact * n / fs + fase0)
    x_off = np.cos(2 * np.pi * f_off * n / fs + fase0)

    ventanas = {
        "Rectangular": np.ones(N),
        "Hann": np.hanning(N),
    }
    senales = {
        f"Bin exacto: {f_exact:.3f} Hz": x_exact,
        f"Entre bins: {f_off:.5f} Hz": x_off,
    }

    # Magnitud
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)

    for fila, (nombre_senal, x) in enumerate(senales.items()):
        for col, (nombre_ventana, w) in enumerate(ventanas.items()):
            f, mag, _ = espectro_ventana(x, w, fs)
            mag_db = 20 * np.log10(np.maximum(mag / np.max(mag), 1e-12))

            ax = axes[fila, col]
            ax.plot(f, mag_db)
            ax.set_xlim(850, 1150)
            ax.set_ylim(-100, 5)
            ax.grid(True)
            ax.set_title(f"{nombre_senal}\n{nombre_ventana}")
            ax.set_xlabel("Frecuencia [Hz]")
            ax.set_ylabel("Magnitud normalizada [dB]")

    ruta_mag = FIGURAS / "2_1c_magnitud.png"
    fig.savefig(ruta_mag, dpi=160)
    plt.close(fig)

    # Fase
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)

    for fila, (nombre_senal, x) in enumerate(senales.items()):
        for col, (nombre_ventana, w) in enumerate(ventanas.items()):
            f, mag, fase = espectro_ventana(x, w, fs)
            mag_db = 20 * np.log10(np.maximum(mag / np.max(mag), 1e-12))

            mask = (f >= 850) & (f <= 1150) & (mag_db > -60)

            ax = axes[fila, col]
            ax.plot(f[mask], fase[mask], marker=".", linestyle="none")
            ax.set_xlim(850, 1150)
            ax.set_ylim(-np.pi, np.pi)
            ax.grid(True)
            ax.set_title(f"{nombre_senal}\n{nombre_ventana}")
            ax.set_xlabel("Frecuencia [Hz]")
            ax.set_ylabel("Fase [rad]")

    ruta_fase = FIGURAS / "2_1c_fase.png"
    fig.savefig(ruta_fase, dpi=160)
    plt.close(fig)

    print("\n" + "=" * 60)
    print("2.1(c) BIN EXACTO Y FUGA ESPECTRAL")
    print("=" * 60)
    print(f"fs = {fs:.1f} Hz")
    print(f"N = {N}")
    print(f"Δf = {df:.6f} Hz")
    print(f"Tono exacto: k = {k_exact}, f = {f_exact:.6f} Hz")
    print(f"Tono entre bins: k = {k_exact + 0.5}, f = {f_off:.6f} Hz")
    print(f"Figura magnitud: {ruta_mag}")
    print(f"Figura fase: {ruta_fase}")

    return {
        "fs_Hz": fs,
        "N": N,
        "df_Hz": df,
        "k_exacto": k_exact,
        "f_exacto_Hz": f_exact,
        "k_entre_bins": k_exact + 0.5,
        "f_entre_bins_Hz": f_off,
        "figura_magnitud": str(ruta_mag.relative_to(SECCION)),
        "figura_fase": str(ruta_fase.relative_to(SECCION)),
    }


def inciso_d(fs=8000.0, N=1024):
    n = np.arange(N)

    x = (
        np.cos(2 * np.pi * 1000 * n / fs)
        + 0.5 * np.cos(2 * np.pi * 625 * n / fs + 0.3)
        + 0.25 * np.cos(2 * np.pi * 1375 * n / fs - 0.5)
    )

    X = np.fft.fft(x)

    # Para k=1,...,N-1: X[k] debe coincidir con conj(X[N-k]).
    error_simetria = float(
        np.max(np.abs(X[1:] - np.conj(X[-1:0:-1])))
    )

    k_objetivo = int(round(1000 * N / fs))

    X_asim = X.copy()
    X_asim[k_objetivo] = 0
    x_asim = np.fft.ifft(X_asim)

    X_sim = X.copy()
    X_sim[k_objetivo] = 0
    X_sim[-k_objetivo] = 0
    x_sim = np.fft.ifft(X_sim)

    imag_asim = float(np.max(np.abs(np.imag(x_asim))))
    imag_sim = float(np.max(np.abs(np.imag(x_sim))))

    # Figura de simetría
    f = np.fft.fftshift(np.fft.fftfreq(N, d=1 / fs))
    X_shift = np.fft.fftshift(X)

    fig, ax = plt.subplots(figsize=(11, 5), constrained_layout=True)
    ax.plot(f, np.abs(X_shift))
    ax.set_xlim(-1600, 1600)
    ax.grid(True)
    ax.set_xlabel("Frecuencia [Hz]")
    ax.set_ylabel("|X[k]|")
    ax.set_title("DFT de una señal real: simetría en magnitud")
    ruta_sim = FIGURAS / "2_1d_simetria_conjugada.png"
    fig.savefig(ruta_sim, dpi=160)
    plt.close(fig)

    # Figura de partes imaginarias
    t = n / fs
    fig, ax = plt.subplots(figsize=(11, 5), constrained_layout=True)
    ax.plot(t[:160], np.imag(x_asim[:160]), label="Modificación asimétrica")
    ax.plot(t[:160], np.imag(x_sim[:160]), label="Modificación simétrica")
    ax.grid(True)
    ax.legend()
    ax.set_xlabel("Tiempo [s]")
    ax.set_ylabel("Parte imaginaria")
    ax.set_title("Efecto de preservar la simetría conjugada antes de la IFFT")
    ruta_ifft = FIGURAS / "2_1d_ifft_simetria.png"
    fig.savefig(ruta_ifft, dpi=160)
    plt.close(fig)

    print("\n" + "=" * 60)
    print("2.1(d) SIMETRÍA CONJUGADA")
    print("=" * 60)
    print(f"Error máximo X[N-k] - conj(X[k]) = {error_simetria:.6e}")
    print(f"Bin del tono de 1000 Hz = {k_objetivo}")
    print(f"Máx. parte imaginaria rompiendo simetría = {imag_asim:.6e}")
    print(f"Máx. parte imaginaria preservando simetría = {imag_sim:.6e}")
    print(f"Figura simetría: {ruta_sim}")
    print(f"Figura IFFT: {ruta_ifft}")

    return {
        "fs_Hz": fs,
        "N": N,
        "error_max_simetria": error_simetria,
        "k_objetivo_1000Hz": k_objetivo,
        "max_imag_modificacion_asimetrica": imag_asim,
        "max_imag_modificacion_simetrica": imag_sim,
        "figura_simetria": str(ruta_sim.relative_to(SECCION)),
        "figura_ifft": str(ruta_ifft.relative_to(SECCION)),
    }


def main():
    resultados = {
        "2_1a": inciso_a(),
        "2_1b": inciso_b(),
        "2_1c": inciso_c(),
        "2_1d": inciso_d(),
    }

    RESULTADOS_JSON.write_text(
        json.dumps(resultados, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("RESULTADOS 2.1 GENERADOS")
    print("=" * 60)
    print(f"JSON: {RESULTADOS_JSON}")


if __name__ == "__main__":
    main()
