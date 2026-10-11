import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from filtros_temporales import (
    obtener_polos_ceros,
    verificar_estabilidad,
    roc_causal,
)


def probar_iir_estable():
    """
    H(z) = 0.2 / (1 - 0.8 z^-1)

    Multiplicando por z:

        H(z) = 0.2 z / (z - 0.8)

    Por lo tanto:

        cero = 0
        polo = 0.8
    """

    b = np.array([0.2])
    a = np.array([1.0, -0.8])

    ceros, polos = obtener_polos_ceros(b, a)

    print("IIR estable")
    print("Ceros:", ceros)
    print("Polos:", polos)

    assert np.allclose(ceros, [0.0])
    assert np.allclose(polos, [0.8])

    estable, radio, _ = verificar_estabilidad(b, a)

    print("Radio máximo:", radio)
    print("Estable:", estable)
    print("ROC causal: |z| >", roc_causal(b, a))

    assert estable
    assert np.isclose(radio, 0.8)


def probar_iir_inestable():
    """
    H(z) = 1 / (1 - 1.1 z^-1)

    Tiene un polo en z = 1.1, fuera del círculo unitario.
    """

    b = np.array([1.0])
    a = np.array([1.0, -1.1])

    _, polos = obtener_polos_ceros(b, a)

    estable, radio, _ = verificar_estabilidad(b, a)

    print("\nIIR inestable")
    print("Polos:", polos)
    print("Radio máximo:", radio)
    print("Estable:", estable)

    assert np.allclose(polos, [1.1])
    assert not estable
    assert np.isclose(radio, 1.1)


def probar_fir():
    """
    FIR de promedio móvil de cinco muestras.

    Al expresarlo como función racional en z aparecen polos
    en el origen asociados a los retardos.
    """

    b = np.array([0.2, 0.2, 0.2, 0.2, 0.2])
    a = np.array([1.0])

    ceros, polos = obtener_polos_ceros(b, a)

    estable, radio, _ = verificar_estabilidad(b, a)

    print("\nFIR")
    print("Ceros:", ceros)
    print("Polos:", polos)
    print("Radio máximo:", radio)
    print("Estable:", estable)

    assert len(polos) == 4
    assert np.allclose(polos, 0.0)
    assert estable
    assert np.isclose(radio, 0.0)


if __name__ == "__main__":
    probar_iir_estable()
    probar_iir_inestable()
    probar_fir()

    print("\nTodas las pruebas de polos y estabilidad pasaron.")
