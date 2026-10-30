import csv
from pathlib import Path
import runpy

from sim import analogico, costo, nodo2, senales


CONFIG = senales.cargar_config()
CFG_N2 = nodo2.cargar_config_nodo2()
CFG_ANALOGICA = analogico.cargar_config_analogica()


def test_tabla_costo_configuracion_real():
    filas = costo.tabla_costo(CONFIG, CFG_N2, CFG_ANALOGICA)
    # Valores independientes de la implementación, calculados para el diseño actual.
    # DFT: entrada, salida y términos (16 KiB cada uno) e índices (8 KiB).
    esperados = [
        (296000, 73, 292, 18, 0.75),
        (296000, 73, 292, 18, 2.25),
        (40000, 7, 28, 0, 0),
        (65536000, 14336, 57344, 0, 0),
    ]
    claves_numericas = ("mult_por_segundo", "memoria_valores", "memoria_bytes",
                       "latencia_muestras", "latencia_ms")
    claves = {"metodo", "nota", *claves_numericas}
    assert len(filas) == 4
    assert len({fila["metodo"] for fila in filas}) == 4
    for fila, esperado in zip(filas, esperados):
        assert set(fila) == claves
        assert tuple(fila[clave] for clave in claves_numericas) == esperado
        assert fila["nota"] and "\n" not in fila["nota"]


def test_costo_espectral():
    fila = costo.costo_espectral(1024, 512, 8000, 8)
    assert fila["mult_por_segundo"] == 688031.25
    assert fila["memoria_valores"] == 8715
    assert fila["memoria_bytes"] == 34860
    assert fila["latencia_muestras"] == 512
    assert fila["latencia_ms"] == 64


def test_coherencia_entre_metodos():
    glob = CONFIG["global"]
    fs, N, H = glob["fs_Hz"], glob["N"], glob["H"]
    assert (costo.costo_espectral(N, H, fs, 8)["mult_por_segundo"]
            < costo.costo_dft_trama(N, fs, H)["mult_por_segundo"])
    fila_fir = costo.costo_fir(CFG_N2["fir_banda_protegida"]["coeficientes"], fs)
    assert costo.costo_notch(fs)["mult_por_segundo"] < fila_fir["mult_por_segundo"]


def test_comando_costo_exporta_e_imprime(tmp_path, capsys):
    # Copiar solo el punto de entrada dirige su salida al directorio temporal;
    # las configuraciones se cargan desde los módulos originales del proyecto.
    copia = tmp_path / "sim" / "costo.py"
    copia.parent.mkdir()
    copia.write_text(Path(costo.__file__).read_text(encoding="utf-8"), encoding="utf-8")
    runpy.run_path(str(copia), run_name="__main__")
    with (tmp_path / "resultados" / "costo.csv").open(encoding="utf-8", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    assert len(filas) == 4
    assert float(filas[-1]["mult_por_segundo"]) == 65536000
    assert int(filas[-1]["memoria_bytes"]) == 57344
    salida = capsys.readouterr().out
    assert "Retardo (ms)" in salida
    assert all(fila["metodo"] in salida for fila in filas)
