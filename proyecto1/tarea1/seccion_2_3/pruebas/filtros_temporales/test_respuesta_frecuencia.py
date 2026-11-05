import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from filtros_temporales import (
    analizar_respuesta_frecuencia,
    graficar_polos_ceros,
    graficar_respuesta_frecuencia,
)


def probar_respuesta():
    """
    Sistema de prueba:

        H(z) = 0.2 / (1 - 0.8 z^-1)

    En DC:

        H(1) = 0.2 / (1 - 0.8) = 1

    por lo que la magnitud debe ser 0 dB.
    """

    fs = 8000.0

    b = np.array([0.2])
    a = np.array([1.0, -0.8])

    (
        frecuencia,
        magnitud_db,
        fase,
        frecuencia_gd,
        retardo_grupo,
    ) = analizar_respuesta_frecuencia(
        b,
        a,
        fs
    )

    print("Frecuencia inicial:", frecuencia[0], "Hz")
    print("Magnitud en DC:", magnitud_db[0], "dB")
    print("Fase en DC:", fase[0], "rad")
    print("Retardo de grupo en DC:", retardo_grupo[0], "muestras")

    # H(1) = 1 -> 0 dB
    assert np.isclose(
        magnitud_db[0],
        0.0,
        atol=1e-12
    )

    # En DC la fase debe ser cero
    assert np.isclose(
        fase[0],
        0.0,
        atol=1e-12
    )

    assert np.all(np.isfinite(magnitud_db))
    assert np.all(np.isfinite(fase))
    assert np.all(np.isfinite(retardo_grupo))

    graficar_polos_ceros(
        b,
        a,
        titulo="IIR de primer orden"
    )

    graficar_respuesta_frecuencia(
        b,
        a,
        fs,
        titulo="IIR de primer orden"
    )

    print("Prueba de respuesta en frecuencia completada.")

    plt.show()


if __name__ == "__main__":
    probar_respuesta()
