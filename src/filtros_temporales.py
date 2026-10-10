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


def obtener_polos_ceros(b, a):
    """
    Obtiene los ceros y polos de un filtro digital descrito mediante
    coeficientes en potencias de z^-1.

    H(z) = B(z) / A(z)

    donde:

        B(z) = b[0] + b[1]z^-1 + ...
        A(z) = a[0] + a[1]z^-1 + ...

    Para obtener los polinomios en z se multiplica numerador y
    denominador por una potencia común de z.

    Parámetros
    ----------
    b : array_like
        Coeficientes del numerador.
    a : array_like
        Coeficientes del denominador.

    Retorna
    -------
    ceros : numpy.ndarray
        Ceros del sistema.
    polos : numpy.ndarray
        Polos del sistema.
    """

    b = np.asarray(b, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64)

    if b.ndim != 1 or len(b) == 0:
        raise ValueError("b debe contener al menos un coeficiente.")

    if a.ndim != 1 or len(a) == 0:
        raise ValueError("a debe contener al menos un coeficiente.")

    if a[0] == 0:
        raise ValueError("a[0] no puede ser cero.")

    orden_b = len(b) - 1
    orden_a = len(a) - 1

    orden = max(orden_b, orden_a)

    # Completar con ceros para expresar ambos polinomios
    # utilizando la misma potencia común de z.
    b_z = np.pad(b, (0, orden + 1 - len(b)))
    a_z = np.pad(a, (0, orden + 1 - len(a)))

    ceros = np.roots(b_z) if orden > 0 else np.array([])
    polos = np.roots(a_z) if orden > 0 else np.array([])

    return ceros, polos


def verificar_estabilidad(b, a, tolerancia=1e-12):
    """
    Verifica la estabilidad BIBO de un filtro causal racional.

    Para un sistema causal, todos los polos deben encontrarse
    estrictamente dentro del círculo unitario:

        |p_k| < 1

    Parámetros
    ----------
    b : array_like
        Coeficientes del numerador.
    a : array_like
        Coeficientes del denominador.
    tolerancia : float
        Margen numérico utilizado en la comparación.

    Retorna
    -------
    estable : bool
        True si todos los polos están dentro del círculo unitario.
    radio_maximo : float
        Magnitud del polo más alejado del origen.
    polos : numpy.ndarray
        Polos encontrados.
    """

    _, polos = obtener_polos_ceros(b, a)

    if len(polos) == 0:
        return True, 0.0, polos

    radio_maximo = np.max(np.abs(polos))

    estable = radio_maximo < (1.0 - tolerancia)

    return estable, radio_maximo, polos


def roc_causal(b, a):
    """
    Determina el radio interno de la región de convergencia causal.

    Para un sistema causal racional:

        ROC: |z| > max(|p_k|)

    Retorna
    -------
    radio : float
        Radio correspondiente al polo de mayor magnitud.
    """

    _, polos = obtener_polos_ceros(b, a)

    if len(polos) == 0:
        return 0.0

    return float(np.max(np.abs(polos)))
