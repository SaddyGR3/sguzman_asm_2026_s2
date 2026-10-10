import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from filtros_temporales import (
    disenar_fir_kaiser,
    disenar_iir_butterworth,
    aplicar_filtro_manual_bloque,
)


FS = 8000.0
TAMANO_BLOQUE = 1024

FP = 1200.0
FSTOP = 1800.0

RIZADO_DB = 1.0
ATENUACION_DB = 40.0


def filtrar_por_bloques(x, b, a):

    estado = None
    salidas = []

    for inicio in range(
        0,
        len(x),
        TAMANO_BLOQUE
    ):

        bloque = x[
            inicio:
            inicio + TAMANO_BLOQUE
        ]

        y_bloque, estado = aplicar_filtro_manual_bloque(
            bloque,
            b,
            a,
            estado
        )

        salidas.append(
            y_bloque
        )

    return np.concatenate(
        salidas
    )


def calcular_mse(
    referencia,
    estimada
):

    return np.mean(
        (
            referencia
            -
            estimada
        ) ** 2
    )


def calcular_snr(
    referencia,
    estimada
):

    error = (
        referencia
        -
        estimada
    )

    energia_senal = np.sum(
        referencia ** 2
    )

    energia_error = np.sum(
        error ** 2
    )

    if energia_error == 0:
        return np.inf

    return 10.0 * np.log10(
        energia_senal
        /
        energia_error
    )


def estimar_retardo(
    referencia,
    estimada,
    max_retardo=200
):

    mejor_retardo = 0
    mejor_correlacion = -np.inf

    for retardo in range(
        max_retardo + 1
    ):

        if retardo == 0:

            ref = referencia
            est = estimada

        else:

            ref = referencia[
                :-retardo
            ]

            est = estimada[
                retardo:
            ]

        correlacion = np.dot(
            ref,
            est
        )

        if correlacion > mejor_correlacion:

            mejor_correlacion = correlacion
            mejor_retardo = retardo

    return mejor_retardo


def alinear_senales(
    referencia,
    estimada,
    retardo
):

    if retardo == 0:

        return (
            referencia,
            estimada
        )

    return (
        referencia[:-retardo],
        estimada[retardo:]
    )


def evaluar_filtro(
    nombre,
    limpia,
    contaminada,
    b,
    a
):

    salida = filtrar_por_bloques(
        contaminada,
        b,
        a
    )

    snr_entrada = calcular_snr(
        limpia,
        contaminada
    )

    snr_salida_sin_alinear = calcular_snr(
        limpia,
        salida
    )

    mse_sin_alinear = calcular_mse(
        limpia,
        salida
    )

    retardo = estimar_retardo(
        limpia,
        salida
    )

    (
        limpia_alineada,
        salida_alineada
    ) = alinear_senales(
        limpia,
        salida,
        retardo
    )

    snr_salida = calcular_snr(
        limpia_alineada,
        salida_alineada
    )

    mse = calcular_mse(
        limpia_alineada,
        salida_alineada
    )

    delta_snr = (
        snr_salida
        -
        snr_entrada
    )

    print(
        f"\n  {nombre}"
    )

    print(
        f"    Retardo estimado: "
        f"{retardo} muestras"
    )

    print(
        f"    SNR entrada:      "
        f"{snr_entrada:8.3f} dB"
    )

    print(
        f"    SNR salida:       "
        f"{snr_salida:8.3f} dB"
    )

    print(
        f"    Delta SNR:        "
        f"{delta_snr:8.3f} dB"
    )

    print(
        f"    MSE alineado:     "
        f"{mse:.6e}"
    )

    print(
        f"    SNR sin alinear:  "
        f"{snr_salida_sin_alinear:8.3f} dB"
    )

    print(
        f"    MSE sin alinear:  "
        f"{mse_sin_alinear:.6e}"
    )

    return {
        "salida": salida,
        "retardo": retardo,
        "snr_entrada": snr_entrada,
        "snr_salida": snr_salida,
        "delta_snr": delta_snr,
        "mse": mse,
        "snr_salida_sin_alinear": (
            snr_salida_sin_alinear
        ),
        "mse_sin_alinear": (
            mse_sin_alinear
        ),
    }


def cargar_caso(numero):

    ruta = (
        RAIZ
        / "seccion_2_2"
        / "2_2_generacionsenales"
        / "pruebas"
        / f"caso_{numero}"
        / "muestras_exactas.npz"
    )

    if not ruta.exists():

        raise FileNotFoundError(
            "\nNo se encontró:\n"
            f"{ruta}\n\n"
            "Verifique que "
            "'2_2_generacionsenales' "
            "esté en la raíz del repositorio."
        )

    datos = np.load(
        ruta
    )

    return (
        datos["limpia"],
        datos["ruido"],
        datos["contaminada"],
    )


def main():

    (
        b_fir,
        a_fir,
        orden_fir
    ) = disenar_fir_kaiser(
        FS,
        FP,
        FSTOP,
        ATENUACION_DB
    )

    (
        b_iir,
        a_iir,
        orden_iir
    ) = disenar_iir_butterworth(
        FS,
        FP,
        FSTOP,
        RIZADO_DB,
        ATENUACION_DB
    )

    print(
        "========================================"
    )

    print(
        " EVALUACIÓN DE CANDIDATOS FIR / IIR"
    )

    print(
        "========================================"
    )

    print(
        f"FIR Kaiser: orden {orden_fir}"
    )

    print(
        f"IIR Butterworth: orden {orden_iir}"
    )

    for caso in [1, 2, 3]:

        (
            limpia,
            ruido,
            contaminada
        ) = cargar_caso(
            caso
        )

        print(
            "\n========================================"
        )

        print(
            f" CASO {caso}"
        )

        print(
            "========================================"
        )

        evaluar_filtro(
            "FIR Kaiser",
            limpia,
            contaminada,
            b_fir,
            a_fir
        )

        evaluar_filtro(
            "IIR Butterworth",
            limpia,
            contaminada,
            b_iir,
            a_iir
        )


if __name__ == "__main__":
    main()
