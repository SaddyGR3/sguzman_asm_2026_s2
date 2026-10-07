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