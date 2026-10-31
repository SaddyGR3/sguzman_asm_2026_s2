"""Métricas, alineación de rutas y condiciones de integración P1/P2/P5."""

import numpy as np

from sim import comparacion, metricas, nodo3


CONFIGS = comparacion.cargar_configuraciones()
PRUEBAS = CONFIGS["pruebas"]["pruebas"]
FS = CONFIGS["pruebas"]["global"]["fs_Hz"]
N = CONFIGS["pruebas"]["global"]["N"]
H = CONFIGS["pruebas"]["global"]["H"]
I0 = round(CONFIGS["nodo3"]["evaluacion"]["inicio_s"] * FS)
I1 = round(CONFIGS["nodo3"]["evaluacion"]["fin_s"] * FS)


def _medir(caso, prueba, ruta):
    if ruta == "nodo2":
        y, util, retardo = caso["y2"], caso["y2_s"], caso["retardo2"]
    else:
        y, util, retardo = caso["y3"], caso["y3_s"], caso["retardo3"]
    senal = PRUEBAS[prueba]["senal"]
    tonos = ([senal["frecuencia_Hz"]] if senal["tipo"] == "tono" else
             senal["frecuencias_Hz"] if senal["tipo"] == "multitono" else [])
    return comparacion.metricas_ruta(caso["s8"], caso["x8"], y, util, retardo,
                                     I0, I1, FS, PRUEBAS[prueba]["banda_atenuacion_Hz"], tonos)


def test_calidad_y_entrada():
    s = np.array([1.0, -1.0, 1.0, -1.0])
    assert metricas.calidad(s, s) == {"mse": 0.0, "snr_db": float("inf")}
    assert abs(metricas.calidad(s, 0.5 * s)["snr_db"] - 20 * np.log10(2)) < 1e-12
    x = s + np.array([0.1, -0.1, -0.1, 0.1])
    entrada = comparacion.metricas_ruta(s, x, x, s, 0, 0, len(s), FS, (100, 1200), [])
    assert entrada["delta_snr_dB"] == 0
    assert entrada["energia_util_pct"] == 100
    assert entrada["atenuacion_total_dB"] == 0


def test_alineacion_fir_y_espectral():
    caso = comparacion.correr_caso(CONFIGS, "P2", PRUEBAS["P2"]["semillas"][0])
    assert caso["retardo2"] == 18
    assert caso["retardo3"] == H
    correcto = _medir(caso, "P2", "nodo2")["energia_util_pct"]
    assert correcto > 99
    # La energía sola no detecta un desplazamiento de una muestra en tonos
    # estacionarios: comparar el error muestra a muestra sí lo detecta.
    referencia = metricas.recortar(caso["s8"], I0, I1)
    mse_18 = metricas.calidad(
        referencia, metricas.recortar(caso["y2_s"], I0, I1, 18))["mse"]
    mse_17 = metricas.calidad(
        referencia, metricas.recortar(caso["y2_s"], I0, I1, 17))["mse"]
    assert mse_18 < mse_17

    G = np.ones_like(caso["G"])
    identidad = nodo3.aplicar_ganancias(caso["s8"], G, N, H)
    medidas = comparacion.metricas_ruta(caso["s8"], caso["x8"], identidad,
                                        identidad, H, I0, I1, FS, None, [])
    assert medidas["snr_dB"] >= 100


def test_p1_criterios_de_ambas_rutas():
    caso = comparacion.correr_caso(CONFIGS, "P1", PRUEBAS["P1"]["semillas"][0])
    temporal = _medir(caso, "P1", "nodo2")
    espectral = _medir(caso, "P1", "nodo3")
    assert temporal["atenuacion_banda_dB"] >= 30
    assert temporal["ganancias_tonos_dB"]["700"] >= -0.1
    assert espectral["atenuacion_banda_dB"] >= 30
    assert espectral["ganancias_tonos_dB"]["700"] >= -0.5
    assert temporal["delta_snr_dB"] > 0
    assert espectral["delta_snr_dB"] > 0


def test_p2_criterios_de_ambas_rutas():
    caso = comparacion.correr_caso(CONFIGS, "P2", PRUEBAS["P2"]["semillas"][0])
    temporal = _medir(caso, "P2", "nodo2")
    espectral = _medir(caso, "P2", "nodo3")
    assert temporal["atenuacion_banda_dB"] >= 40
    assert all(g >= -0.1 for g in temporal["ganancias_tonos_dB"].values())
    assert espectral["delta_snr_dB"] > 0


def test_p5_compromiso():
    prueba = PRUEBAS["P5"]
    semilla = prueba["semillas"][0]
    niveles = prueba["barrido"][:3]
    medidas = [(_medir(caso, "P5", "nodo2"), _medir(caso, "P5", "nodo3"))
               for caso in (comparacion.correr_caso(CONFIGS, "P5", semilla, nivel)
                            for nivel in niveles)]
    ganancia_700 = [par[0]["ganancias_tonos_dB"]["700"] for par in medidas]
    atenuacion = [par[1]["atenuacion_banda_dB"] for par in medidas]
    ganancia_1100 = [par[1]["ganancias_tonos_dB"]["1100"] for par in medidas]
    assert ganancia_700[0] > ganancia_700[1] > ganancia_700[2]
    assert atenuacion[0] < atenuacion[1] < atenuacion[2]
    assert ganancia_1100[0] > ganancia_1100[1] > ganancia_1100[2]


def test_comparacion_en_memoria():
    """El evaluador devuelve datos; no escribe CSV ni figuras al probarlo."""
    reducido = dict(CONFIGS)
    reducido["pruebas"] = dict(CONFIGS["pruebas"])
    reducido["pruebas"]["pruebas"] = {"P1": dict(PRUEBAS["P1"], semillas=[202611])}
    filas = comparacion.comparar_todo(reducido)
    assert len(filas) == 3
    assert all(set(comparacion.COLUMNAS) == set(fila) for fila in filas)
    resumen = comparacion.resumir(filas)
    assert len(resumen) == 3
    assert all("snr_dB_media" in fila and "snr_dB_desv" in fila for fila in resumen)
