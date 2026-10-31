import copy

import numpy as np
import pytest
from scipy.signal import lfilter, sosfreqz

from sim import analogico

CFG = analogico.cargar_config_analogica()
FS = CFG["tasas"]["fs_Hz"]
FA = CFG["tasas"]["fa_Hz"]
ADC = CFG["adc"]


def _tono(f_Hz, amplitud, duracion_s, fs):
    return amplitud * np.sin(2 * np.pi * f_Hz * np.arange(round(duracion_s * fs)) / fs)


def _amplitud(senal, f_Hz, fs, t0, t1):
    """Amplitud del tono de f_Hz entre t0 y t1 (s): mínimos cuadrados de [cos, sin, 1]."""
    i0, i1 = round(t0 * fs), round(t1 * fs)
    t = np.arange(i0, i1) / fs
    base = np.column_stack((np.cos(2 * np.pi * f_Hz * t), np.sin(2 * np.pi * f_Hz * t),
                            np.ones_like(t)))
    coef = np.linalg.lstsq(base, senal[i0:i1], rcond=None)[0]
    return float(np.hypot(coef[0], coef[1]))


def _db(razon):
    return 20 * np.log10(razon)


def test_config():
    analogico.validar_config(CFG)
    alterada = copy.deepcopy(CFG)
    alterada["decimacion"]["coeficientes"] = 36
    with pytest.raises(ValueError):
        analogico.validar_config(alterada)
    acople = CFG["acople_entrada"]
    centro = (acople["V_alimentacion_V"] * acople["R_inferior_ohm"]
              / (acople["R_superior_ohm"] + acople["R_inferior_ohm"]))
    assert abs(centro - 1.32) < 1e-12
    assert abs(centro - ADC["v_centro_V"]) < 1e-12


def test_parametros_sallen_key():
    fc, q = analogico.sallen_key_parametros(CFG)
    assert 3350 < fc < 3470
    assert 0.70 < q < 0.76


def test_sallen_key_discreto_contra_analitico():
    f = np.linspace(10, 4000, 400)
    _, h_discreto = sosfreqz(analogico.sallen_key_discreto(CFG), worN=2 * np.pi * f / FA)
    h_analitico = analogico.respuesta_sallen_key(CFG, f)
    diferencia = _db(np.abs(h_discreto)) - _db(np.abs(h_analitico))
    assert np.max(np.abs(diferencia)) <= 0.1


def test_sallen_key_a_3k():
    nivel = _db(np.abs(analogico.respuesta_sallen_key(CFG, [3000.0])[0]))
    assert abs(nivel - (-2.0)) <= 0.3


def test_fir_decimacion():
    h = analogico.coeficientes_decimacion(CFG)
    assert len(h) == 37
    assert np.array_equal(h, h[::-1])
    assert abs(np.sum(h) - 1) < 1e-6
    banda = np.linspace(0, 3000, 301)
    ondulacion = _db(np.abs(analogico.respuesta_decimacion(CFG, banda)))
    assert np.max(np.abs(ondulacion)) <= 0.1
    rechazo = np.linspace(5000, 12000, 701)
    assert -np.max(_db(np.abs(analogico.respuesta_decimacion(CFG, rechazo)))) >= 45


def test_retardo_decimacion():
    impulso = np.zeros(200)
    impulso[0] = 1.0
    respuesta = lfilter(analogico.coeficientes_decimacion(CFG), 1.0, impulso)
    assert np.argmax(respuesta) == 18
    assert np.argmax(respuesta[::CFG["decimacion"]["factor"]]) == 6


def test_largo_entrada():
    x = _tono(700, 0.5, 1.0, FS)
    salida = analogico.entrada_nodo1(x, x, CFG)
    assert len(x) == 8000
    assert len(salida["x"]) == len(salida["s"]) == 8000


def test_dos_canales_iguales():
    x = _tono(700, 0.5, 1.0, FS)
    salida = analogico.entrada_nodo1(x, x.copy(), CFG)
    assert np.array_equal(salida["x"], salida["s"])
    assert salida["saturaciones_x"] == salida["saturaciones_s"]


def test_ganancia_en_banda():
    salida = analogico.entrada_nodo1(_tono(1000, 0.8, 1.0, FS), _tono(1000, 0.8, 1.0, FS), CFG)
    amplitud = _amplitud(salida["x"], 1000, FS, 0.2, 0.9)
    assert abs(_db(amplitud / 0.8)) <= 0.5


def test_aliasing():
    v96 = _tono(7000, 0.8, 1.0, FA)
    senal, _ = analogico._canal_desde_analogico(v96, CFG)
    alias = _amplitud(senal, 1000, FS, 0.2, 0.9)
    assert _db(alias / 0.8) <= -50


def test_saturacion_entrada():
    x = _tono(1000, 1.2, 1.0, FS)
    salida = analogico.entrada_nodo1(x, x.copy(), CFG)
    minimo = (ADC["v_min_V"] - ADC["v_centro_V"]) / ADC["escala_V"]
    maximo = (ADC["v_max_V"] - ADC["v_centro_V"]) / ADC["escala_V"]
    assert salida["saturaciones_x"] > 0
    assert np.max(salida["x"]) <= maximo + 0.02
    assert np.min(salida["x"]) >= minimo - 0.02


def test_salida_a_3k():
    y = analogico.salida_dac(_tono(3000, 0.8, 1.0, FS), CFG)["y"]
    amplitud = _amplitud(y, 3000, FA, 0.2, 0.9)
    assert abs(_db(amplitud / 0.8) - (-4.0)) <= 0.5
    esperada = (0.8 * np.abs(analogico.respuesta_sallen_key(CFG, [3000.0])[0])
                * np.abs(analogico.respuesta_zoh(CFG, [3000.0])[0]))
    assert abs(_db(amplitud / esperada)) <= 0.3


def test_imagen_del_dac():
    y = analogico.salida_dac(_tono(300, 0.8, 1.2, FS), CFG)["y"]
    fundamental = _amplitud(y, 300, FA, 0.1, 1.1)
    imagen = _amplitud(y, 7700, FA, 0.1, 1.1)
    assert _db(imagen / fundamental) <= -40


def test_saturacion_dac():
    salida = analogico.salida_dac(_tono(1000, 1.1, 0.5, FS), CFG)
    assert salida["saturaciones"] > 0
