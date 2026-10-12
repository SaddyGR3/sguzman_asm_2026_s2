"""Tarea 1, apartado 2.4: reduccion de ruido por bloques FFT/IFFT.

Cadena: quitar DC -> bloques -> ventana -> rFFT -> ganancia real por bin ->
irFFT -> ventana -> suma con solapamiento -> restaurar DC.

La ventana sqrt(Hann) periodica se aplica dos veces. Con salto N/2, el
producto de las ventanas es Hann periodica y las contribuciones suman uno
(condicion COLA). Esto permite reconstruir la entrada cuando G = 1.

Metodos disponibles:
* ``picos`` detecta maximos locales respecto al piso espectral de la propia
  entrada y atenúa un vecindario configurable. No contiene una lista de bins
  o una frecuencia interferente codificada.
* ``resta`` estima el piso por bin y calcula G = clip(1-alpha*piso/|X|).
  Puede proteger tonos estables detectados en la entrada contaminada.
* ``top_k`` conserva los K bins mas fuertes de cada bloque; se incluye como
  punto de comparacion, no como metodo elegido para los tres casos.

Solo se procesan los bins no negativos con rFFT. Como G es real, la mitad
negativa conserva la simetria conjugada y la irFFT devuelve una señal real.
La mediana temporal y el promedio de DC usan la captura completa: esta
implementacion sirve para evaluar la Tarea 1 fuera de linea.
"""
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

# ----------------------------------------------------------------------------
# Utilidades basicas
# ----------------------------------------------------------------------------

def es_potencia_de_dos(n: int) -> bool:
    """Comprueba el requisito de tamaño de bloque de la Tarea 1."""
    return n > 0 and (n & (n - 1)) == 0


def ventana_sqrt_hann(N: int) -> np.ndarray:
    """Ventana de analisis y sintesis; w[n]^2 + w[n+N/2]^2 = 1."""
    n = np.arange(N)
    return np.sqrt(0.5 * (1.0 - np.cos(2.0 * np.pi * n / N)))


def _trocear(x: np.ndarray, N: int, hop: int):
    """Devuelve bloques, muestras de relleno inicial y longitud extendida.

    Se añade un bloque parcial antes del primer dato. Asi, la primera muestra
    no cae en el cero inicial de la ventana y tambien recibe la suma COLA.
    El relleno final permite reconstruir las ultimas muestras de la misma
    manera. Al terminar se descartan ambos extremos artificiales.
    """
    pre = N - hop
    n_bloques = int(np.ceil((len(x) + pre) / hop))
    total = (n_bloques - 1) * hop + N
    xp = np.zeros(total)
    xp[pre:pre + len(x)] = x
    idx = np.arange(N)[None, :] + hop * np.arange(n_bloques)[:, None]
    return xp[idx], pre, total


# ----------------------------------------------------------------------------
# Calculo de ganancias espectrales (reales, una por bin de rfft)
# ----------------------------------------------------------------------------

def estimar_piso_ruido(mag: np.ndarray, ancho_suavizado: int = 31) -> np.ndarray:
    """Estima un piso espectral robusto usando solo la entrada contaminada.

    ``mag`` tiene forma (bloques, bins de rFFT). Primero se toma la mediana
    entre bloques en cada frecuencia; despues se toma la mediana de un entorno
    impar de bins. Los picos estrechos dejan de dominar el piso local.
    Los extremos se reflejan para no crear un piso artificialmente bajo en
    DC y Nyquist. Se devuelve un vector de longitud N/2+1.

    El resultado usa todos los bloques; no es una estimacion en tiempo real.
    """
    mag = np.asarray(mag, dtype=float)
    if mag.ndim != 2 or mag.shape[0] == 0:
        raise ValueError("mag debe tener forma (bloques, bins) y no estar vacia")
    if ancho_suavizado < 1:
        raise ValueError("ancho_suavizado debe ser positivo")
    if ancho_suavizado % 2 == 0:
        # La mediana debe tener un bin central bien definido.
        ancho_suavizado += 1
    piso = np.median(mag, axis=0)
    radio = ancho_suavizado // 2
    extendido = np.pad(piso, radio, mode="reflect")
    return np.median(sliding_window_view(extendido, ancho_suavizado), axis=1)


