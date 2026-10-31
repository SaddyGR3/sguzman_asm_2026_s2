"""Modelo de la cadena analógica: PC -> nodo 1 (entrada) y nodos 2 y 3 -> parlante (salida).
Todos los valores de hardware salen de config/cadena_analogica.json."""
import json
from pathlib import Path

import numpy as np
from scipy.signal import (bilinear, firwin, freqs, freqz, kaiser_beta, lfilter,
                          resample_poly, sosfilt, tf2sos)

RAIZ = Path(__file__).resolve().parents[1]
RUTA_RESULTADOS = RAIZ / "resultados" / "decimacion.json"


def cargar_config_analogica():
    ruta = Path(__file__).resolve().parents[1] / "config" / "cadena_analogica.json"
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def validar_config(cfg):
    """Revisa que las tasas, la decimación y el centro del ADC sean coherentes entre sí."""
    tasas = cfg["tasas"]
    fa, fs_adc, fs = tasas["fa_Hz"], tasas["fs_adc_Hz"], tasas["fs_Hz"]
    if fa % fs_adc != 0 or fs_adc % fs != 0:
        raise ValueError("fa_Hz debe ser múltiplo entero de fs_adc_Hz, y este de fs_Hz.")
    if fs_adc / fs != cfg["decimacion"]["factor"]:
        raise ValueError("fs_adc_Hz / fs_Hz debe ser igual al factor de decimación.")
    if cfg["decimacion"]["coeficientes"] % 2 == 0:
        raise ValueError("El FIR de decimación debe tener un número impar de coeficientes.")
    acople = cfg["acople_entrada"]
    centro = (acople["V_alimentacion_V"] * acople["R_inferior_ohm"]
              / (acople["R_superior_ohm"] + acople["R_inferior_ohm"]))
    if abs(cfg["adc"]["v_centro_V"] - centro) >= 1e-12:
        raise ValueError(f"v_centro_V no coincide con el centro del divisor ({centro} V).")


# --- Sallen-Key de ganancia unitaria (pasa bajas de 2.º orden) ---

def sallen_key_parametros(cfg):
    """Devuelve (fc_Hz, Q). C1 es el capacitor de realimentación y C2 el que va a tierra."""
    sk = cfg["sallen_key"]
    r1, r2, c1, c2 = sk["R1_ohm"], sk["R2_ohm"], sk["C1_F"], sk["C2_F"]
    raiz = np.sqrt(r1 * r2 * c1 * c2)
    return 1 / (2 * np.pi * raiz), raiz / (c2 * (r1 + r2))


def sallen_key_analogico(cfg):
    """(b, a) en s de H(s) = w0² / (s² + (w0/Q)·s + w0²)."""
    fc, q = sallen_key_parametros(cfg)
    w0 = 2 * np.pi * fc
    return np.array([w0 ** 2]), np.array([1.0, w0 / q, w0 ** 2])


def sallen_key_discreto(cfg):
    """sos a fa_Hz, por transformación bilineal del filtro analógico."""
    b, a = sallen_key_analogico(cfg)
    bz, az = bilinear(b, a, fs=cfg["tasas"]["fa_Hz"])
    return tf2sos(bz, az)


# --- Acople de entrada (pasa altas de 1.er orden) ---

def acople_discreto(cfg):
    """(b, a) a fa_Hz de H(s) = s / (s + wc), con R = R_superior en paralelo con R_inferior."""
    ac = cfg["acople_entrada"]
    r = ac["R_superior_ohm"] * ac["R_inferior_ohm"] / (ac["R_superior_ohm"] + ac["R_inferior_ohm"])
    wc = 1 / (r * ac["C_F"])
    return bilinear([1.0, 0.0], [1.0, wc], fs=cfg["tasas"]["fa_Hz"])


# --- FIR de decimación ---

def coeficientes_decimacion(cfg):
    """FIR pasa bajas Kaiser a fs_adc_Hz. Con 37 coeficientes el retardo es de 18 muestras
    a 24 kHz, es decir 6 muestras exactas a 8 kHz."""
    d = cfg["decimacion"]
    return firwin(d["coeficientes"], d["corte_Hz"],
                  window=("kaiser", kaiser_beta(d["atenuacion_beta_dB"])),
                  fs=cfg["tasas"]["fs_adc_Hz"])


# --- Cadena de entrada (nodo 1) ---

