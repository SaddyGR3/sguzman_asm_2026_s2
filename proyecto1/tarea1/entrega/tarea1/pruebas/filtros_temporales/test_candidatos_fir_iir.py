import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import freqz

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from filtros_temporales import (
    disenar_fir_kaiser,
    disenar_iir_butterworth,
    evaluar_especificaciones,
    verificar_estabilidad,
    graficar_polos_ceros,
    graficar_respuesta_frecuencia,
)


FS = 8000.0

FP = 1200.0
FSTOP = 1800.0

RIZADO_DB = 1.0
ATENUACION_DB = 40.0


def magnitud_en_frecuencia(b, a, frecuencia_objetivo):

    frecuencia, h = freqz(
        b,
        a,
        worN=65536,
        fs=FS
    )

    indice = np.argmin(
        np.abs(frecuencia - frecuencia_objetivo)
    )

    return 20.0 * np.log10(
        max(
            abs(h[indice]),
            np.finfo(np.float64).tiny
        )
    )


def imprimir_resultados(nombre, b, a, orden):

    medidas = evaluar_especificaciones(
        b,
        a,
        FS,
        FP,
        FSTOP
    )

    estable, radio, polos = verificar_estabilidad(
        b,
        a
    )

    print(f"\n{nombre}")
    print("-" * len(nombre))

    print("Orden:", orden)
    print("Número de coeficientes b:", len(b))
    print("Número de coeficientes a:", len(a))

    print(
        "Rizado banda de paso:",
        f"{medidas['rizado_paso_db']:.3f} dB"
    )

    print(
        "Pérdida máxima banda de paso:",
        f"{medidas['perdida_max_paso_db']:.3f} dB"
    )

    print(
        "Atenuación mínima banda de rechazo:",
        f"{medidas['atenuacion_rechazo_db']:.3f} dB"
    )

    print("Estable:", estable)
    print("Radio máximo de polos:", radio)

    for f in [300, 700, 1100, 2150]:

        ganancia = magnitud_en_frecuencia(
            b,
            a,
            f
        )

        print(
            f"Magnitud a {f:4d} Hz:",
            f"{ganancia:.3f} dB"
        )

    assert estable

    assert (
        medidas["perdida_max_paso_db"]
        <= RIZADO_DB + 0.1
    )

    assert (
        medidas["atenuacion_rechazo_db"]
        >= ATENUACION_DB
    )


def main():

    b_fir, a_fir, orden_fir = disenar_fir_kaiser(
        FS,
        FP,
        FSTOP,
        ATENUACION_DB
    )

    b_iir, a_iir, orden_iir = disenar_iir_butterworth(
        FS,
        FP,
        FSTOP,
        RIZADO_DB,
        ATENUACION_DB
    )

    imprimir_resultados(
        "Candidato FIR Kaiser",
        b_fir,
        a_fir,
        orden_fir
    )

    imprimir_resultados(
        "Candidato IIR Butterworth",
        b_iir,
        a_iir,
        orden_iir
    )

    graficar_polos_ceros(
        b_fir,
        a_fir,
        "Candidato FIR Kaiser"
    )

    graficar_respuesta_frecuencia(
        b_fir,
        a_fir,
        FS,
        titulo="Candidato FIR Kaiser"
    )

    graficar_polos_ceros(
        b_iir,
        a_iir,
        "Candidato IIR Butterworth"
    )

    graficar_respuesta_frecuencia(
        b_iir,
        a_iir,
        FS,
        titulo="Candidato IIR Butterworth"
    )

    print(
        "\nAmbos candidatos cumplen las "
        "especificaciones preliminares."
    )

    plt.show()


if __name__ == "__main__":
    main()
