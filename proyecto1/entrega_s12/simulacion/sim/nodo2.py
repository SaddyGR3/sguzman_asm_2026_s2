"""Nodo 2 (filtrado temporal): FIR de la banda protegida y notch IIR de 2.º orden, aplicados
por bloques con estado. Los valores de diseño salen de config/nodo2.json y config/pruebas.json."""
import json
from pathlib import Path

import numpy as np
from scipy.signal import freqz, lfilter

from sim import senales

# Piso numérico para no imprimir -inf en dB cuando una ganancia es exactamente 0.
# No es un valor de diseño.
PISO_MAGNITUD = 1e-10


def cargar_config_nodo2():
    ruta = Path(__file__).resolve().parents[1] / "config" / "nodo2.json"
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


# --- Ventana de Kaiser con fórmula explícita ---

def bessel_i0(x):
    """I0(x) = suma de ((x/2)^k / k!)². Cada término sale del anterior multiplicando por
    (x/2)² / k², y se suma hasta que sea menor que 1e-16 de la suma. Acepta escalar o arreglo."""
    x = np.asarray(x, dtype=np.float64)
    cuadrado = (x / 2) ** 2
    termino = np.ones_like(x)
    suma = np.ones_like(x)
    k = 0
    while np.any(termino >= 1e-16 * suma):
        k += 1
        termino = termino * cuadrado / k ** 2
        suma = suma + termino
    return suma


def beta_kaiser(atenuacion_dB):
    """Parámetro β de la ventana de Kaiser según la atenuación A que se quiere."""
    a = atenuacion_dB
    if a > 50:
        return 0.1102 * (a - 8.7)
    if a >= 21:
        return 0.5842 * (a - 21) ** 0.4 + 0.07886 * (a - 21)
    return 0.0


def ventana_kaiser(n_coef, beta):
    """w[n] = I0(β·√(1 − (2n/(n_coef−1) − 1)²)) / I0(β), simétrica, n = 0…n_coef−1."""
    n = np.arange(n_coef)
    arg = 2 * n / (n_coef - 1) - 1
    return bessel_i0(beta * np.sqrt(1 - arg ** 2)) / bessel_i0(beta)


# --- FIR de la banda protegida ---

def es_pasa_banda(banda_Hz, cfg_n2):
    """True si el borde inferior de la banda es suficientemente alto para un pasa banda."""
    return banda_Hz[0] >= cfg_n2["fir_banda_protegida"]["borde_inferior_min_pasa_banda_Hz"]


def _pasa_bajas_ideal(fc_Hz, m, fs):
    """Respuesta al impulso del pasa bajas ideal con corte fc, para los retardos m."""
    return (2 * fc_Hz / fs) * np.sinc(2 * fc_Hz / fs * m)


def fir_banda_protegida(banda_Hz, cfg_n2, fs):
    """FIR de fase lineal (retardo de 18 muestras) para la banda (lo, hi): pasa bajas si lo es
    menor que el borde mínimo, y pasa banda si no. Se calcula con sinc por ventana de Kaiser y se
    normaliza a ganancia 1 en el centro de la banda (en continua para el pasa bajas)."""
    fir = cfg_n2["fir_banda_protegida"]
    n_coef, t = fir["coeficientes"], fir["transicion_Hz"]
    lo, hi = banda_Hz
    if not (0 < lo < hi and hi + t / 2 < fs / 2):
        raise ValueError(f"Banda inválida: ({lo}, {hi}) Hz con transición de {t} Hz a fs = {fs} Hz.")

    m = np.arange(n_coef) - (n_coef - 1) / 2
    if es_pasa_banda(banda_Hz, cfg_n2):
        h = _pasa_bajas_ideal(hi + t / 2, m, fs) - _pasa_bajas_ideal(lo - t / 2, m, fs)
        f_esc = ((lo - t / 2) + (hi + t / 2)) / 2
    else:
        h = _pasa_bajas_ideal(hi + t / 2, m, fs)
        f_esc = 0.0
    h = h * ventana_kaiser(n_coef, beta_kaiser(fir["atenuacion_diseno_dB"]))
    return h / np.sum(h * np.cos(2 * np.pi * f_esc * m / fs))


# --- Notch IIR de 2.º orden ---

def notch(f0_Hz, q, fs):
    """(b, a) del notch de 2.º orden: w0 = 2π·f0/fs, bw = w0/q, g = 1/(1 + tan(bw/2)),
    b = g·[1, −2·cos(w0), 1], a = [1, −2·g·cos(w0), 2g − 1].
    Ceros en e^{±j·w0}, sobre el círculo unitario: la ganancia en f0 es exactamente 0.
    Polos complejos conjugados con radio √(2g − 1) < 1. Ganancia 1 en continua y en Nyquist.
    Q = f0 / ancho de banda a −3 dB."""
    if not 0 < f0_Hz < fs / 2:
        raise ValueError(f"f0 debe cumplir 0 < f0 < {fs / 2} Hz, y es {f0_Hz}.")
    if q <= 0:
        raise ValueError(f"Q debe ser positivo, y es {q}.")
    w0 = 2 * np.pi * f0_Hz / fs
    g = 1 / (1 + np.tan(w0 / q / 2))
    return g * np.array([1.0, -2 * np.cos(w0), 1.0]), np.array([1.0, -2 * g * np.cos(w0), 2 * g - 1])


