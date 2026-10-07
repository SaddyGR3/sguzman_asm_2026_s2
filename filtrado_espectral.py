"""
Cadena: bloque -> ventana -> FFT -> estimacion/modificacion espectral -> IFFT
        -> reconstruccion por solapamiento (overlap-add) -> salida

Metodos (todos adaptativos, ninguno anula un bin fijo conocido de antemano):
  "picos" : detecta picos interferentes (magnitud > umbral * piso de ruido)
            fuera de la banda util y los atenua (ancho de rechazo configurable).
  "resta" : sustraccion espectral; el piso de ruido por bin se estima de los
            propios datos (mediana temporal + suavizado en frecuencia).
  "top_k" : conserva solo los K coeficientes mas energeticos de cada bloque.

Simetria conjugada: se trabaja con rfft/irfft sobre ganancias REALES por bin.
Esto garantiza X[N-k] = conj(X[k]) y por tanto una salida real. La funcion
`verificar_simetria_conjugada` lo comprueba contra una FFT completa.

Ventana: sqrt(Hann) periodica en analisis y sintesis con 50 % de solape. Su
cuadrado (Hann periodica) cumple COLA a hop = N/2, asi que con ganancia 1
la reconstruccion es perfecta.
"""
import numpy as np
from scipy.signal import medfilt

# ----------------------------------------------------------------------------
# Utilidades basicas
# ----------------------------------------------------------------------------

def es_potencia_de_dos(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def ventana_sqrt_hann(N: int) -> np.ndarray:
    """sqrt de Hann periodica; w^2 suma 1 con hop = N/2."""
    n = np.arange(N)
    return np.sqrt(0.5 * (1.0 - np.cos(2.0 * np.pi * n / N)))


def _trocear(x: np.ndarray, N: int, hop: int):
    """Rellena con ceros y devuelve matriz (n_bloques, N)."""
    pre = N - hop                                   # cubre el inicio con 2 bloques
    n_bloques = int(np.ceil((len(x) + pre) / hop))
    total = (n_bloques - 1) * hop + N
    xp = np.zeros(total)
    xp[pre:pre + len(x)] = x
    idx = np.arange(N)[None, :] + hop * np.arange(n_bloques)[:, None]
    return xp[idx], pre, total


# ----------------------------------------------------------------------------
# Calculo de ganancias espectrales 
# ----------------------------------------------------------------------------

def estimar_piso_ruido(mag: np.ndarray, ancho_suavizado: int = 31) -> np.ndarray:
    """
    Piso de ruido por bin: mediana en el tiempo y mediana en frecuencia.
    El suavizado en frecuencia elimina los picos estrechos (tonos), de modo que
    el piso refleje el ruido de fondo y no las componentes tonales.
    mag: (n_bloques, n_bins)
    """
    if ancho_suavizado % 2 == 0:
        ancho_suavizado += 1
    piso = np.median(mag, axis=0)
    return medfilt(piso, kernel_size=ancho_suavizado)


def ganancias_picos(mag, fs, N, umbral=6.0, ancho_bins=2, atenuacion_db=60.0,
                    banda_util=None, ancho_suavizado=31):
    """
    Atenua picos que superan `umbral` veces el piso de ruido estimado.
    banda_util: (f_lo, f_hi) en Hz. Los picos DENTRO de la banda se consideran
                senal util y se conservan. Si es None, se atenuan todos.
    ancho_bins: bins a cada lado del pico que tambien se atenuan (ancho de rechazo).
    """
    n_bloques, n_bins = mag.shape
    piso = estimar_piso_ruido(mag, ancho_suavizado)
    g_min = 10.0 ** (-atenuacion_db / 20.0)
    f = np.arange(n_bins) * fs / N
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


def ganancias_resta(mag, alpha=1.5, g_min=0.05, ancho_suavizado=31):
    """Sustraccion espectral en magnitud: G = max(1 - alpha*piso/|X|, g_min)."""
    piso = estimar_piso_ruido(mag, ancho_suavizado)
    G = 1.0 - alpha * piso[None, :] / np.maximum(mag, 1e-12)
    return np.maximum(G, g_min)


def ganancias_top_k(mag, k=8, g_min=0.0):
    """Conserva los k bins de mayor magnitud en cada bloque."""
    G = np.full_like(mag, g_min)
    k = min(k, mag.shape[1])
    idx = np.argpartition(mag, -k, axis=1)[:, -k:]
    np.put_along_axis(G, idx, 1.0, axis=1)
    return G


# ----------------------------------------------------------------------------
# Filtro espectral por bloques (funcion principal)
# ----------------------------------------------------------------------------

def filtrar_espectral(x, fs, N=1024, metodo="picos", solape=0.5, **params):
    """
    Reduce ruido de `x` por bloques FFT/IFFT con overlap-add.

    x       : senal contaminada (1D)
    fs      : frecuencia de muestreo [Hz]
    N       : tamano de bloque (potencia de dos)
    metodo  : "picos" | "resta" | "top_k"
    solape  : 0.5 (50 %), requerido por la ventana sqrt-Hann (COLA)
    params  : parametros adaptativos del metodo elegido
              picos: umbral, ancho_bins, atenuacion_db, banda_util, ancho_suavizado
              resta: alpha, g_min, ancho_suavizado
              top_k: k, g_min
    Devuelve (y, info) con info = dict (ganancias, fraccion de bins modificados).
    """
    x = np.asarray(x, dtype=float)
    if not es_potencia_de_dos(N):
        raise ValueError("N debe ser potencia de dos")
    if solape != 0.5:
        raise ValueError("Con sqrt-Hann solo se admite solape = 0.5")
    hop = int(N * (1 - solape))
    w = ventana_sqrt_hann(N)

    # 0) quitar componente DC (el ADC real tiene offset)
    dc = x.mean()
    xc = x - dc

    # 1) bloques + ventana, 2) FFT
    bloques, pre, total = _trocear(xc, N, hop)
    X = np.fft.rfft(bloques * w[None, :], axis=1)
    mag = np.abs(X)

    # 3) estimacion de ruido / seleccion de componentes -> ganancias reales
    if metodo == "picos":
        G = ganancias_picos(mag, fs, N, **params)
    elif metodo == "resta":
        G = ganancias_resta(mag, **params)
    elif metodo == "top_k":
        G = ganancias_top_k(mag, **params)
    else:
        raise ValueError(f"Metodo desconocido: {metodo}")

    # 4) modificacion del espectro (ganancia real => fase intacta y simetria
    #    conjugada preservada), 5) IFFT
    Y = X * G
    y_bloques = np.fft.irfft(Y, n=N, axis=1) * w[None, :]

    # 6) overlap-add
    salida = np.zeros(total)
    for i in range(y_bloques.shape[0]):
        salida[i * hop:i * hop + N] += y_bloques[i]
    y = salida[pre:pre + len(x)] + dc

    info = {"ganancias": G, "fraccion_modificada": float(np.mean(G < 0.99)),
            "N": N, "hop": hop}
    return y, info