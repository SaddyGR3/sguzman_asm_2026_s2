import sys
from pathlib import Path

import numpy as np
from scipy.signal import lfilter

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from filtros_temporales import (
    aplicar_filtro_manual,
    aplicar_filtro_manual_bloque,
    disenar_fir_kaiser,
    evaluar_especificaciones,
    verificar_estabilidad,
    roc_causal,
)


# ============================================================
# Diseño final 2.3
# ============================================================

FS = 8000.0

FP = 1200.0
FSTOP = 1800.0

RIZADO_DESEADO_DB = 1.0
ATENUACION_DESEADA_DB = 40.0

TAMANO_BLOQUE = 1024

TOLERANCIA = 1e-12


def cargar_caso(numero):

    ruta = (
        RAIZ
        / "seccion_2_2"
        / "2_2_generacionsenales"
        / "pruebas"
        / f"caso_{numero}"
        / "muestras_exactas.npz"
    )

    datos = np.load(ruta)

    return datos["contaminada"]


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

        salida, estado = aplicar_filtro_manual_bloque(
            bloque,
            b,
            a,
            estado
        )

        salidas.append(salida)

    return np.concatenate(salidas)


def main():

    # --------------------------------------------------------
    # Diseño
    # --------------------------------------------------------

    b, a, orden = disenar_fir_kaiser(
        FS,
        FP,
        FSTOP,
        ATENUACION_DESEADA_DB
    )

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

    roc = roc_causal(
        b,
        a
    )

    print("=" * 60)
    print(" FILTRO TEMPORAL FINAL - SECCIÓN 2.3")
    print("=" * 60)

    print("\nTipo: FIR pasa-bajas con ventana Kaiser")
    print(f"Orden: {orden}")
    print(f"Número de coeficientes: {len(b)}")

    print("\nEspecificaciones:")
    print(f"  fs = {FS:.1f} Hz")
    print(f"  fp = {FP:.1f} Hz")
    print(f"  fsb = {FSTOP:.1f} Hz")
    print(f"  Rp deseado <= {RIZADO_DESEADO_DB:.1f} dB")
    print(f"  As deseado >= {ATENUACION_DESEADA_DB:.1f} dB")

    print("\nRespuesta obtenida:")
    print(
        "  Rizado real = "
        f"{medidas['rizado_paso_db']:.6f} dB"
    )
    print(
        "  Pérdida máxima de paso = "
        f"{medidas['perdida_max_paso_db']:.6f} dB"
    )
    print(
        "  Atenuación mínima de rechazo = "
        f"{medidas['atenuacion_rechazo_db']:.6f} dB"
    )

    print("\nEstabilidad:")
    print(f"  Estable = {estable}")
    print(f"  Radio máximo de polos = {radio}")
    print(f"  ROC causal: |z| > {roc}")

    print("\nCoeficientes b[k]:")

    for k, coef in enumerate(b):
        print(
            f"  b[{k:2d}] = "
            f"{coef:.16e}"
        )

    print("\nCoeficientes a[k]:")

    for k, coef in enumerate(a):
        print(
            f"  a[{k:2d}] = "
            f"{coef:.16e}"
        )

    # --------------------------------------------------------
    # Validación manual vs biblioteca
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print(" VALIDACIÓN MANUAL CONTRA scipy.signal.lfilter")
    print("=" * 60)

    print(
        f"Tolerancia declarada: {TOLERANCIA:.1e}"
    )

    for caso in [1, 2, 3]:

        x = cargar_caso(caso)

        # Nuestra ecuación de diferencias
        y_manual = aplicar_filtro_manual(
            x,
            b,
            a
        )

        # Nuestra implementación real por bloques
        y_bloques = filtrar_por_bloques(
            x,
            b,
            a
        )

        # Biblioteca de referencia
        y_scipy = lfilter(
            b,
            a,
            x
        )

        error_manual = np.max(
            np.abs(
                y_manual
                -
                y_scipy
            )
        )

        error_bloques = np.max(
            np.abs(
                y_bloques
                -
                y_scipy
            )
        )

        print(f"\nCaso {caso}")

        print(
            "  Error máximo manual vs SciPy:  "
            f"{error_manual:.3e}"
        )

        print(
            "  Error máximo bloques vs SciPy: "
            f"{error_bloques:.3e}"
        )

        assert error_manual < TOLERANCIA
        assert error_bloques < TOLERANCIA

    print(
        "\nValidación completada correctamente."
    )


if __name__ == "__main__":
    main()
