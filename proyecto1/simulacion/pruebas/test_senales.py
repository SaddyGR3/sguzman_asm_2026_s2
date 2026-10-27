import copy

import numpy as np
import pytest
from scipy.io import wavfile

from sim import senales

CONFIG = senales.cargar_config()
FS = CONFIG["global"]["fs_Hz"]
L = round(FS * CONFIG["global"]["duracion_s"])
CASOS = [(p, s) for p, cfg in CONFIG["pruebas"].items() for s in cfg["semillas"]]
CASOS_RUIDO_BANDA = [(p, s) for p, s in CASOS if p != "P1"]


@pytest.fixture(scope="module")
def salida(tmp_path_factory):
    destino = tmp_path_factory.mktemp("senales")
    senales.generar_todas(destino)
    return destino


def _npz(salida, prueba, semilla):
    return np.load(salida / prueba / str(semilla) / "muestras.npz")


def _energia_db(energia, total):
    return 10 * np.log10(energia / total)


def test_quince_wav(salida):
    assert len(list(salida.glob("P*/*/entrada_estereo.wav"))) == 15


@pytest.mark.parametrize("prueba, semilla", CASOS)
def test_snr_pico_y_longitud(salida, prueba, semilla):
    d = _npz(salida, prueba, semilla)
    s, x = d["s"], d["x"]
    assert len(s) == len(x) == L == 80000
    assert abs(senales.snr_db(s, x) - CONFIG["pruebas"][prueba]["snr_dB"]) < 1e-8
    assert abs(np.max(np.abs(x)) - CONFIG["global"]["pico_x"]) < 1e-12
    assert np.max(np.abs(s)) <= 1


@pytest.mark.parametrize("prueba, semilla", CASOS)
def test_wav(salida, prueba, semilla):
    fs, wav = wavfile.read(salida / prueba / str(semilla) / "entrada_estereo.wav")
    d = _npz(salida, prueba, semilla)
    assert fs == 8000 and wav.dtype == np.int16 and wav.shape == (L, 2)
    tolerancia = 1/32767 + 1e-9
    assert np.max(np.abs(wav[:, 0]/32767 - d["x"])) <= tolerancia
    assert np.max(np.abs(wav[:, 1]/32767 - d["s"])) <= tolerancia


@pytest.mark.parametrize("prueba", CONFIG["pruebas"])
def test_reproducibilidad(prueba):
    semillas = CONFIG["pruebas"][prueba]["semillas"]
    a = senales.generar_caso(CONFIG, prueba, semillas[0])["x"]
    b = senales.generar_caso(CONFIG, prueba, semillas[0])["x"]
    c = senales.generar_caso(CONFIG, prueba, semillas[1])["x"]
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


@pytest.mark.parametrize("prueba, semilla", CASOS_RUIDO_BANDA)
def test_ruido_dentro_de_banda(salida, prueba, semilla):
    lo, hi = CONFIG["pruebas"][prueba]["ruido"]["banda_Hz"]
    r = _npz(salida, prueba, semilla)["r"]
    energia = np.abs(np.fft.rfft(r))**2
    f = np.fft.rfftfreq(len(r), 1/FS)
    fuera = (f < lo/1.5) | (f > min(1.5*hi, FS/2))
    assert _energia_db(energia[fuera].sum(), energia.sum()) <= -40


@pytest.mark.parametrize("semilla", CONFIG["pruebas"]["P3"]["semillas"])
def test_p3_senal_sin_energia_sobre_la_banda(salida, semilla):
    hi = CONFIG["pruebas"]["P3"]["senal"]["banda_Hz"][1]
    s = _npz(salida, "P3", semilla)["s"]
    energia = np.abs(np.fft.rfft(s))**2
    f = np.fft.rfftfreq(len(s), 1/FS)
    assert _energia_db(energia[f > hi].sum(), energia.sum()) <= -40


@pytest.mark.parametrize("semilla", CONFIG["pruebas"]["P4"]["semillas"])
def test_p4_rafagas(salida, semilla):
    cfg = CONFIG["pruebas"]["P4"]["senal"]
    n_rafaga = round(cfg["duracion_ms"]*FS/1000)
    n_rampa = round(cfg["rampa_ms"]*FS/1000)
    s = _npz(salida, "P4", semilla)["s"]
    dentro = np.zeros(L, dtype=bool)
    for k in range(cfg["cantidad"]):
        i0 = round((cfg["primer_arranque_s"] + k*cfg["periodo_s"])*FS)
        dentro[i0:i0 + n_rafaga] = True
        assert np.sum(s[i0:i0 + n_rampa]**2) > 0  # energía en los primeros 5 ms
    assert np.all(s[~dentro] == 0)


@pytest.mark.parametrize("semilla", CONFIG["pruebas"]["P1"]["semillas"])
def test_p1_frecuencias(salida, semilla):
    d = _npz(salida, "P1", semilla)
    f = np.fft.rfftfreq(L, 1/FS)
    f_ruido = CONFIG["pruebas"]["P1"]["ruido"]["frecuencia_Hz"]
    f_senal = CONFIG["pruebas"]["P1"]["senal"]["frecuencia_Hz"]
    assert abs(f[np.argmax(np.abs(np.fft.rfft(d["r"])))] - f_ruido) < 8
    assert abs(f[np.argmax(np.abs(np.fft.rfft(d["s"])))] - f_senal) < 8


def test_p5_tres_senales(salida):
    carpetas = sorted(c.name for c in (salida / "P5").iterdir())
    assert carpetas == ["202651", "202652", "202653"]


def test_validar_semillas():
    senales.validar_semillas(CONFIG)
    mala = copy.deepcopy(CONFIG)
    mala["pruebas"]["P1"]["semillas"].pop()
    with pytest.raises(ValueError):
        senales.validar_semillas(mala)


def test_fase_distinta_de_aleatoria():
    t = np.arange(L) / FS
    cfg = dict(CONFIG["pruebas"]["P1"]["senal"], fase=0.0)
    with pytest.raises(ValueError):
        senales.generar_senal_util(cfg, t, np.random.default_rng(0), FS)
