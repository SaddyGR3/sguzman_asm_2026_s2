"""Banco de señales de las pruebas P1-P5. Todos los valores salen de config/pruebas.json."""
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfiltfilt

RAIZ = Path(__file__).resolve().parents[1]
RUTA_CONFIG = RAIZ / "config" / "pruebas.json"


def cargar_config():
    with open(RUTA_CONFIG, encoding="utf-8") as f:
        return json.load(f)


# Origen: proyecto1/tarea1/entrega/tarea1/src/generar_senales.py (Tarea 1), sin cambios.
def rms(x):
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))


# Origen: proyecto1/tarea1/entrega/tarea1/src/generar_senales.py (Tarea 1), sin cambios.
def snr_db(clean, observed):
    error = observed - clean
    return 10*np.log10((np.sum(clean**2)+1e-15)/(np.sum(error**2)+1e-15))


# Origen: proyecto1/tarea1/entrega/tarea1/src/generar_senales.py (Tarea 1), sin cambios.
def fade(x, fs, ms=20):
    n = min(int(fs*ms/1000), len(x)//2)
    if n > 0:
        ramp = np.sin(np.linspace(0, np.pi/2, n))**2
        x = x.copy(); x[:n] *= ramp; x[-n:] *= ramp[::-1]
    return x


# Origen: proyecto1/tarea1/entrega/tarea1/src/generar_senales.py (Tarea 1), sin cambios.
def escalar_ruido_para_snr(clean, noise, target_db):
    target_noise_rms = rms(clean)/(10**(target_db/20))
    return noise*(target_noise_rms/(rms(noise)+1e-15))


# Origen: proyecto1/tarea1/entrega/tarea1/src/generar_senales.py (Tarea 1), parte de ruido_banda.
# Cambio: se separó el filtro del generador de ruido, porque también se aplica a la melodía de
# P3 y al tren de impulsos de P4.
def filtrar_banda(x, fs, band):
    low, high = band
    if not (0 < low < high < fs/2):
        raise ValueError(f'BANDA_RUIDO debe cumplir 0 < low < high < {fs/2}')
    sos = butter(6, [low, high], btype='bandpass', fs=fs, output='sos')
    return sosfiltfilt(sos, x)


# Origen: proyecto1/tarea1/entrega/tarea1/src/generar_senales.py (Tarea 1).
# Cambio: ahora delega el filtrado en filtrar_banda.
def ruido_banda(n, fs, band, rng):
    return filtrar_banda(rng.standard_normal(n), fs, band)


def _fase_aleatoria(cfg, rng):
    if cfg["fase"] != "aleatoria":
        raise ValueError(f"Fase no soportada: {cfg['fase']!r} (solo 'aleatoria').")
    return rng.uniform(-np.pi, np.pi)


def _multitono(cfg, t):
    return sum(a*np.sin(2*np.pi*f*t + np.deg2rad(p))
               for f, a, p in zip(cfg["frecuencias_Hz"], cfg["amplitudes"], cfg["fases_grados"]))


def _melodia(cfg, fs):
    n_nota = round(cfg["duracion_nota_s"]*fs)
    tau = np.arange(n_nota)/fs
    dur = cfg["duracion_nota_s"]
    env = cfg["envolvente"]
    ataque = env["ataque_ms"]/1000
    decaimiento = env["decaimiento_ms"]/1000
    liberacion = env["liberacion_ms"]/1000
    sostenido = env["sostenido"]
    envolvente = np.interp(tau, [0, ataque, ataque + decaimiento, dur - liberacion, dur],
                           [0, 1, sostenido, sostenido, 0])
    notas = []
    for f in cfg["notas_Hz"]:
        tono = sum(c*np.sin(2*np.pi*k*f*tau) for k, c in enumerate(cfg["armonicos"], start=1))
        notas.append(tono*envolvente)
    return filtrar_banda(np.concatenate(notas), fs, cfg["banda_Hz"])


def _rafagas(cfg, t, fs):
    s = np.zeros(len(t))
    n_rafaga = round(cfg["duracion_ms"]*fs/1000)
    n_rampa = round(cfg["rampa_ms"]*fs/1000)
    rampa = 0.5*(1 - np.cos(np.pi*np.arange(n_rampa)/n_rampa))
    ventana = np.ones(n_rafaga)
    ventana[:n_rampa] = rampa
    ventana[-n_rampa:] = rampa[::-1]
    for k in range(cfg["cantidad"]):
        i0 = round((cfg["primer_arranque_s"] + k*cfg["periodo_s"])*fs)
        tramo = slice(i0, i0 + n_rafaga)
        s[tramo] = cfg["amplitud"]*np.sin(2*np.pi*cfg["frecuencia_Hz"]*t[tramo])*ventana
    return s


def generar_senal_util(cfg, t, rng, fs):
    """Señal útil según cfg["tipo"] (sección `senal` de la prueba)."""
    tipo = cfg["tipo"]
    if tipo == "tono":
        return cfg["amplitud"]*np.sin(2*np.pi*cfg["frecuencia_Hz"]*t + _fase_aleatoria(cfg, rng))
    if tipo == "multitono":
        return _multitono(cfg, t)
    if tipo == "melodia":
        return _melodia(cfg, fs)
    if tipo == "rafagas":
        return _rafagas(cfg, t, fs)
    raise ValueError(f"Tipo de señal desconocido: {tipo!r}")


def _tren_impulsos(L, fs, tasa, rng):
    duracion = L/fs
    tiempos = []
    acumulado = rng.exponential(1/tasa)
    while acumulado <= duracion:
        tiempos.append(acumulado)
        acumulado += rng.exponential(1/tasa)
    signos = rng.choice([-1, 1], size=len(tiempos))
    indices = np.minimum(np.round(np.array(tiempos)*fs).astype(int), L - 1)
    d = np.zeros(L)
    np.add.at(d, indices, signos)
    return d


def generar_ruido(cfg, t, rng, fs):
    """Ruido sin escalar según cfg["tipo"] (sección `ruido` de la prueba)."""
    tipo = cfg["tipo"]
    if tipo == "tonal":
        return np.sin(2*np.pi*cfg["frecuencia_Hz"]*t + _fase_aleatoria(cfg, rng))
    if tipo == "banda":
        return ruido_banda(len(t), fs, cfg["banda_Hz"], rng)
    if tipo == "impulsivo":
        return filtrar_banda(_tren_impulsos(len(t), fs, cfg["tasa_por_s"], rng), fs, cfg["banda_Hz"])
    raise ValueError(f"Tipo de ruido desconocido: {tipo!r}")


def validar_semillas(config):
    repeticiones = config["global"]["repeticiones"]
    for nombre, cfg in config["pruebas"].items():
        if len(cfg["semillas"]) != repeticiones:
            raise ValueError(f"{nombre}: {len(cfg['semillas'])} semillas y repeticiones = {repeticiones}.")


def generar_caso(config, prueba, semilla):
    """Genera s, r y x de una prueba y semilla. Devuelve un dict con las señales y la SNR obtenida."""
    glob = config["global"]
    cfg = config["pruebas"][prueba]
    fs = glob["fs_Hz"]
    L = round(fs*glob["duracion_s"])
    t = np.arange(L)/fs

    rng = np.random.default_rng(semilla)
    s = fade(generar_senal_util(cfg["senal"], t, rng, fs), fs, glob["rampa_ms"])
    r0 = fade(generar_ruido(cfg["ruido"], t, rng, fs), fs, glob["rampa_ms"])
    if s.shape != (L,) or r0.shape != (L,):
        raise ValueError(f"{prueba}: la señal o el ruido no tienen {L} muestras.")
    r = escalar_ruido_para_snr(s, r0, cfg["snr_dB"])
    x = s + r

    g = glob["pico_x"]/np.max(np.abs(x))
    s, r, x = g*s, g*r, g*x

    snr = float(snr_db(s, x))
    assert abs(snr - cfg["snr_dB"]) < 1e-8, f"{prueba}/{semilla}: SNR {snr} ≠ {cfg['snr_dB']}"
    assert abs(np.max(np.abs(x)) - glob["pico_x"]) < 1e-12, f"{prueba}/{semilla}: pico de x fuera de tolerancia"
    assert np.max(np.abs(s)) <= 1, f"{prueba}/{semilla}: |s| supera 1"
    return {"s": s, "r": r, "x": x, "g": float(g), "snr_obtenida_dB": snr}


def guardar_caso(config, prueba, semilla, caso, destino):
    glob = config["global"]
    fs = glob["fs_Hz"]
    s, r, x = caso["s"], caso["r"], caso["x"]
    carpeta = Path(destino) / prueba / str(semilla)
    carpeta.mkdir(parents=True, exist_ok=True)

    estereo = np.column_stack((x, s))  # canal 0 = x, canal 1 = s
    wavfile.write(str(carpeta / "entrada_estereo.wav"), fs,
                  np.int16(np.round(np.clip(estereo, -1, 1) * 32767)))
    np.savez(carpeta / "muestras.npz", s=s, r=r, x=x, fs=fs)

    metadatos = {
        "prueba": prueba,
        "semilla": semilla,
        "fs_Hz": fs,
        "muestras": len(x),
        "snr_objetivo_dB": config["pruebas"][prueba]["snr_dB"],
        "snr_obtenida_dB": caso["snr_obtenida_dB"],
        "factor_escala": caso["g"],
        "pico_x": float(np.max(np.abs(x))),
        "pico_s": float(np.max(np.abs(s))),
        "configuracion": config["pruebas"][prueba],
    }
    with open(carpeta / "metadatos.json", "w", encoding="utf-8") as f:
        json.dump(metadatos, f, indent=2, ensure_ascii=False)


def generar_todas(destino=None):
    """Genera las 15 señales. Devuelve [(prueba, semilla, snr_obtenida_dB), ...]."""
    config = cargar_config()
    validar_semillas(config)
    if destino is None:
        destino = RAIZ / config["global"]["carpeta_salida"]
    resumen = []
    for prueba, cfg in config["pruebas"].items():
        for semilla in cfg["semillas"]:
            caso = generar_caso(config, prueba, semilla)
            guardar_caso(config, prueba, semilla, caso, destino)
            resumen.append((prueba, semilla, caso["snr_obtenida_dB"]))
    return resumen


if __name__ == "__main__":
    for prueba, semilla, snr in generar_todas():
        print(f"{prueba}  semilla {semilla}  SNR obtenida {snr:.6f} dB")
