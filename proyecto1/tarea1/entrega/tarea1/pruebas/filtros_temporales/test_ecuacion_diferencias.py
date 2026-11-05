import sys
from pathlib import Path

import numpy as np
from scipy.signal import lfilter


# Permite importar src/filtros_temporales.py desde la raíz del repositorio
RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from filtros_temporales import aplicar_filtro_manual


def probar_fir():
    """
    Prueba FIR sencilla: promedio móvil de 5 muestras.
    """

    rng = np.random.default_rng(1234)
    x = rng.normal(size=1000)

    b = np.array([0.2, 0.2, 0.2, 0.2, 0.2])
    a = np.array([1.0])

    y_manual = aplicar_filtro_manual(x, b, a)
    y_scipy = lfilter(b, a, x)

    error_max = np.max(np.abs(y_manual - y_scipy))

    print(f"Error máximo FIR: {error_max:.3e}")

    assert error_max < 1e-12


def probar_iir():
    """
    Prueba IIR causal y estable de primer orden.

    H(z) = 0.2 / (1 - 0.8 z^-1)

    y[n] = 0.2 x[n] + 0.8 y[n-1]
    """

    rng = np.random.default_rng(5678)
    x = rng.normal(size=1000)

    b = np.array([0.2])
    a = np.array([1.0, -0.8])

    y_manual = aplicar_filtro_manual(x, b, a)
    y_scipy = lfilter(b, a, x)

    error_max = np.max(np.abs(y_manual - y_scipy))

    print(f"Error máximo IIR: {error_max:.3e}")

    assert error_max < 1e-12


if __name__ == "__main__":
    probar_fir()
    probar_iir()

    print("Todas las pruebas pasaron correctamente.")
