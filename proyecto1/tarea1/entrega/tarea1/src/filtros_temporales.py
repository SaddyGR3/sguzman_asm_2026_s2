"""
Implementación y análisis de filtros temporales FIR/IIR.

CE1110 - Tarea 1
Sección 2.3 - Filtrado temporal
"""

import warnings

import numpy as np


# ============================================================
# ECUACIÓN DE DIFERENCIAS
# ============================================================

def aplicar_filtro_manual(x, b, a):
    """
    Aplica un filtro digital mediante su ecuación de diferencias.

    Convención:

        a[0] y[n] =
            sum(b[k] x[n-k])
            - sum(a[k] y[n-k]), para k >= 1

    Se asumen condiciones iniciales nulas.
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

        suma_entrada = 0.0

        for k in range(len(b)):
            if n - k >= 0:
                suma_entrada += b[k] * x[n - k]

        suma_salida = 0.0

        for k in range(1, len(a)):
            if n - k >= 0:
                suma_salida += a[k] * y[n - k]

        y[n] = (
            suma_entrada - suma_salida
        ) / a[0]

    return y


# ============================================================
# POLOS, CEROS, ROC Y ESTABILIDAD
# ============================================================

def obtener_polos_ceros(b, a):
    """
    Obtiene ceros y polos del sistema descrito por:

        H(z) = B(z) / A(z)

    Los coeficientes de entrada están expresados originalmente
    en potencias de z^-1.
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

    orden = max(
        orden_b,
        orden_a
    )

    b_z = np.pad(
        b,
        (0, orden + 1 - len(b))
    )

    a_z = np.pad(
        a,
        (0, orden + 1 - len(a))
    )

    if orden == 0:
        ceros = np.array([])
        polos = np.array([])
    else:
        ceros = np.roots(b_z)
        polos = np.roots(a_z)

    return ceros, polos


def verificar_estabilidad(
    b,
    a,
    tolerancia=1e-12
):
    """
    Verifica estabilidad BIBO para un sistema causal racional.

    Para estabilidad causal todos los polos deben cumplir:

        |p_k| < 1
    """

    _, polos = obtener_polos_ceros(
        b,
        a
    )

    if len(polos) == 0:
        return True, 0.0, polos

    radio_maximo = float(
        np.max(
            np.abs(polos)
        )
    )

    estable = (
        radio_maximo
        <
        1.0 - tolerancia
    )

    return (
        estable,
        radio_maximo,
        polos
    )


def roc_causal(b, a):
    """
    Devuelve el radio interno de la ROC causal.

    Para un sistema causal racional:

        ROC: |z| > max(|p_k|)
    """

    _, polos = obtener_polos_ceros(
        b,
        a
    )

    if len(polos) == 0:
        return 0.0

    return float(
        np.max(
            np.abs(polos)
        )
    )


# ============================================================
# RESPUESTA EN FRECUENCIA
# ============================================================

def analizar_respuesta_frecuencia(
    b,
    a,
    fs,
    puntos=4096
):
    """
    Calcula magnitud, fase y retardo de grupo.

    Retorna
    -------
    frecuencia
        Frecuencia en Hz.
    magnitud_db
        Magnitud en dB.
    fase
        Fase desenrollada en radianes.
    frecuencia_gd
        Frecuencias del retardo de grupo.
    retardo_grupo
        Retardo de grupo en muestras.
    """

    from scipy.signal import (
        freqz,
        group_delay,
    )

    b = np.asarray(
        b,
        dtype=np.float64
    )

    a = np.asarray(
        a,
        dtype=np.float64
    )

    frecuencia, h = freqz(
        b,
        a,
        worN=puntos,
        fs=fs
    )

    magnitud = np.abs(h)

    magnitud_db = (
        20.0
        *
        np.log10(
            np.maximum(
                magnitud,
                np.finfo(np.float64).tiny
            )
        )
    )

    fase = np.unwrap(
        np.angle(h)
    )

    # El retardo de grupo puede estar mal condicionado
    # donde la magnitud del filtro es prácticamente cero.
    with warnings.catch_warnings():

        warnings.simplefilter(
            "ignore",
            UserWarning
        )

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


# ============================================================
# GRÁFICAS
# ============================================================

