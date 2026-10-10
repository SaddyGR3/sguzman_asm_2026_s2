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


def analizar_respuesta_frecuencia(b, a, fs, puntos=4096):
    """
    Calcula la respuesta en frecuencia de un filtro digital.

    Parámetros
    ----------
    b : array_like
        Coeficientes del numerador.
    a : array_like
        Coeficientes del denominador.
    fs : float
        Frecuencia de muestreo en Hz.
    puntos : int
        Cantidad de puntos utilizados para evaluar la respuesta.

    Retorna
    -------
    frecuencia : numpy.ndarray
        Frecuencias en Hz.
    magnitud_db : numpy.ndarray
        Magnitud de H(e^jw) en dB.
    fase : numpy.ndarray
        Fase desenrollada en radianes.
    frecuencia_gd : numpy.ndarray
        Frecuencias correspondientes al retardo de grupo.
    retardo_grupo : numpy.ndarray
        Retardo de grupo expresado en muestras.
    """

    from scipy.signal import freqz, group_delay

    b = np.asarray(b, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64)

    frecuencia, h = freqz(
        b,
        a,
        worN=puntos,
        fs=fs
    )

    magnitud = np.abs(h)

    # Evita log10(0)
    magnitud_db = 20.0 * np.log10(
        np.maximum(magnitud, np.finfo(np.float64).tiny)
    )

    fase = np.unwrap(np.angle(h))

    frecuencia_gd, retardo_grupo = group_delay(
        (b, a),
        w=puntos,
        fs=fs
    )

    return (
        frecuencia,
        magnitud_db,
        fase,
        frecuencia_gd,
        retardo_grupo,
    )


def graficar_polos_ceros(b, a, titulo="Diagrama de polos y ceros"):
    """
    Genera el diagrama de polos y ceros incluyendo el círculo unitario.

    Retorna
    -------
    fig, ax
        Objetos de Matplotlib para poder mostrar o guardar la figura.
    """

    import matplotlib.pyplot as plt

    ceros, polos = obtener_polos_ceros(b, a)

    fig, ax = plt.subplots(figsize=(6, 6))

    # Círculo unitario
    angulo = np.linspace(0.0, 2.0 * np.pi, 500)

    ax.plot(
        np.cos(angulo),
        np.sin(angulo),
        "--",
        label="Círculo unitario"
    )

    # Ejes real e imaginario
    ax.axhline(0.0, linewidth=0.8)
    ax.axvline(0.0, linewidth=0.8)

    if len(ceros) > 0:
        ax.plot(
            np.real(ceros),
            np.imag(ceros),
            "o",
            fillstyle="none",
            markersize=9,
            label="Ceros"
        )

    if len(polos) > 0:
        ax.plot(
            np.real(polos),
            np.imag(polos),
            "x",
            markersize=9,
            label="Polos"
        )

    valores = [1.0]

    if len(ceros) > 0:
        valores.extend(np.abs(ceros))

    if len(polos) > 0:
        valores.extend(np.abs(polos))

    limite = max(valores) + 0.25

    ax.set_xlim(-limite, limite)
    ax.set_ylim(-limite, limite)

    ax.set_aspect("equal", adjustable="box")

    ax.set_xlabel("Parte real")
    ax.set_ylabel("Parte imaginaria")
    ax.set_title(titulo)
    ax.grid(True)
    ax.legend()

    return fig, ax


def graficar_respuesta_frecuencia(
    b,
    a,
    fs,
    puntos=4096,
    titulo="Filtro digital"
):
    """
    Genera gráficas independientes de magnitud, fase y retardo de grupo.

    Retorna
    -------
    figuras : tuple
        Tupla con las tres figuras generadas.
    """

    import matplotlib.pyplot as plt

    (
        frecuencia,
        magnitud_db,
        fase,
        frecuencia_gd,
        retardo_grupo,
    ) = analizar_respuesta_frecuencia(
        b,
        a,
        fs,
        puntos
    )

    # Magnitud
    fig_mag, ax_mag = plt.subplots()

    ax_mag.plot(frecuencia, magnitud_db)
    ax_mag.set_xlabel("Frecuencia [Hz]")
    ax_mag.set_ylabel("Magnitud [dB]")
    ax_mag.set_title(f"{titulo} - Magnitud")
    ax_mag.grid(True)

    # Fase
    fig_fase, ax_fase = plt.subplots()

    ax_fase.plot(frecuencia, fase)
    ax_fase.set_xlabel("Frecuencia [Hz]")
    ax_fase.set_ylabel("Fase [rad]")
    ax_fase.set_title(f"{titulo} - Fase")
    ax_fase.grid(True)

    # Retardo de grupo
    fig_gd, ax_gd = plt.subplots()

    ax_gd.plot(frecuencia_gd, retardo_grupo)
    ax_gd.set_xlabel("Frecuencia [Hz]")
    ax_gd.set_ylabel("Retardo de grupo [muestras]")
    ax_gd.set_title(f"{titulo} - Retardo de grupo")
    ax_gd.grid(True)

    return fig_mag, fig_fase, fig_gd


def aplicar_filtro_manual_bloque(x, b, a, estado=None):
    """
    Aplica la ecuación de diferencias a un bloque de muestras
    conservando el estado entre llamadas.

    Parámetros
    ----------
    x : array_like
        Bloque de entrada.
    b : array_like
        Coeficientes del numerador.
    a : array_like
        Coeficientes del denominador.
    estado : dict o None
        Estado proveniente del bloque anterior.

        Contiene:
            "x_prev": muestras anteriores de entrada.
            "y_prev": muestras anteriores de salida.

        Si es None, se asume reposo inicial.

    Retorna
    -------
    y : numpy.ndarray
        Salida correspondiente al bloque.
    estado : dict
        Estado final que debe utilizarse en el siguiente bloque.
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

    memoria_x = len(b) - 1
    memoria_y = len(a) - 1

    if estado is None:
        x_prev = np.zeros(memoria_x, dtype=np.float64)
        y_prev = np.zeros(memoria_y, dtype=np.float64)
    else:
        x_prev = np.asarray(
            estado["x_prev"],
            dtype=np.float64
        ).copy()

        y_prev = np.asarray(
            estado["y_prev"],
            dtype=np.float64
        ).copy()

        if len(x_prev) != memoria_x:
            raise ValueError(
                "El estado de entrada no coincide con el filtro."
            )

        if len(y_prev) != memoria_y:
            raise ValueError(
                "El estado de salida no coincide con el filtro."
            )

    y = np.zeros(len(x), dtype=np.float64)

    for n, muestra in enumerate(x):

        suma_entrada = b[0] * muestra

        for k in range(1, len(b)):
            suma_entrada += b[k] * x_prev[k - 1]

        suma_salida = 0.0

        for k in range(1, len(a)):
            suma_salida += a[k] * y_prev[k - 1]

        salida = (suma_entrada - suma_salida) / a[0]

        y[n] = salida

        # Actualizar memorias: la posición 0 contiene
        # siempre la muestra más reciente.
        if memoria_x > 0:
            if memoria_x > 1:
                x_prev[1:] = x_prev[:-1].copy()

            x_prev[0] = muestra

        if memoria_y > 0:
            if memoria_y > 1:
                y_prev[1:] = y_prev[:-1].copy()

            y_prev[0] = salida

    estado_final = {
        "x_prev": x_prev,
        "y_prev": y_prev,
    }

    return y, estado_final
