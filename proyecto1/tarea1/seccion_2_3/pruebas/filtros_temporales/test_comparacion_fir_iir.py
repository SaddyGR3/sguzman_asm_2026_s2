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


def analizar_fir():
    fs = 8000.0

    b = np.array([0.2, 0.2, 0.2, 0.2, 0.2])
    a = np.array([1.0])

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

    print("FIR promedio móvil de orden 4")
    print("Magnitud en DC:", magnitud_db[0], "dB")
    print("Fase en DC:", fase[0], "rad")
    print("Retardo de grupo en DC:", retardo_grupo[0], "muestras")

    # La suma de coeficientes es 1 -> ganancia DC = 1 -> 0 dB
    assert np.isclose(magnitud_db[0], 0.0, atol=1e-12)

    # FIR simétrico de orden 4 -> retardo de grupo = 2 muestras
    assert np.isclose(retardo_grupo[0], 2.0, atol=1e-12)

    graficar_polos_ceros(
        b,
        a,
        titulo="FIR promedio móvil de orden 4"
    )

    graficar_respuesta_frecuencia(
        b,
        a,
        fs,
        titulo="FIR promedio móvil de orden 4"
    )

    plt.show()


if __name__ == "__main__":
    analizar_fir()