def graficar_polos_ceros(
    b,
    a,
    titulo="Diagrama de polos y ceros"
):
    """
    Genera el diagrama de polos y ceros junto al círculo unitario.
    """

    import matplotlib.pyplot as plt

    ceros, polos = obtener_polos_ceros(
        b,
        a
    )

    fig, ax = plt.subplots(
        figsize=(6, 6)
    )

    angulo = np.linspace(
        0.0,
        2.0 * np.pi,
        500
    )

    ax.plot(
        np.cos(angulo),
        np.sin(angulo),
        "--",
        label="Círculo unitario"
    )

    ax.axhline(
        0.0,
        linewidth=0.8
    )

    ax.axvline(
        0.0,
        linewidth=0.8
    )

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
        valores.extend(
            np.abs(ceros)
        )

    if len(polos) > 0:
        valores.extend(
            np.abs(polos)
        )

    limite = (
        max(valores)
        + 0.25
    )

    ax.set_xlim(
        -limite,
        limite
    )

    ax.set_ylim(
        -limite,
        limite
    )

    ax.set_aspect(
        "equal",
        adjustable="box"
    )

    ax.set_xlabel(
        "Parte real"
    )

    ax.set_ylabel(
        "Parte imaginaria"
    )

    ax.set_title(
        titulo
    )

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
    Genera gráficas de magnitud, fase y retardo de grupo.

    El retardo de grupo se oculta donde la magnitud es menor
    que -80 dB, porque en esas regiones la fase deja de tener
    interpretación práctica.
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

    ax_mag.plot(
        frecuencia,
        magnitud_db
    )

    ax_mag.set_xlabel(
        "Frecuencia [Hz]"
    )

    ax_mag.set_ylabel(
        "Magnitud [dB]"
    )

    ax_mag.set_title(
        f"{titulo} - Magnitud"
    )

    ax_mag.grid(True)

    # Fase
    fig_fase, ax_fase = plt.subplots()

    ax_fase.plot(
        frecuencia,
        fase
    )

    ax_fase.set_xlabel(
        "Frecuencia [Hz]"
    )

    ax_fase.set_ylabel(
        "Fase [rad]"
    )

    ax_fase.set_title(
        f"{titulo} - Fase"
    )

    ax_fase.grid(True)

    # Retardo de grupo
    magnitud_gd = np.interp(
        frecuencia_gd,
        frecuencia,
        magnitud_db
    )

    retardo_visible = (
        retardo_grupo.copy()
    )

    retardo_visible[
        magnitud_gd < -80.0
    ] = np.nan

    fig_gd, ax_gd = plt.subplots()

    ax_gd.plot(
        frecuencia_gd,
        retardo_visible
    )

    ax_gd.set_xlabel(
        "Frecuencia [Hz]"
    )

    ax_gd.set_ylabel(
        "Retardo de grupo [muestras]"
    )

    ax_gd.set_title(
        f"{titulo} - Retardo de grupo"
    )

    ax_gd.grid(True)

    return (
        fig_mag,
        fig_fase,
        fig_gd
    )


# ============================================================
# PROCESAMIENTO POR BLOQUES
# ============================================================

def aplicar_filtro_manual_bloque(
    x,
    b,
    a,
    estado=None
):
    """
    Aplica la ecuación de diferencias a un bloque conservando
    el estado necesario para el siguiente bloque.

    Estado:
        x_prev : entradas anteriores.
        y_prev : salidas anteriores.
    """

    x = np.asarray(
        x,
        dtype=np.float64
    )

    b = np.asarray(
        b,
        dtype=np.float64
    )

    a = np.asarray(
        a,
        dtype=np.float64
    )

    if x.ndim != 1:
        raise ValueError(
            "x debe ser un arreglo unidimensional."
        )

    if b.ndim != 1 or len(b) == 0:
        raise ValueError(
            "b debe contener al menos un coeficiente."
        )

    if a.ndim != 1 or len(a) == 0:
        raise ValueError(
            "a debe contener al menos un coeficiente."
        )

    if a[0] == 0:
        raise ValueError(
            "a[0] no puede ser cero."
        )

    memoria_x = len(b) - 1
    memoria_y = len(a) - 1

    if estado is None:

        x_prev = np.zeros(
            memoria_x,
            dtype=np.float64
        )

        y_prev = np.zeros(
            memoria_y,
            dtype=np.float64
        )

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

    y = np.zeros(
        len(x),
        dtype=np.float64
    )

    for n, muestra in enumerate(x):

        suma_entrada = (
            b[0]
            *
            muestra
        )

        for k in range(
            1,
            len(b)
        ):

            suma_entrada += (
                b[k]
                *
                x_prev[k - 1]
            )

        suma_salida = 0.0

        for k in range(
            1,
            len(a)
        ):

            suma_salida += (
                a[k]
                *
                y_prev[k - 1]
            )

        salida = (
            suma_entrada
            -
            suma_salida
        ) / a[0]

        y[n] = salida

        if memoria_x > 0:

            if memoria_x > 1:
                x_prev[1:] = (
                    x_prev[:-1].copy()
                )

            x_prev[0] = muestra

        if memoria_y > 0:

            if memoria_y > 1:
                y_prev[1:] = (
                    y_prev[:-1].copy()
                )

            y_prev[0] = salida

    estado_final = {
        "x_prev": x_prev,
        "y_prev": y_prev,
    }

    return (
        y,
        estado_final
    )


