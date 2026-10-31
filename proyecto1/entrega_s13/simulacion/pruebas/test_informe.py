import csv

import numpy as np
import pytest

from sim import comparacion, costo, informe

CONFIGS = comparacion.cargar_configuraciones()


def _comprobar_png(ruta):
    assert ruta.is_file()
    assert ruta.stat().st_size > 10000
    assert ruta.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.parametrize("nombre", ["polos_ceros", "respuesta_nodo2", "cadena_analogica", "dft_fft"])
def test_figuras_nuevas(nombre, tmp_path):
    destino = tmp_path / "figuras" / f"{nombre}.png"
    if nombre == "polos_ceros":
        ruta = informe.figura_polos_ceros(CONFIGS["pruebas"], CONFIGS["nodo2"], destino)
    elif nombre == "respuesta_nodo2":
        ruta = informe.figura_respuesta_nodo2(CONFIGS["pruebas"], CONFIGS["nodo2"], destino)
    elif nombre == "cadena_analogica":
        ruta = informe.figura_cadena_analogica(CONFIGS["analogica"], destino)
    else:
        ruta = informe.figura_dft_fft(CONFIGS["pruebas"], destino)
    assert ruta == destino
    _comprobar_png(ruta)


def test_costo_con_nodo3(tmp_path):
    filas = costo.generar_costo(CONFIGS["pruebas"], CONFIGS["nodo2"], CONFIGS["analogica"],
                                CONFIGS["nodo3"], tmp_path)
    assert len(filas) == 5
    ultima = filas[-1]
    assert ultima["metodo"] == "Espectral nodo 3"
    assert ultima["mult_por_segundo"] == 688031.25
    assert ultima["memoria_bytes"] == 34860
    assert ultima["latencia_muestras"] == 512
    with (tmp_path / "costo.csv").open(encoding="utf-8", newline="") as archivo:
        exportadas = list(csv.DictReader(archivo))
    assert len(exportadas) == 5
    assert float(exportadas[-1]["mult_por_segundo"]) == 688031.25


def test_figura_comparacion(tmp_path, monkeypatch):
    from matplotlib.figure import Figure

    figuras = []
    guardar = Figure.savefig

    def capturar(figura, *args, **kwargs):
        figuras.append(figura)
        return guardar(figura, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", capturar)
    config = CONFIGS["pruebas"]
    semilla = config["pruebas"]["P1"]["semillas"][0]
    caso = comparacion.correr_caso(CONFIGS, "P1", semilla)
    fs = config["global"]["fs_Hz"]
    evaluacion = CONFIGS["nodo3"]["evaluacion"]
    i0, i1 = (round(evaluacion[clave] * fs) for clave in ("inicio_s", "fin_s"))
    destino = tmp_path / "P1.png"
    comparacion.figura_prueba(caso, "P1", destino, fs, i0, i1)
    _comprobar_png(destino)
    figura = figuras[0]
    assert len(figura.axes) == 3
    temporal, nodo2, nodo3 = figura.axes
    assert nodo2.get_title() == "Nodo 2 (filtrado temporal)"
    assert nodo3.get_title() == "Nodo 3 (filtrado espectral)"
    assert nodo2.get_ylim() == nodo3.get_ylim()
    for eje, ruta in ((nodo2, "nodo 2"), (nodo3, "nodo 3")):
        assert [linea.get_label() for linea in eje.lines] == ["contaminada (x)", "limpia (s)", ruta]
        assert eje.lines[0].get_alpha() == 0.5
        assert eje.get_ylim()[0] == -100
        for linea in eje.lines:
            color_temporal = next(l.get_color() for l in temporal.lines
                                  if l.get_label() == linea.get_label())
            assert linea.get_color() == color_temporal
    # Los nuevos paneles conservan la alineación temporal de la salida espectral.
    linea_n3 = next(linea for linea in temporal.lines if linea.get_label() == "nodo 3")
    inicio = round(5 * fs) + caso["retardo3"]
    fin = inicio + round(0.04 * fs)
    np.testing.assert_array_equal(linea_n3.get_ydata(), caso["y3"][inicio:fin])
