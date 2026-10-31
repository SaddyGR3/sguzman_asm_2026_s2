"""Propiedades del procesador causal del nodo 3."""

import numpy as np
import pytest

from sim import nodo3, senales


CONFIG = senales.cargar_config()
CFG_N3 = nodo3.cargar_config_nodo3()
FS = CONFIG["global"]["fs_Hz"]
N = CONFIG["global"]["N"]
H = CONFIG["global"]["H"]


def test_ventana_y_reconstruccion_identidad():
    ventana = nodo3.ventana_sqrt_hann(N)
    assert np.max(np.abs(ventana[:H]**2 + ventana[H:]**2 - 1)) <= 1e-15
    x = np.random.default_rng(0).standard_normal(20_000)
    G = np.ones(((x.size + H - 1) // H, N // 2 + 1))
    y = nodo3.aplicar_ganancias(x, G, N, H)
    assert y.shape == x.shape
    assert np.max(np.abs(y[:H])) <= 1e-12
    assert np.max(np.abs(y[H:-H] - x[:-2 * H])) <= 1e-12


def test_suavizado_y_validacion():
    perfil = np.ones(N // 2 + 1)
    assert np.array_equal(nodo3.suavizar_piso(perfil, 31), perfil)
    perfil[100] = 100
    assert nodo3.suavizar_piso(perfil, 31)[100] == 1
    with pytest.raises(ValueError):
        nodo3.suavizar_piso(perfil, 30)


def test_calentamiento_y_causalidad():
    x = np.random.default_rng(1).standard_normal(20_000)
    original = nodo3.filtrar_espectral_causal(x, "resta", (100, 1200), CFG_N3, FS, N, H)
    assert original["tramas_calentamiento"] == CFG_N3["historial_tramas"]
    assert np.all(original["G"][:CFG_N3["historial_tramas"]] == 1)
    limite = CFG_N3["historial_tramas"] * H
    assert np.max(np.abs(original["y"][H:limite] - x[:limite - H])) <= 1e-12

    k = 10 * H
    modificado = x.copy()
    modificado[k:] *= -2
    nuevo = nodo3.filtrar_espectral_causal(modificado, "resta", (100, 1200),
                                           CFG_N3, FS, N, H)
    assert np.array_equal(original["y"][:k], nuevo["y"][:k])


def test_picos_fuera_de_banda_y_proteccion_dentro():
    t = np.arange(20_000) / FS
    ruido = np.random.default_rng(2).normal(0, 1e-3, t.size)
    banda = (100, 1200)
    fuera = nodo3.filtrar_espectral_causal(np.sin(2 * np.pi * 2150 * t) + ruido,
                                           "picos", banda, CFG_N3, FS, N, H)
    bin_ruido = round(2150 * N / FS)
    g_min = 10 ** (-CFG_N3["picos"]["atenuacion_dB"] / 20)
    assert np.all(fuera["G"][12:, bin_ruido] == g_min)

    dentro = nodo3.filtrar_espectral_causal(np.sin(2 * np.pi * 700 * t) + ruido,
                                            "picos", banda, CFG_N3, FS, N, H)
    assert np.all(dentro["G"][12:, round(700 * N / FS)] == 1)


def test_resta_protege_tono_estable():
    t = np.arange(20_000) / FS
    x = 0.4 * np.sin(2 * np.pi * 700 * t) + np.random.default_rng(3).normal(0, 0.05, t.size)
    con = nodo3.filtrar_espectral_causal(x, "resta", (100, 1200), CFG_N3, FS, N, H,
                                         proteccion=True)
    sin = nodo3.filtrar_espectral_causal(x, "resta", (100, 1200), CFG_N3, FS, N, H)
    bin_tono = round(700 * N / FS)
    assert np.all(con["G"][12:, bin_tono] == 1)
    assert np.all(sin["G"][12:, bin_tono] < 1)


def test_parametros_y_errores():
    pruebas = CONFIG["pruebas"]
    assert nodo3.parametros_nodo3(pruebas["P1"], CFG_N3) == ("picos", None, False)
    assert nodo3.parametros_nodo3(pruebas["P2"], CFG_N3) == ("resta", 3.0, True)
    assert nodo3.parametros_nodo3(pruebas["P3"], CFG_N3) == ("resta", 3, False)
    for nivel in pruebas["P5"]["barrido"]:
        assert nodo3.parametros_nodo3(pruebas["P5"], CFG_N3, nivel) == (
            "resta", nivel["alfa"], nivel["proteccion_tonos"])
    with pytest.raises(ValueError):
        nodo3.filtrar_espectral_causal(np.ones(N), "otro", (100, 1200), CFG_N3, FS, N, H)
    with pytest.raises(ValueError):
        nodo3.aplicar_ganancias(np.ones(N), np.ones((1, N // 2 + 1)), N, H)