# --- Polos, ceros, ROC y estabilidad ---

def polos_ceros(b, a):
    """(polos, ceros). Un FIR (a = [1]) tiene len(b) − 1 polos en el origen:
    H(z) = Σ b[k]·z^(N−k) / z^N con N = len(b) − 1."""
    polos = np.zeros(len(b) - 1) if len(a) == 1 else np.roots(a)
    return polos, np.roots(b)


def radio_roc(polos):
    """Radio de la ROC causal: |z| > máx |polo|."""
    return float(np.max(np.abs(polos)))


def es_estable(polos):
    """Estable si la ROC causal incluye el círculo unitario."""
    return radio_roc(polos) < 1


# --- Aplicación por bloques y selección del filtro ---

def filtrar_por_bloques(b, a, x, H):
    """Filtra x en bloques de H muestras conservando el estado entre bloques, como en la placa.
    El último bloque puede ser más corto. Devuelve la salida, del mismo largo que x."""
    estado = np.zeros(max(len(a), len(b)) - 1)
    partes = []
    for i in range(0, len(x), H):
        y, estado = lfilter(b, a, x[i:i + H], zi=estado)
        partes.append(y)
    return np.concatenate(partes)


def disenar_filtro_nodo2(cfg_prueba, cfg_n2, fs, f0_Hz=None, q=None):
    """(b, a) del filtro que usa el nodo 2 en la prueba. En el notch, f0 la da el nodo 1."""
    tipo = cfg_prueba["filtro_n2"]
    if tipo == "fir_banda_protegida":
        return fir_banda_protegida(cfg_prueba["banda_protegida_Hz"], cfg_n2, fs), np.array([1.0])
    if tipo == "notch":
        if f0_Hz is None:
            raise ValueError("El notch necesita f0_Hz: la frecuencia la da el nodo 1.")
        return notch(f0_Hz, cfg_n2["notch"]["q_automatico"] if q is None else q, fs)
    raise ValueError(f"filtro_n2 desconocido: {tipo!r}.")


# --- Resumen de filtros ---

def _ganancia_dB(b, a, f_Hz, fs):
    """Ganancia en dB a f_Hz, con un piso numérico en la magnitud."""
    h = freqz(b, a, worN=[f_Hz], fs=fs)[1][0]
    return 20 * np.log10(max(abs(h), PISO_MAGNITUD))


if __name__ == "__main__":
    config = senales.cargar_config()
    cfg_n2 = cargar_config_nodo2()
    fs = config["global"]["fs_Hz"]
    t = cfg_n2["fir_banda_protegida"]["transicion_Hz"]
    for prueba, cfg in config["pruebas"].items():
        if cfg["filtro_n2"] == "fir_banda_protegida":
            lo, hi = cfg["banda_protegida_Hz"]
            b, a = disenar_filtro_nodo2(cfg, cfg_n2, fs)
            if es_pasa_banda(cfg["banda_protegida_Hz"], cfg_n2):
                tipo = f"FIR pasa banda, cortes {lo - t / 2:g} y {hi + t / 2:g} Hz"
            else:
                tipo = f"FIR pasa bajas, corte {hi + t / 2:g} Hz"
            polos = polos_ceros(b, a)[0]
            print(f"{prueba}: {tipo}; radio de la ROC {radio_roc(polos):.4f}, "
                  f"{'estable' if es_estable(polos) else 'inestable'}")
            continue
        f0 = cfg["frecuencia_notch_Hz"] if "frecuencia_notch_Hz" in cfg else cfg["ruido"]["frecuencia_Hz"]
        niveles = cfg.get("barrido", [{"nivel": "automático", "q_notch": None}])
        for nivel in niveles:
            b, a = disenar_filtro_nodo2(cfg, cfg_n2, fs, f0_Hz=f0, q=nivel["q_notch"])
            q = cfg_n2["notch"]["q_automatico"] if nivel["q_notch"] is None else nivel["q_notch"]
            polos = polos_ceros(b, a)[0]
            linea = (f"{prueba}: notch en {f0:g} Hz, Q = {q:g} ({nivel['nivel']}); "
                     f"radio de la ROC {radio_roc(polos):.4f}, "
                     f"{'estable' if es_estable(polos) else 'inestable'}")
            if "barrido" in cfg:    # ganancia en cada tono de la señal útil (700 y 1100 Hz entre ellos)
                ganancias = ", ".join(f"{f:g} Hz {_ganancia_dB(b, a, f, fs):.4f} dB"
                                      for f in cfg["senal"]["frecuencias_Hz"])
                linea += f"; ganancia en {ganancias}"
            print(linea)