def ganancias_picos(mag, fs, N, umbral=6.0, ancho_bins=2, atenuacion_db=60.0,
                    banda_util=None, ancho_suavizado=31):
    """Calcula la matriz de ganancias para interferencias tonales aisladas.

    Por cada bloque se buscan maximos locales cuya magnitud supere
    ``umbral * piso``. ``banda_util`` protege intervalos en Hz, no posiciones
    de bins: fuera de ellos se atenúa cada pico detectado y ``ancho_bins``
    vecinos por lado. La anchura cubre la fuga de un tono entre bins.

    La frecuencia del rechazo sale de ``mag`` en cada bloque. Por eso puede
    desplazarse la interferencia sin cambiar una frecuencia en el codigo.
    Devuelve ganancias reales entre 0 y 1 de la misma forma que ``mag``.
    """
    if umbral <= 0 or ancho_bins < 0 or atenuacion_db < 0:
        raise ValueError("Parametros de picos fuera de rango")
    n_bloques, n_bins = mag.shape
    piso = estimar_piso_ruido(mag, ancho_suavizado)
    g_min = 10.0 ** (-atenuacion_db / 20.0)
    f = np.arange(n_bins) * fs / N  # conversion de indice k a k*fs/N Hz
    protegido = np.zeros(n_bins, bool)
    if banda_util is not None:
        for (lo, hi) in np.atleast_2d(banda_util):
            protegido |= (f >= lo) & (f <= hi)

    G = np.ones_like(mag)
    for b in range(n_bloques):
        pico = (mag[b] > umbral * piso) & ~protegido
        # maximos locales para no marcar los lobulos laterales como picos
        loc = np.r_[False, (mag[b, 1:-1] >= mag[b, :-2]) & (mag[b, 1:-1] >= mag[b, 2:]), False]
        centros = np.flatnonzero(pico & loc)
        for c in centros:
            G[b, max(0, c - ancho_bins):c + ancho_bins + 1] = g_min
    return G


def detectar_tonos_estables(mag, fs, N, banda_util=(0, 1200), umbral=3.0,
                           ancho_bins=2, ancho_suavizado=31):
    """Busca tonos utiles persistentes para que la resta no los suprima.

    Un candidato debe estar dentro de ``banda_util``, ser maximo local,
    superar ``umbral`` veces el piso y variar poco entre bloques. Esto
    distingue aproximadamente tonos estables del ruido aleatorio. Se
    devuelven una mascara de bins protegidos y los centros detectados en Hz.

    En el caso 3, el ruido ocupa 900-1300 Hz y coincide con el tono de
    1100 Hz. Proteger el tono evita atenuarlo, pero tambien deja pasar parte
    del ruido que ocupa esos mismos bins; no existe separacion perfecta.
    """
    if ancho_bins < 0 or umbral <= 0:
        raise ValueError("Parametros de deteccion fuera de rango")
    perfil = np.median(mag, axis=0)
    piso = estimar_piso_ruido(mag, ancho_suavizado)
    freqs = np.fft.rfftfreq(N, 1 / fs)
    lo, hi = banda_util
    candidatos = (perfil > umbral * np.maximum(piso, 1e-12)) & (freqs >= lo) & (freqs <= hi)
    maximos = np.zeros(len(perfil), dtype=bool)
    maximos[1:-1] = (perfil[1:-1] >= perfil[:-2]) & (perfil[1:-1] >= perfil[2:])
    # Un tono mantiene magnitud entre bloques; el ruido aleatorio fluctua.
    # El cociente evita depender de la escala absoluta de la senal.
    variacion = np.std(mag, axis=0) / np.maximum(np.mean(mag, axis=0), 1e-12)
    centros = np.flatnonzero(candidatos & maximos & (variacion < 0.55))
    protegidos = np.zeros(len(perfil), dtype=bool)
    for centro in centros:
        protegidos[max(0, centro - ancho_bins):centro + ancho_bins + 1] = True
    return protegidos, freqs[centros].tolist()


def ganancias_resta(mag, alpha=1.5, g_min=0.05, ancho_suavizado=31,
                    proteger_tonos=None, fs=None, N=None, banda_util=(0, 1200),
                    umbral_tono=3.0, ancho_tono_bins=2):
    """Calcula una ganancia de sustraccion espectral por bloque y frecuencia.

    ``alpha`` controla cuanto piso de ruido se resta. Un valor mayor suele
    quitar mas ruido, pero puede reducir energia util. ``g_min`` limita la
    atenuacion para evitar ceros abruptos. Si ``proteger_tonos`` es verdadero,
    los bins detectados como tonos estables reciben G=1.

    Este metodo funciona mejor con ruido repartido entre muchos bins que
    con una interferencia sinusoidal dominante. El barrido del inciso 2.4 f)
    se realiza en el evaluador variando ``alpha`` sin proteccion tonal.
    """
    if alpha < 0 or not 0 <= g_min <= 1:
        raise ValueError("alpha y g_min fuera de rango")
    piso = estimar_piso_ruido(mag, ancho_suavizado)
    G = 1.0 - alpha * piso[None, :] / np.maximum(mag, 1e-12)
    G = np.clip(G, g_min, 1.0)
    if proteger_tonos:
        if fs is None or N is None:
            raise ValueError("fs y N son necesarios para proteger tonos")
        protegidos, _ = detectar_tonos_estables(
            mag, fs, N, banda_util, umbral_tono, ancho_tono_bins, ancho_suavizado
        )
        G[:, protegidos] = 1.0
    return G


