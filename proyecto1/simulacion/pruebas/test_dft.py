import numpy as np
import pytest

from sim import dft, senales


def test_dft_aleatoria_contra_fft():
    N = senales.cargar_config()["global"]["N"]
    x = np.random.default_rng(1).standard_normal(N)
    esperado = np.fft.fft(x)
    obtenido = dft.dft_directa(x)
    assert obtenido.dtype == np.complex128
    assert np.max(np.abs(obtenido - esperado)) / np.max(np.abs(esperado)) <= 1e-9


def test_dft_impulso():
    x = np.zeros(16)
    x[0] = 1
    assert np.max(np.abs(dft.dft_directa(x) - 1)) <= 1e-12


def test_dft_compleja_sin_fft_ni_matriz(monkeypatch):
    # La definición admite longitudes que no son potencias de dos y señales complejas.
    rng = np.random.default_rng(3)
    x = rng.standard_normal(15) + 1j * rng.standard_normal(15)
    esperado = np.fft.fft(x)

    def rechazar(*args, **kwargs):
        raise AssertionError("La DFT de referencia no debe usar FFT ni np.outer.")

    monkeypatch.setattr(np.fft, "fft", rechazar)
    monkeypatch.setattr(np, "outer", rechazar)
    assert np.max(np.abs(dft.dft_directa(x) - esperado)) <= 1e-12


def test_dft_coseno():
    N, bin_tono = 64, 5
    x = np.cos(2 * np.pi * bin_tono * np.arange(N) / N)
    magnitudes = np.abs(dft.dft_directa(x))
    assert np.max(np.abs(magnitudes[[bin_tono, N - bin_tono]] - N / 2)) <= 1e-9
    assert np.max(np.delete(magnitudes, [bin_tono, N - bin_tono])) <= 1e-9


def test_comparacion_campos_y_operaciones():
    x = np.random.default_rng(2).standard_normal(256)
    fila = dft.comparar_dft_fft(x, 1)
    assert set(fila) == {
        "N", "error_max_rel", "tiempo_dft_s", "tiempo_fft_s", "aceleracion",
        "operaciones_dft", "operaciones_fft", "cociente_operaciones",
    }
    assert fila["N"] == 256
    assert fila["operaciones_dft"] == 65536
    assert fila["operaciones_fft"] == 1024
    assert fila["cociente_operaciones"] == 64
    assert fila["error_max_rel"] <= 1e-9
    assert fila["tiempo_dft_s"] > 0
    assert fila["tiempo_fft_s"] > 0
    # La velocidad depende del equipo: no se impone un umbral de aceleración.
    assert np.isfinite(fila["aceleracion"]) and fila["aceleracion"] > 0


def test_comparacion_usa_mediana(monkeypatch):
    # Duraciones DFT: 4, 1, 2; FFT: 2, 0.5, 1. Sin depender del reloj real.
    instantes = iter([0, 4, 10, 12, 20, 21, 30, 30.5, 40, 42, 50, 51])
    monkeypatch.setattr(dft, "perf_counter", lambda: next(instantes))
    fila = dft.comparar_dft_fft(np.ones(16), 3)
    assert fila["tiempo_dft_s"] == 2
    assert fila["tiempo_fft_s"] == 1
    assert fila["aceleracion"] == 2


def test_comparacion_senal_nula():
    assert dft.comparar_dft_fft(np.zeros(16), 1)["error_max_rel"] == 0


@pytest.mark.parametrize("N, repeticiones", [(1000, 1), (16, 0), (16, -1),
                                              (16, 1.5), (0, 1), (1, 1)])
def test_comparacion_rechaza_parametros_invalidos(N, repeticiones):
    with pytest.raises(ValueError):
        dft.comparar_dft_fft(np.zeros(N), repeticiones)


@pytest.mark.parametrize("x", [[], [[1, 2], [3, 4]]])
def test_dft_rechaza_entrada_no_vectorial_o_vacia(x):
    with pytest.raises(ValueError):
        dft.dft_directa(x)
