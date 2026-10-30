"""Reúne imágenes y tablas reproducibles para compilar informe.tex.

Ejecutar con el Python del entorno de simulación. Requiere Graphviz (dot).
Los diagramas compactos son resúmenes de los diagramas del receptor; sus
originales se conservan en avance_s12/diagramas/.
"""
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys

CARPETA = Path(__file__).resolve().parent
PROYECTO = CARPETA.parents[1]


def preparar():
    """Regenera resultados, reúne nueve figuras y exporta diagramas vectoriales."""
    if shutil.which("dot") is None:
        raise RuntimeError("Se necesita Graphviz (comando dot) para exportar los diagramas.")
    simulacion = PROYECTO / "simulacion"
    subprocess.run([sys.executable, "-m", "sim.informe"], cwd=simulacion, check=True)
    figuras = CARPETA / "figuras"
    figuras.mkdir(exist_ok=True)
    for origen in sorted((simulacion / "resultados" / "figuras").glob("*.png")):
        shutil.copy2(origen, figuras / origen.name)
    shutil.copy2(PROYECTO / "avance_s12" / "diagramas" / "montaje_prueba.png",
                 figuras / "montaje_prueba.png")
    for fuente in sorted((CARPETA / "diagramas").glob("*.dot")):
        subprocess.run(["dot", "-Tpdf", str(fuente), "-o", str(figuras / (fuente.stem + ".pdf"))],
                       check=True)

    resultados = simulacion / "resultados"
    dft = json.loads((resultados / "dft_fft.json").read_text(encoding="utf-8"))
    filas_dft = []
    for nombre, etiqueta in (("P1", "Tramo de P1"), ("aleatoria", "Aleatoria")):
        fila = dft[nombre]
        filas_dft.append(f"{etiqueta} & \\num{{{fila['error_max_rel']:.3g}}} & "
                         f"{1000 * fila['tiempo_dft_s']:.3f} & "
                         f"{1000 * fila['tiempo_fft_s']:.4f} \\\\")
    tabla_dft = (r"\begin{tabular}{lrrr}\toprule Señal & Error rel. & DFT (ms) & FFT (ms)\\\midrule"
                 + "\n" + "\n".join(filas_dft) + "\n" + r"\bottomrule\end{tabular}" + "\n")
    (CARPETA / "tabla_dft.tex").write_text(tabla_dft, encoding="utf-8")

    etiquetas = {"FIR decimación nodo 1": "FIR decimación (nodo 1)",
                 "FIR banda protegida nodo 2": "FIR protegido (nodo 2)",
                 "Notch IIR": "Notch IIR (nodo 2)",
                 "DFT directa": "DFT directa en PC", "Espectral nodo 3": "Espectral (nodo 3)"}
    with (resultados / "costo.csv").open(encoding="utf-8", newline="") as archivo:
        costos = list(csv.DictReader(archivo))
    filas_costo = []
    for fila in costos:
        latencia = "---" if fila["metodo"] == "DFT directa" else f"{float(fila['latencia_ms']):g} ms"
        mult = f"{float(fila['mult_por_segundo']):.12g}"
        filas_costo.append(f"{etiquetas[fila['metodo']]} & \\num{{{mult}}} & "
                           f"\\num{{{fila['memoria_bytes']}}} B & {latencia} \\\\")
    tabla_costo = (r"\begin{tabular}{lrrr}\toprule Método & Mult./s & Memoria & Latencia\\\midrule"
                   + "\n" + "\n".join(filas_costo) + "\n" + r"\bottomrule\end{tabular}" + "\n")
    (CARPETA / "tabla_costo.tex").write_text(tabla_costo, encoding="utf-8")
    print(f"\nImágenes y tablas del informe preparadas en {CARPETA}")


if __name__ == "__main__":
    preparar()
