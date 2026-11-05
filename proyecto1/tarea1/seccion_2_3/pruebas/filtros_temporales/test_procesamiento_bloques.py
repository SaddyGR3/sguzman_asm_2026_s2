import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from filtros_temporales import (
    aplicar_filtro_manual,
    aplicar_filtro_manual_bloque,
)


def filtrar_por_bloques(x, b, a, tamano_bloque):
    """
    Procesa una señal completa en bloques conservando
    el estado del filtro.
    """

    estado = None
    salidas = []

    for inicio in range(0, len(x), tamano_bloque):

        bloque = x[inicio:inicio + tamano_bloque]

        y_bloque, estado = aplicar_filtro_manual_bloque(
            bloque,
            b,
            a,
            estado
        )

        salidas.append(y_bloque)

    return np.concatenate(salidas)


def probar_filtro(nombre, b, a):

    rng = np.random.default_rng(2026)

    # Misma longitud utilizada en los casos de 2.2
    x = rng.normal(size=8192)

    # Referencia: procesamiento de toda la señal de una vez
    y_completa = aplicar_filtro_manual(
        x,
        b,
        a
    )

    tamanos = [
        256,
        512,
        1024,
        2048,
    ]

    print(f"\n{nombre}")

    for tamano in tamanos:

        y_bloques = filtrar_por_bloques(
            x,
            b,
            a,
            tamano
        )

        error_max = np.max(
            np.abs(y_completa - y_bloques)
        )

        print(
            f"Bloque {tamano:4d}: "
            f"error máximo = {error_max:.3e}"
        )

        assert error_max < 1e-12


def main():

    # FIR promedio móvil
    b_fir = np.array([
        0.2,
        0.2,
        0.2,
        0.2,
        0.2
    ])

    a_fir = np.array([1.0])

    probar_filtro(
        "FIR promedio móvil",
        b_fir,
        a_fir
    )

    # IIR estable de primer orden
    b_iir = np.array([0.2])
    a_iir = np.array([1.0, -0.8])

    probar_filtro(
        "IIR de primer orden",
        b_iir,
        a_iir
    )

    print(
        "\nTodas las pruebas por bloques pasaron correctamente."
    )


if __name__ == "__main__":
    main()