def _canal_desde_analogico(v96, cfg):
    """Pasos 2 a 10 de la entrada, desde la señal analógica a fa_Hz hasta 8 kHz.
    Devuelve (señal a 8 kHz, saturaciones del ADC)."""
    tasas, adc = cfg["tasas"], cfg["adc"]
    b, a = acople_discreto(cfg)
    senal = lfilter(b, a, v96)                              # 2. acople
    senal = sosfilt(sallen_key_discreto(cfg), senal)        # 3. Sallen-Key
    senal = senal[::tasas["fa_Hz"] // tasas["fs_adc_Hz"]]   # 4. muestreo del ADC a 24 kHz

    v = adc["v_centro_V"] + adc["escala_V"] * senal         # 5. voltaje
    saturaciones = int(np.count_nonzero((v < adc["v_min_V"]) | (v > adc["v_max_V"])))
    v = np.clip(v, adc["v_min_V"], adc["v_max_V"])          # 6. recorte

    # Limitación del modelo: la calibración del ADC se supone ideal e ignora la alinealidad
    # real del ADC del ESP32, y el paso de cuantización de 3.3 V/4096 es un supuesto levemente
    # pesimista. Ambos se verifican en la placa en la fase 4.
    q = adc["v_ref_V"] / 2 ** adc["bits"]
    v = np.round(v / q) * q                                 # 7. cuantización
    senal = (v - adc["v_centro_V"]) / adc["escala_V"]       # 8. calibración ideal

    senal = lfilter(coeficientes_decimacion(cfg), 1.0, senal)   # 9. FIR de decimación (causal)
    return senal[::cfg["decimacion"]["factor"]], saturaciones   # 10. ÷3


def _canal_entrada(v, cfg):
    """Un canal (x o s) a 8 kHz: lo que reconstruye la PC y lo que mide el nodo 1."""
    tasas = cfg["tasas"]
    v96 = resample_poly(v, tasas["fa_Hz"] // tasas["fs_Hz"], 1)   # 1. PC a fa_Hz
    return _canal_desde_analogico(v96, cfg)


def entrada_nodo1(x, s, cfg):
    """x y s a 8 kHz (normalizadas, mismo largo L) pasan por exactamente la misma cadena."""
    x8, saturaciones_x = _canal_entrada(x, cfg)
    s8, saturaciones_s = _canal_entrada(s, cfg)
    return {"x": x8, "s": s8, "saturaciones_x": saturaciones_x, "saturaciones_s": saturaciones_s}


# --- Cadena de salida (nodos 2 y 3) ---

def salida_dac(y, cfg):
    """y a 8 kHz (normalizada) -> DAC de 8 bits, retención y Sallen-Key. La salida queda a fa_Hz."""
    bits = cfg["dac"]["bits"]
    medio = (2 ** bits - 1) / 2
    codigo = np.round(medio + medio * np.asarray(y))
    saturaciones = int(np.count_nonzero((codigo < 0) | (codigo > 2 ** bits - 1)))
    codigo = np.clip(codigo, 0, 2 ** bits - 1)
    normalizada = (codigo - medio) / medio
    retenida = np.repeat(normalizada, cfg["tasas"]["fa_Hz"] // cfg["tasas"]["fs_Hz"])   # ZOH
    # El seguidor de voltaje es ideal (ganancia 1) y no se modela.
    return {"y": sosfilt(sallen_key_discreto(cfg), retenida), "saturaciones": saturaciones}


# --- Respuestas en frecuencia ---

def respuesta_sallen_key(cfg, f_Hz):
    """Respuesta analítica compleja del Sallen-Key en las frecuencias f_Hz."""
    b, a = sallen_key_analogico(cfg)
    return freqs(b, a, worN=2 * np.pi * np.atleast_1d(f_Hz))[1]


def respuesta_decimacion(cfg, f_Hz):
    """Respuesta compleja del FIR de decimación en las frecuencias f_Hz."""
    return freqz(coeficientes_decimacion(cfg), worN=np.atleast_1d(f_Hz),
                 fs=cfg["tasas"]["fs_adc_Hz"])[1]


def respuesta_zoh(cfg, f_Hz):
    """Magnitud de la retención de orden cero a fs_Hz."""
    return np.sinc(np.atleast_1d(f_Hz) / cfg["tasas"]["fs_Hz"])


def _metricas_decimacion(cfg):
    """(ondulación máxima hasta 3 kHz, rechazo mínimo desde 5 kHz) en dB, con 4096 puntos."""
    f = np.linspace(0, cfg["tasas"]["fs_adc_Hz"] / 2, 4096)
    mag_db = 20 * np.log10(np.abs(respuesta_decimacion(cfg, f)))
    return float(np.max(np.abs(mag_db[f <= 3000]))), float(-np.max(mag_db[f >= 5000]))


if __name__ == "__main__":
    cfg = cargar_config_analogica()
    validar_config(cfg)
    h = coeficientes_decimacion(cfg)
    fc, q = sallen_key_parametros(cfg)
    ondulacion, rechazo = _metricas_decimacion(cfg)
    retardo_24k = (len(h) - 1) // 2
    resultado = {
        "coeficientes_float64": h.tolist(),
        "coeficientes_float32": h.astype(np.float32).tolist(),
        "retardo_muestras_24k": retardo_24k,
        "retardo_muestras_8k": retardo_24k // cfg["decimacion"]["factor"],
        "ondulacion_max_dB_hasta_3k": ondulacion,
        "rechazo_min_dB_desde_5k": rechazo,
        "fc_sallen_key_Hz": float(fc),
        "q_sallen_key": float(q),
    }
    RUTA_RESULTADOS.parent.mkdir(exist_ok=True)
    with open(RUTA_RESULTADOS, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)
    print(f"Sallen-Key: fc = {fc:.1f} Hz, Q = {q:.3f}")
    print(f"FIR de decimación: ondulación hasta 3 kHz = {ondulacion:.4f} dB, "
          f"rechazo desde 5 kHz = {rechazo:.1f} dB")
    print(f"Coeficientes guardados en {RUTA_RESULTADOS}")