def ganancias_top_k(mag, k=8, g_min=0.0):
    """Conserva los K bins de mayor magnitud de cada bloque.

    La seleccion depende de los datos del bloque. Es una referencia sencilla
    para comparar: puede conservar una interferencia intensa y perder
    componentes utiles debiles, como muestran los resultados de los casos.
    """
    if k < 1 or not 0 <= g_min <= 1:
        raise ValueError("k y g_min fuera de rango")
    G = np.full_like(mag, g_min)
    k = min(k, mag.shape[1])
    idx = np.argpartition(mag, -k, axis=1)[:, -k:]
    np.put_along_axis(G, idx, 1.0, axis=1)
    return G


# ----------------------------------------------------------------------------
# Filtro espectral por bloques (funcion principal)
# ----------------------------------------------------------------------------

def filtrar_espectral(x, fs, N=1024, metodo="picos", solape=0.5, **params):
    """Filtra una señal contaminada mediante FFT/IFFT y overlap-add.

    Parametros
    ----------
    x : arreglo unidimensional
        Señal contaminada; la referencia limpia nunca entra a esta funcion.
    fs : numero positivo
        Frecuencia de muestreo en Hz. Se usa para ubicar bins, no para
        cambiar las muestras.
    N : entero potencia de dos, por defecto 1024
        Longitud de cada FFT. La resolucion es ``fs/N`` Hz.
    metodo : {"picos", "resta", "top_k"}
        Estrategia de modificacion espectral.
    solape : 0.5
        La ventana sqrt(Hann) de analisis y sintesis usa exactamente 50 %.
    **params : dict
        ``picos``: umbral, ancho_bins, atenuacion_db, banda_util.
        ``resta``: alpha, g_min, proteger_tonos, banda_util, umbral_tono,
        ancho_tono_bins. Ambos admiten ancho_suavizado.
        ``top_k``: k, g_min.

    Devuelve
    --------
    salida : ndarray
        Vector real del mismo tamaño que ``x`` y sin retardo de indices.
    info : dict
        Ganancias por bloque y bin, fraccion modificada, N, hop y, si aplica,
        frecuencias de los tonos protegidos. Las ganancias pueden ocupar
        memoria significativa para capturas largas.

    Nota: se procesa la captura completa para estimar el piso. El codigo
    reproduce el experimento de la Tarea 1, no una rutina de streaming.
    """
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or len(x) == 0 or not np.all(np.isfinite(x)):
        raise ValueError("x debe ser un vector real, finito y no vacio")
    if fs <= 0:
        raise ValueError("fs debe ser positivo")
    if not es_potencia_de_dos(N) or N < 4:
        raise ValueError("N debe ser potencia de dos y al menos 4")
    if solape != 0.5:
        raise ValueError("Con sqrt-Hann solo se admite solape = 0.5")
    hop = int(N * (1 - solape))
    w = ventana_sqrt_hann(N)

    # Quitar DC impide que un offset contamine la estimacion del piso.
    # Se restaura al final para conservar el nivel original de la entrada.
    dc = x.mean()
    xc = x - dc

    # _trocear coloca relleno a ambos extremos para conservar COLA en bordes.
    # rFFT calcula solamente las N/2+1 frecuencias no negativas.
    bloques, pre, total = _trocear(xc, N, hop)
    X = np.fft.rfft(bloques * w[None, :], axis=1)
    mag = np.abs(X)

    # La estrategia modifica magnitudes mediante ganancias reales. No usa
    # fases ni consulta la referencia limpia.
    if metodo == "picos":
        G = ganancias_picos(mag, fs, N, **params)
    elif metodo == "resta":
        G = ganancias_resta(mag, fs=fs, N=N, **params)
    elif metodo == "top_k":
        G = ganancias_top_k(mag, **params)
    else:
        raise ValueError(f"Metodo desconocido: {metodo}")

    # La fase de cada bin conservado permanece intacta. irFFT reconstruye
    # implicitamente los bins negativos como conjugados de los positivos.
    Y = X * G
    y_bloques = np.fft.irfft(Y, n=N, axis=1) * w[None, :]

    # Cada bloque sintetizado se suma en la posicion de su salto. El producto
    # de ventanas hace que, con G=1, la suma reproduzca exactamente x.
    salida = np.zeros(total)
    for i in range(y_bloques.shape[0]):
        salida[i * hop:i * hop + N] += y_bloques[i]
    y = salida[pre:pre + len(x)] + dc

    info = {"ganancias": G, "fraccion_modificada": float(np.mean(G < 0.99)),
            "N": N, "hop": hop}
    if metodo == "resta" and params.get("proteger_tonos"):
        _, info["tonos_protegidos_Hz"] = detectar_tonos_estables(
            mag, fs, N,
            banda_util=params.get("banda_util", (0, 1200)),
            umbral=params.get("umbral_tono", 3.0),
            ancho_bins=params.get("ancho_tono_bins", 2),
            ancho_suavizado=params.get("ancho_suavizado", 31),
        )
    return y, info