# ============================================================
# DISEÑO DE CANDIDATOS
# ============================================================

def disenar_fir_kaiser(
    fs,
    frecuencia_paso,
    frecuencia_rechazo,
    atenuacion_db=40.0,
    margen_db=5.0
):
    """
    Diseña un FIR pasa bajas mediante ventana Kaiser.
    """

    from scipy.signal import (
        firwin,
        kaiserord,
    )

    if not (
        0
        <
        frecuencia_paso
        <
        frecuencia_rechazo
        <
        fs / 2
    ):
        raise ValueError(
            "Las frecuencias de diseño no son válidas."
        )

    ancho_transicion = (
        frecuencia_rechazo
        -
        frecuencia_paso
    ) / (fs / 2)

    num_taps, beta = kaiserord(
        atenuacion_db + margen_db,
        ancho_transicion
    )

    # FIR tipo I: número impar de coeficientes.
    if num_taps % 2 == 0:
        num_taps += 1

    frecuencia_corte = (
        frecuencia_paso
        +
        frecuencia_rechazo
    ) / 2

    b = firwin(
        num_taps,
        cutoff=frecuencia_corte,
        window=("kaiser", beta),
        fs=fs,
        pass_zero="lowpass"
    )

    a = np.array(
        [1.0]
    )

    orden = (
        num_taps - 1
    )

    return (
        b,
        a,
        orden
    )


def disenar_iir_butterworth(
    fs,
    frecuencia_paso,
    frecuencia_rechazo,
    rizado_db=1.0,
    atenuacion_db=40.0
):
    """
    Diseña un IIR Butterworth pasa bajas.
    """

    from scipy.signal import (
        buttord,
        butter,
    )

    if not (
        0
        <
        frecuencia_paso
        <
        frecuencia_rechazo
        <
        fs / 2
    ):
        raise ValueError(
            "Las frecuencias de diseño no son válidas."
        )

    (
        orden,
        frecuencia_natural
    ) = buttord(
        frecuencia_paso,
        frecuencia_rechazo,
        rizado_db,
        atenuacion_db,
        fs=fs
    )

    b, a = butter(
        orden,
        frecuencia_natural,
        btype="low",
        fs=fs
    )

    return (
        b,
        a,
        orden
    )


# ============================================================
# EVALUACIÓN DE ESPECIFICACIONES
# ============================================================

def evaluar_especificaciones(
    b,
    a,
    fs,
    frecuencia_paso,
    frecuencia_rechazo,
    puntos=65536
):
    """
    Mide el comportamiento real del filtro diseñado.
    """

    from scipy.signal import freqz

    frecuencia, h = freqz(
        b,
        a,
        worN=puntos,
        fs=fs
    )

    magnitud_db = (
        20.0
        *
        np.log10(
            np.maximum(
                np.abs(h),
                np.finfo(np.float64).tiny
            )
        )
    )

    banda_paso = (
        frecuencia
        <=
        frecuencia_paso
    )

    banda_rechazo = (
        frecuencia
        >=
        frecuencia_rechazo
    )

    max_paso = np.max(
        magnitud_db[banda_paso]
    )

    min_paso = np.min(
        magnitud_db[banda_paso]
    )

    rizado_db = (
        max_paso
        -
        min_paso
    )

    perdida_paso_db = (
        -min_paso
    )

    atenuacion_rechazo_db = (
        -np.max(
            magnitud_db[
                banda_rechazo
            ]
        )
    )

    return {
        "rizado_paso_db": float(
            rizado_db
        ),
        "perdida_max_paso_db": float(
            perdida_paso_db
        ),
        "atenuacion_rechazo_db": float(
            atenuacion_rechazo_db
        ),
    }