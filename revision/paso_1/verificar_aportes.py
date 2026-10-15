"""Audita los aportes existentes sin modificar sus señales ni resultados.

Ejecutar desde la raíz: .venv/bin/python revision/paso_1/verificar_aportes.py
El notebook se ejecuta en una carpeta temporal, en orden y con un namespace
limpio. Se ejecutan sus celdas Python; no se valida el frontend de Jupyter.
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl-tarea1")

import matplotlib
import numpy as np
import scipy
from scipy.io import wavfile

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = Path(__file__).resolve().parent
CASOS = RAIZ / "seccion_2_2/2_2_generacionsenales/pruebas"


def cargar_modulo(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def ejecutar_comando(argumentos, cwd, archivo_log):
    proceso = subprocess.run(
        [sys.executable, *map(str, argumentos)], cwd=cwd,
        capture_output=True, text=True, env=os.environ.copy(), timeout=180,
    )
    (DESTINO / archivo_log).write_text(
        proceso.stdout + proceso.stderr, encoding="utf-8"
    )
    if proceso.returncode:
        raise RuntimeError(f"Falló {argumentos}; consultar {archivo_log}")
    return {"argumentos": list(map(str, argumentos)), "codigo_salida": 0,
            "log": archivo_log}


def main():
    configuraciones = json.loads(
        (RAIZ / "seccion_2_2/metadatos/configuraciones.json").read_text()
    )
    informe = {"entorno": {"python": platform.python_version(),
                           "numpy": np.__version__, "scipy": scipy.__version__,
                           "matplotlib": matplotlib.__version__},
               "casos": [], "pruebas_temporales": []}

    with tempfile.TemporaryDirectory(prefix="tarea1-revision-") as temporal:
        trabajo = Path(temporal)
        notebook = json.loads(
            (RAIZ / "seccion_2_2/ce1110-generador-de-se-ales.ipynb").read_text()
        )
        namespace = {"__name__": "__main__"}
        buffer = io.StringIO()
        anterior = Path.cwd()
        ejecutadas = []
        try:
            os.chdir(trabajo)
            with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
                for indice, celda in enumerate(notebook["cells"]):
                    if celda["cell_type"] == "code":
                        exec(compile("".join(celda["source"]),
                                     f"notebook:celda_{indice}", "exec"), namespace)
                        ejecutadas.append(indice)
        finally:
            os.chdir(anterior)
            (DESTINO / "notebook_2_2.log").write_text(buffer.getvalue(), encoding="utf-8")
        informe["notebook"] = {"celdas_python_ejecutadas": ejecutadas,
                               "ejecucion": "Python en orden, directorio temporal",
                               "log": "notebook_2_2.log"}

        temporal_eval = cargar_modulo(
            "evaluador_temporal_revision",
            RAIZ / "seccion_2_3/pruebas/filtros_temporales/evaluar_candidatos_casos.py",
        )
        espectral_eval = cargar_modulo(
            "evaluador_espectral_revision",
            RAIZ / "seccion_2_4/pruebas/filtrado_espectral/evaluar_casos.py",
        )
        guardado = json.loads(
            (RAIZ / "seccion_2_4/resultados/resultados_2_4.json").read_text()
        )
        for numero in (1, 2, 3):
            carpeta = CASOS / f"caso_{numero}"
            archivo = carpeta / "muestras_exactas.npz"
            meta = json.loads((carpeta / "metadatos_prueba.json").read_text())
            config = configuraciones[f"caso_{numero}"]
            for campo in ("semilla", "fs_Hz", "N_bloque", "duracion_s",
                          "frecuencias_utiles_Hz", "tipo_ruido",
                          "frecuencia_interferencia_Hz", "banda_ruido_Hz",
                          "snr_objetivo_dB"):
                assert meta[campo] == config[campo], (numero, campo)
            assert meta["semilla"] == 202600 + numero
            errores_regeneracion = {}
            errores_wav = {}
            with np.load(archivo) as datos, np.load(
                trabajo / f"2_2_generacionsenales/pruebas/caso_{numero}/muestras_exactas.npz"
            ) as regenerados:
                assert int(datos["fs"]) == meta["fs_Hz"] == 8000
                for clave, nombre_wav in (
                    ("limpia", "01_referencia_limpia.wav"),
                    ("ruido", "02_ruido.wav"),
                    ("contaminada", "03_entrada_contaminada.wav"),
                ):
                    assert datos[clave].shape == (8192,)
                    assert np.all(np.isfinite(datos[clave]))
                    errores_regeneracion[clave] = float(np.max(
                        np.abs(datos[clave] - regenerados[clave])))
                    assert errores_regeneracion[clave] < 1e-12
                    fs_wav, pcm = wavfile.read(carpeta / nombre_wav)
                    assert fs_wav == 8000 and pcm.dtype == np.int16
                    assert pcm.shape == datos[clave].shape
                    esperado = np.int16(np.clip(datos[clave], -1, 1) * 32767)
                    assert np.array_equal(pcm, esperado)
                    errores_wav[clave] = float(np.max(np.abs(
                        pcm.astype(float) / 32767 - datos[clave])))
                limpia, ruido, entrada = (datos[k].copy() for k in
                                          ("limpia", "ruido", "contaminada"))
            error_suma = float(np.max(np.abs(limpia + ruido - entrada)))
            assert error_suma < 1e-14
            snr = float(10 * np.log10(np.sum(limpia**2) /
                                      np.sum((entrada - limpia)**2)))
            assert abs(snr - meta["snr_objetivo_dB"]) < 1e-10
            cargada_temporal = temporal_eval.cargar_caso(numero)
            cargada_espectral = espectral_eval.cargar_caso(numero)
            assert np.array_equal(cargada_temporal[0], limpia)
            assert np.array_equal(cargada_temporal[2], entrada)
            assert np.array_equal(cargada_espectral[0], limpia)
            assert np.array_equal(cargada_espectral[1], entrada)

            nuevo = espectral_eval.evaluar_caso(numero, guardar=False)
            previo = next(c for c in guardado["casos"] if c["caso"] == numero)
            diferencias_metricas = {}
            for metodo, metricas in nuevo["metodos"].items():
                diferencias_metricas[metodo] = {}
                for clave in ("mse", "snr_salida_db", "delta_snr_db"):
                    diferencia = abs(metricas[clave] - previo["metodos"][metodo][clave])
                    diferencias_metricas[metodo][clave] = diferencia
                    assert diferencia < 1e-10
            metodo = nuevo["metodo_elegido"]
            salida, _ = espectral_eval.filtrar_espectral(
                entrada, 8000, 1024, metodo, **espectral_eval.METODOS[metodo]
            )
            with np.load(RAIZ / f"seccion_2_4/resultados/caso_{numero}/salida_filtrada.npz") as d:
                error_salida = float(np.max(np.abs(salida - d["salida"])))
                assert error_salida < 1e-12
            informe["casos"].append({
                "caso": numero, "fs_Hz": 8000, "muestras": len(limpia),
                "semilla": meta["semilla"], "snr_entrada_db": snr,
                "sha256_npz": hashlib.sha256(archivo.read_bytes()).hexdigest(),
                "error_suma_max": error_suma,
                "errores_regeneracion_max": errores_regeneracion,
                "errores_cuantizacion_wav_max": errores_wav,
                "misma_entrada_ambos_evaluadores": True,
                "diferencias_metricas_espectrales": diferencias_metricas,
                "error_salida_espectral_guardada_max": error_salida,
                "metodo_espectral_elegido": metodo,
                "snr_salida_espectral_db": nuevo["metodos"][metodo]["snr_salida_db"],
            })

        for prueba in sorted((RAIZ / "seccion_2_3/pruebas/filtros_temporales").glob("test_*.py")):
            informe["pruebas_temporales"].append(ejecutar_comando(
                [prueba], trabajo, prueba.stem + ".log"))
        informe["evaluador_temporal"] = ejecutar_comando(
            [RAIZ / "seccion_2_3/pruebas/filtros_temporales/evaluar_candidatos_casos.py"],
            trabajo, "evaluador_temporal.log")
        informe["pruebas_espectrales"] = ejecutar_comando(
            ["-m", "unittest", "discover", "-s",
             RAIZ / "seccion_2_4/pruebas/filtrado_espectral", "-p", "test_*.py", "-v"],
            trabajo, "pruebas_espectrales.log")

    informe["estado"] = "verificaciones_completadas"
    (DESTINO / "verificacion.json").write_text(
        json.dumps(informe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Verificación completa: tres casos reproducibles, ocho scripts temporales y cuatro pruebas espectrales.")
    print(f"Evidencia: {DESTINO}")


if __name__ == "__main__":
    main()
