import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from filtros_temporales import (
    disenar_fir_kaiser,
    evaluar_especificaciones,
)


FS = 8000.0
FP = 1200.0
FSTOP = 1800.0
ATENUACION_DB = 40.0


def cuantizar_q15(coeficientes):
    """
    Cuantiza coeficientes reales al formato Q15.

    Q15 representa aproximadamente el intervalo:
        [-1, 1)

    con resolución:
        2^-15
    """

    escala = 2 ** 15

    enteros = np.round(
        coeficientes * escala
    ).astype(np.int16)

    reconstruidos = (
        enteros.astype(np.float64)
        /
        escala
    )

    return enteros, reconstruidos


def imprimir_especificaciones(nombre, b):

    medidas = evaluar_especificaciones(
        b,
        np.array([1.0]),
        FS,
        FP,
        FSTOP
    )

    print(f"\n{nombre}")

    print(
        "  Rizado banda de paso: "
        f"{medidas['rizado_paso_db']:.6f} dB"
    )

    print(
        "  Pérdida máxima banda de paso: "
        f"{medidas['perdida_max_paso_db']:.6f} dB"
    )

    print(
        "  Atenuación mínima rechazo: "
        f"{medidas['atenuacion_rechazo_db']:.6f} dB"
    )


def main():

    b, a, orden = disenar_fir_kaiser(
        FS,
        FP,
        FSTOP,
        ATENUACION_DB
    )

    print("=" * 60)
    print(" CUANTIZACIÓN, SATURACIÓN Y MEMORIA - FIR FINAL")
    print("=" * 60)

    print(f"\nOrden: {orden}")
    print(f"Número de coeficientes: {len(b)}")

    # ========================================================
    # 1. CUANTIZACIÓN FLOAT32
    # ========================================================

    b_float32 = (
        b.astype(np.float32)
        .astype(np.float64)
    )

    error_float32 = np.max(
        np.abs(
            b
            -
            b_float32
        )
    )

    print("\n" + "=" * 60)
    print(" CUANTIZACIÓN FLOAT32")
    print("=" * 60)

    print(
        "Error máximo de coeficiente: "
        f"{error_float32:.6e}"
    )

    imprimir_especificaciones(
        "Respuesta con coeficientes float32",
        b_float32
    )

    # ========================================================
    # 2. CUANTIZACIÓN Q15
    # ========================================================

    b_q15_int, b_q15 = cuantizar_q15(
        b
    )

    error_q15 = np.max(
        np.abs(
            b
            -
            b_q15
        )
    )

    print("\n" + "=" * 60)
    print(" CUANTIZACIÓN Q15")
    print("=" * 60)

    print(
        "Resolución Q15: "
        f"{2 ** -15:.6e}"
    )

    print(
        "Error máximo de coeficiente: "
        f"{error_q15:.6e}"
    )

    imprimir_especificaciones(
        "Respuesta con coeficientes Q15",
        b_q15
    )

    print("\nCoeficientes Q15 enteros:")

    for k, valor in enumerate(
        b_q15_int
    ):
        print(
            f"  b_q15[{k:2d}] = "
            f"{int(valor)}"
        )

    # ========================================================
    # 3. SATURACIÓN
    # ========================================================

    norma_l1 = float(
        np.sum(
            np.abs(b)
        )
    )

    norma_l1_q15 = float(
        np.sum(
            np.abs(b_q15)
        )
    )

    print("\n" + "=" * 60)
    print(" ANÁLISIS DE SATURACIÓN")
    print("=" * 60)

    print(
        "Suma de |b[k]| original: "
        f"{norma_l1:.6f}"
    )

    print(
        "Suma de |b[k]| Q15: "
        f"{norma_l1_q15:.6f}"
    )

    print(
        "\nCota teórica:"
    )

    print(
        "  |y[n]| <= sum(|b[k]|) * max(|x[n]|)"
    )

    print(
        "\nSi |x[n]| <= 1:"
    )

    print(
        "  |y[n]| máximo teórico <= "
        f"{norma_l1:.6f}"
    )

    escala_segura = (
        1.0
        /
        norma_l1
    )

    print(
        "\nEscalamiento máximo para garantizar "
        "que |y[n]| <= 1:"
    )

    print(
        f"  {escala_segura:.6f}"
    )

    # --------------------------------------------------------
    # Acumulador Q15
    # --------------------------------------------------------

    suma_abs_q15 = int(
        np.sum(
            np.abs(
                b_q15_int.astype(
                    np.int64
                )
            )
        )
    )

    entrada_max_q15 = 32768

    acumulador_maximo = (
        suma_abs_q15
        *
        entrada_max_q15
    )

    limite_int32 = (
        2 ** 31 - 1
    )

    print(
        "\nPeor caso aproximado del acumulador Q15:"
    )

    print(
        f"  Suma absoluta coeficientes enteros = "
        f"{suma_abs_q15}"
    )

    print(
        f"  Acumulador máximo = "
        f"{acumulador_maximo}"
    )

    print(
        f"  Límite int32 = "
        f"{limite_int32}"
    )

    print(
        "  Cabe en int32 = "
        f"{acumulador_maximo <= limite_int32}"
    )

    # ========================================================
    # 4. MEMORIA
    # ========================================================

    num_coef = len(b)

    # FIR de orden 36 necesita 36 muestras anteriores.
    num_estado = orden

    memoria_float64 = (
        num_coef
        +
        num_estado
    ) * 8

    memoria_float32 = (
        num_coef
        +
        num_estado
    ) * 4

    memoria_q15 = (
        num_coef
        +
        num_estado
    ) * 2

    print("\n" + "=" * 60)
    print(" MEMORIA DEL FILTRO")
    print("=" * 60)

    print(
        f"Coeficientes almacenados: {num_coef}"
    )

    print(
        f"Muestras de estado:       {num_estado}"
    )

    print(
        "\nMemoria coeficientes + estado:"
    )

    print(
        f"  float64: {memoria_float64} bytes"
    )

    print(
        f"  float32: {memoria_float32} bytes"
    )

    print(
        f"  Q15:     {memoria_q15} bytes"
    )


if __name__ == "__main__":
    main()
