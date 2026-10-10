"""
Implementación y análisis de filtros temporales FIR/IIR.

CE1110 - Tarea 1
Sección 2.3 - Filtrado temporal
"""

import numpy as np


def aplicar_filtro_manual(x, b, a):
    """
    Aplica un filtro digital mediante su ecuación de diferencias.

    La convención utilizada es:

        a[0] y[n] =
            sum(b[k] x[n-k])
            - sum(a[k] y[n-k]), para k >= 1

    Parámetros
    ----------
    x : array_like
        Señal de entrada.
    b : array_like
        Coeficientes del numerador.
    a : array_like
        Coeficientes del denominador.

    Retorna
    -------
    y : numpy.ndarray
        Señal de salida filtrada.
    """

    x = np.asarray(x, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64)

    if x.ndim != 1:
        raise ValueError("x debe ser un arreglo unidimensional.")

    if b.ndim != 1 or len(b) == 0:
        raise ValueError("b debe contener al menos un coeficiente.")

    if a.ndim != 1 or len(a) == 0:
        raise ValueError("a debe contener al menos un coeficiente.")

    if a[0] == 0:
        raise ValueError("a[0] no puede ser cero.")

    y = np.zeros(len(x), dtype=np.float64)

    for n in range(len(x)):

        # Contribución de la entrada
        suma_entrada = 0.0

        for k in range(len(b)):
            if n - k >= 0:
                suma_entrada += b[k] * x[n - k]

        # Contribución de salidas anteriores
        suma_salida = 0.0

        for k in range(1, len(a)):
            if n - k >= 0:
                suma_salida += a[k] * y[n - k]

        y[n] = (suma_entrada - suma_salida) / a[0]

    return y