# ----------------------------------------------------------------------------
# Verificaciones y metricas 
# ----------------------------------------------------------------------------

def verificar_simetria_conjugada(bloque: np.ndarray, G_rfft: np.ndarray) -> float:
    """Verifica numericamente la simetria que irFFT aplica implicitamente.

    Forma la FFT completa de un bloque real y refleja las ganancias de los
    bins positivos hacia los negativos. El bin DC y el de Nyquist solo
    aparecen una vez. Devuelve el maximo absoluto de la parte imaginaria
    tras IFFT; debe estar cerca de la precision de coma flotante.
    """
    N = len(bloque)
    if N % 2 or len(G_rfft) != N // 2 + 1:
        raise ValueError("Se requiere un bloque par y N/2+1 ganancias")
    X = np.fft.fft(bloque)
    Gf = np.concatenate([G_rfft, G_rfft[-2:0:-1]])      # G[N-k] = G[k]
    y = np.fft.ifft(X * Gf)
    return float(np.max(np.abs(y.imag)))


def mse(s, s_hat):
    """Error cuadratico medio frente a la referencia, sin alinear muestras."""
    s, s_hat = np.asarray(s), np.asarray(s_hat)
    return float(np.mean((s - s_hat) ** 2))


def snr_db(s, s_hat):
    """10 log10(E_referencia / E_error), igual al criterio basico de 2.3.

    ``s_hat`` debe tener los mismos indices temporales que ``s``. El filtro
    espectral los conserva; si el error es exactamente cero, devuelve +inf.
    """
    s, s_hat = np.asarray(s), np.asarray(s_hat)
    energia_error = np.sum((s - s_hat) ** 2)
    if energia_error == 0:
        return float("inf")
    return float(10 * np.log10(np.sum(s ** 2) / energia_error))


def energia_util_conservada(s_limpia, s_hat):
    """Porcentaje de energia total de salida respecto a la referencia limpia.

    El nombre se conserva por compatibilidad con el borrador inicial. La
    salida incluye ruido residual; por ello este porcentaje NO representa
    por si solo la energia util conservada. El evaluador mide aparte la
    amplitud de cada tono para analizar la distorsion de señal util.
    """
    s_limpia, s_hat = np.asarray(s_limpia), np.asarray(s_hat)
    return float(100 * np.sum(s_hat ** 2) / np.sum(s_limpia ** 2))


def atenuacion_db(x_in, x_out, fs, f0, ancho=5.0):
    """Atenuacion de potencia en dB alrededor de ``f0`` para evaluar.

    La frecuencia ``f0`` se usa solamente en esta metrica, despues de
    filtrar. El metodo ``picos`` no recibe ``f0`` y detecta la interferencia
    por contraste espectral en la entrada contaminada.
    """
    def pot(x):
        X = np.fft.rfft(x * np.hanning(len(x)))
        f = np.fft.rfftfreq(len(x), 1 / fs)
        return np.sum(np.abs(X[(f >= f0 - ancho) & (f <= f0 + ancho)]) ** 2)
    return float(10 * np.log10(pot(x_in) / max(pot(x_out), 1e-30)))


def barrido_compromiso(s, x, fs, metodo, nombre_param, valores, N=1024, **fijos):
    """Explora un parametro y devuelve MSE, SNR y energia total de salida.

    ``s`` es la referencia para metricas y ``x`` la entrada contaminada.
    El evaluador de casos usa un barrido mas detallado de ``alpha`` que
    tambien mide energia fuera de tonos y amplitud del tono de 1100 Hz.
    """
    filas = []
    for v in valores:
        y, _ = filtrar_espectral(x, fs, N, metodo, **{**fijos, nombre_param: v})
        filas.append({nombre_param: v, "mse": mse(s, y), "snr_db": snr_db(s, y),
                      "energia_salida_%": energia_util_conservada(s, y)})
    return filas


