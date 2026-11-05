"""Genera figuras y tablas desde el CSV/JSON/NPZ verificado de 2.5.

No ejecuta filtros ni repite el benchmark. Exporta PNG (300 dpi) y SVG.
La revisión visual de las figuras se realiza después de generarlas.
"""

import argparse
import csv
import hashlib
import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "tarea1-matplotlib"))

import matplotlib.pyplot as plt
import numpy as np

from metricas import atenuacion_banda_db, atenuacion_total_db, ganancias_tonos_db

RESULTADOS = Path(__file__).resolve().parents[1] / "resultados"
RAIZ = Path(__file__).resolve().parents[2]
COLORES = {"limpia": "#334155", "entrada": "#b45309", "temporal_fir": "#2563eb", "espectral": "#15803d"}
ETIQUETAS = {"limpia": "Referencia limpia", "entrada": "Sin filtrar", "temporal_fir": "FIR temporal", "espectral": "Espectral"}
NOMBRES_CASOS = {1: "Interferencia tonal a 2150 Hz", 2: "Ruido blanco gaussiano", 3: "Ruido superpuesto: 900–1300 Hz"}


def exigir(condicion, mensaje):
    if not condicion:
        raise ValueError(mensaje)


def comprobar_resultados(carpeta):
    """Recalcula calidad y energía desde las muestras; comprueba CSV y hashes."""
    d = json.loads((carpeta / "resultados_2_5.json").read_text(encoding="utf-8"))
    exigir(d["benchmark_ejecutado"], "Para las figuras completas, ejecutar primero el evaluador con benchmark")
    p = d["configuracion"]
    with (carpeta / "metricas.csv").open(encoding="utf-8", newline="") as archivo:
        lector = csv.DictReader(archivo)
        exigir(lector.fieldnames == p["columnas_csv_previstas"], "Columnas CSV incompatibles")
        csv_filas = list(lector)
    exigir(len(csv_filas) == len(d["filas"]) == 9, "Se requieren nueve filas")
    exigir({(f["caso"], f["metodo"]) for f in d["filas"]} ==
           {(c, m) for c in (1, 2, 3) for m in p["metodos_principales"]}, "Filas duplicadas o faltantes")
    for csv_fila, fila in zip(csv_filas, d["filas"]):
        for clave, valor in fila.items():
            texto = csv_fila[clave]
            if valor is None:
                exigir(texto == "", f"Celda no aplicable incompatible: {clave}")
            elif isinstance(valor, str):
                exigir(texto == valor, f"Texto incompatible: {clave}")
            else:
                exigir(float(texto) == valor, f"CSV/JSON difieren: {clave}")
    exigir(hashlib.sha256((RAIZ / "revision/paso_2/protocolo.json").read_bytes()).hexdigest() ==
           d["sha256_protocolo"], "El protocolo cambió después de evaluar")
    for ruta, sha in d["sha256_codigo"].items():
        exigir(hashlib.sha256((RAIZ / ruta).read_bytes()).hexdigest() == sha,
               f"El código evaluado cambió: {ruta}")
    senales, errores = {}, {}
    inicio = p["alineamiento_principal"]["referencia_inicio"]
    fin = p["alineamiento_principal"]["referencia_fin_exclusivo"]
    for caso in d["casos"]:
        numero = caso["caso"]
        fuente = next(c for c in p["casos"] if c["caso"] == numero)
        exigir(hashlib.sha256((RAIZ / fuente["archivo"]).read_bytes()).hexdigest() ==
               caso["sha256_entrada"] == fuente["sha256"], "Las señales oficiales cambiaron")
        with np.load(carpeta / caso["archivo_senales"], allow_pickle=False) as datos:
            arrays = {k: datos[k].copy() for k in datos.files}
        with np.load(RAIZ / fuente["archivo"], allow_pickle=False) as oficiales:
            for clave in ("limpia", "ruido", "contaminada", "fs"):
                exigir(np.array_equal(arrays[clave], oficiales[clave]), f"Fuente exportada alterada: {clave}")
        exigir(int(arrays["fs"]) == p["fs_Hz"], "Muestreo exportado incompatible")
        s, r = arrays["limpia"][inicio:fin], arrays["ruido"][inicio:fin]
        curvas = {"limpia": s}
        for fila in (f for f in d["filas"] if f["caso"] == numero):
            nombre = fila["metodo"]
            retardo = fila["retardo_compensado_muestras"]
            y_completa = arrays["contaminada"] if nombre == "entrada" else arrays[f"{nombre}_salida"]
            util = arrays["limpia"] if nombre == "entrada" else arrays[f"{nombre}_util"]
            residual = arrays["ruido"] if nombre == "entrada" else arrays[f"{nombre}_residual"]
            y = y_completa[inicio+retardo:fin+retardo]
            ys, yr = (v[inicio+retardo:fin+retardo] for v in (util, residual))
            exigir(y.shape == s.shape and s.size == fila["K_evaluacion"], "Tramo desigual")
            mse = float(np.mean((s-y)**2))
            snr = float(10*np.log10(np.sum(s*s)/np.sum((s-y)**2)))
            snr_entrada = float(10*np.log10(np.sum(s*s)/np.sum((s-curvas["entrada"])**2))) if "entrada" in curvas else snr
            limpia_completa = arrays["limpia"]
            mse_directo = float(np.mean((limpia_completa-y_completa)**2))
            snr_directo = float(10*np.log10(np.sum(limpia_completa**2)/np.sum((limpia_completa-y_completa)**2)))
            entrada_directa = float(10*np.log10(np.sum(limpia_completa**2)/np.sum((limpia_completa-arrays["contaminada"])**2)))
            energia_util = float(100*np.sum(ys*ys)/np.sum(s*s))
            energia_total = float(100*np.sum(y*y)/np.sum(s*s))
            error = float(np.max(np.abs(y_completa-util-residual)))
            exigir(error < p["energia_util"]["tolerancia_descomposicion_abs"], "Fuentes no suman la salida")
            banda = p["atenuacion"]["bandas_Hz_por_caso"][str(numero)]
            recalculadas = {"mse": mse, "snr_salida_db": snr, "snr_entrada_db": snr_entrada,
                            "delta_snr_db": snr-snr_entrada, "mse_directo": mse_directo,
                            "snr_salida_directo_db": snr_directo, "snr_entrada_directo_db": entrada_directa,
                            "delta_snr_directo_db": snr_directo-entrada_directa,
                            "energia_util_conservada_pct": energia_util,
                            "energia_total_salida_pct": energia_total,
                            "atenuacion_ruido_total_db": atenuacion_total_db(r, yr),
                            "atenuacion_interferencia_banda_db": atenuacion_banda_db(r, yr, p["fs_Hz"], banda)}
            recalculadas.update({f"ganancia_util_{f}_Hz_db": v for f, v in
                                ganancias_tonos_db(s, ys, p["fs_Hz"], p["ganancia_tonos"]["frecuencias_Hz"]).items()})
            diferencias = {}
            for clave, valor in recalculadas.items():
                if valor is None:
                    exigir(fila[clave] is None, f"Métrica no aplicable inconsistente: {clave}")
                else:
                    diferencia = abs(valor-fila[clave])
                    exigir(diferencia < 1e-10, f"Métrica no coincide con las muestras: {clave}")
                    diferencias[clave] = diferencia
            errores[f"caso_{numero}/{nombre}"] = {"error_descomposicion_max": error,
                                                 "diferencias_metricas": diferencias}
            curvas[nombre] = y
            if nombre != "entrada":
                tiempos = caso["recursos"]["repeticiones_ms"][nombre]
                exigir(len(tiempos) == p["benchmark"]["repeticiones"] and min(tiempos) > 0,
                       "Repeticiones de benchmark inconsistentes")
                for clave, valor in (("tiempo_captura_mediana_ms", np.median(tiempos)),
                                     ("tiempo_captura_p95_ms", np.percentile(tiempos, 95)),
                                     ("tiempo_captura_max_ms", np.max(tiempos))):
                    exigir(abs(float(valor)-fila[clave]) < 1e-10, "Estadística temporal inconsistente")
        senales[numero] = curvas
    return d, senales, errores


def psd_db(x, fs):
    """Periodograma Hann unilateral; piso solo para representación gráfica."""
    k = len(x)
    ventana = .5-.5*np.cos(2*np.pi*np.arange(k)/k)
    espectro = np.fft.rfft(x*ventana)
    potencia = np.abs(espectro)**2 / (fs*np.sum(ventana**2))
    potencia[1:-1 if k % 2 == 0 else None] *= 2
    return np.fft.rfftfreq(k, 1/fs), 10*np.log10(np.maximum(potencia, 1e-18))


def guardar(fig, carpeta, nombre):
    fig.savefig(carpeta / f"{nombre}.png", dpi=300, facecolor="white")
    fig.savefig(carpeta / f"{nombre}.svg", facecolor="white")
    plt.close(fig)
    return [f"figuras/{nombre}.png", f"figuras/{nombre}.svg"]


def figura_caso(numero, curvas, fs, carpeta):
    fig, axs = plt.subplots(3, 1, figsize=(11.5, 9.2), layout="constrained")
    fig.suptitle(f"Caso {numero} · {NOMBRES_CASOS[numero]}", fontsize=15, fontweight="bold")
    t = np.arange(len(curvas["limpia"])) / fs
    # Un tramo fijo en régimen interior, separado de los fades de 20 ms.
    seleccion = (t >= .1) & (t <= .12)
    for nombre in ("entrada", "temporal_fir", "espectral", "limpia"):
        axs[0].plot(t[seleccion]*1000, curvas[nombre][seleccion], color=COLORES[nombre],
                    label=ETIQUETAS[nombre], lw=1.25 if nombre != "limpia" else 1.5,
                    linestyle="--" if nombre == "limpia" else "-", alpha=.85)
        f, db = psd_db(curvas[nombre], fs)
        axs[1].plot(f, db, color=COLORES[nombre], lw=1, label=ETIQUETAS[nombre],
                    linestyle="--" if nombre == "limpia" else "-", alpha=.8)
    axs[0].set(title="Señal temporal: 100–120 ms, FIR alineado", xlabel="Tiempo de referencia (ms)", ylabel="Amplitud digital")
    axs[0].legend(ncol=4, loc="upper center", fontsize=8)
    axs[1].set(title="Espectro de las señales sobre las 8174 muestras comunes", xlabel="Frecuencia (Hz)",
               ylabel="PSD (dB re 1 amplitud²/Hz)", xlim=(0, fs/2), ylim=(-180, -10))
    for nombre in ("entrada", "temporal_fir", "espectral"):
        f, db = psd_db(curvas[nombre]-curvas["limpia"], fs)
        axs[2].plot(f, db, color=COLORES[nombre], lw=1, label=ETIQUETAS[nombre], alpha=.85)
    axs[2].set(title="Espectro del error: incluye ruido residual y distorsión", xlabel="Frecuencia (Hz)",
               ylabel="PSD del error (dB)", xlim=(0, fs/2), ylim=(-180, -10))
    axs[2].legend(ncol=3, loc="upper right", fontsize=8)
    for ax in axs:
        ax.grid(alpha=.2)
    return guardar(fig, carpeta, f"caso_{numero}_comparacion")


def serie(filas, metodo, campo):
    return np.array([next(f[campo] for f in filas if f["caso"] == c and f["metodo"] == metodo)
                     for c in (1, 2, 3)])


def figura_calidad(filas, carpeta):
    fig, axs = plt.subplots(2, 2, figsize=(11.5, 7.6), layout="constrained")
    fig.suptitle("Comparación común de calidad · FIR con retardo compensado", fontsize=14, fontweight="bold")
    x = np.arange(3)
    campos = [("snr_salida_db", "SNR de salida", "SNR (dB)"),
              ("mse", "Error cuadrático medio", "MSE (amplitud²), escala log"),
              ("delta_snr_db", "Mejora frente a la misma entrada", "ΔSNR (dB)"),
              ("atenuacion_ruido_total_db", "Reducción del ruido total separado", "Atenuación (dB)")]
    for ax, (campo, titulo, unidad) in zip(axs.flat, campos):
        for i, metodo in enumerate(("entrada", "temporal_fir", "espectral")):
            valores = serie(filas, metodo, campo)
            bars = ax.bar(x+(i-1)*.24, valores, width=.23, color=COLORES[metodo], label=ETIQUETAS[metodo])
            ax.bar_label(bars, labels=[f"{v:.1e}" if campo == "mse" else f"{v:.1f}" for v in valores],
                         fontsize=7, padding=3)
        ax.set(title=titulo, ylabel=unidad, xticks=x, xticklabels=["Caso 1", "Caso 2", "Caso 3"])
        if campo == "mse":
            ax.set_yscale("log")
            ax.set_ylim(1e-7, .3)
        else:
            ax.set_ylim(0, max(max(serie(filas, m, campo)) for m in ("entrada", "temporal_fir", "espectral"))*1.22)
        ax.grid(axis="y", alpha=.2)
    axs[0, 0].legend(fontsize=8)
    return guardar(fig, carpeta, "resumen_calidad")


def figura_energia(filas, carpeta):
    fig, axs = plt.subplots(1, 2, figsize=(11.5, 4.8), layout="constrained")
    fig.suptitle("Conservación útil · fuentes separadas con ganancias de la mezcla", fontsize=13, fontweight="bold")
    x = np.arange(3)
    for i, metodo in enumerate(("entrada", "temporal_fir", "espectral")):
        axs[0].plot(x, serie(filas, metodo, "energia_util_conservada_pct"), "o-",
                    color=COLORES[metodo], label=ETIQUETAS[metodo], lw=1.2)
        for j, f in enumerate((300, 700, 1100)):
            axs[1].plot(x+(j-1)*.15, serie(filas, metodo, f"ganancia_util_{f}_Hz_db"),
                        ["o", "s", "^"][j], color=COLORES[metodo],
                        label=f"{ETIQUETAS[metodo]} · {f} Hz" if metodo != "entrada" else None,
                        markersize=5, alpha=.85)
    axs[0].set(title="Energía útil conservada (eje ampliado)", ylabel="Energía respecto a limpia (%)", ylim=(98.6, 100.3))
    axs[1].set(title="Cambio de amplitud de cada tono útil", ylabel="Ganancia útil (dB)", ylim=(-.12, .03))
    axs[0].axhline(100, color="#94a3b8", lw=.7, ls="--")
    axs[1].axhline(0, color="#94a3b8", lw=.7, ls="--")
    axs[0].legend(fontsize=8)
    axs[1].legend(fontsize=7, ncol=2, loc="lower left")
    for ax in axs:
        ax.set_xticks(x, ["Caso 1", "Caso 2", "Caso 3"])
        ax.grid(alpha=.2)
    return guardar(fig, carpeta, "energia_y_tonos")


def figura_recursos(filas, entorno, carpeta):
    fig, axs = plt.subplots(1, 2, figsize=(11.5, 5.1), layout="constrained")
    fig.suptitle("Recursos medidos en PC · procesamiento de la captura completa", fontsize=13, fontweight="bold")
    x = np.arange(3)
    for i, metodo in enumerate(("temporal_fir", "espectral")):
        posicion = x+(i-.5)*.3
        mediana = serie(filas, metodo, "tiempo_equivalente_1024_mediana_ms")
        p95 = serie(filas, metodo, "tiempo_captura_p95_ms") / 8
        bars = axs[0].bar(posicion, mediana, width=.28, color=COLORES[metodo], label=ETIQUETAS[metodo])
        axs[0].scatter(posicion, p95, marker="_", s=150, color="#111827", zorder=3)
        axs[0].bar_label(bars, fmt="%.3f", fontsize=8,
                         padding=-14 if metodo == "temporal_fir" else 4,
                         color="white" if metodo == "temporal_fir" else "black")
        memoria = serie(filas, metodo, "memoria_pico_trazada_adicional_bytes") / 1024
        bars = axs[1].bar(posicion, memoria, width=.28, color=COLORES[metodo], label=ETIQUETAS[metodo])
        axs[1].bar_label(bars, fmt="%.1f", fontsize=8, padding=4)
    axs[0].set(title="Tiempo equivalente por 1024 muestras\nBarras: mediana; marcas negras: percentil 95", ylabel="Tiempo amortizado (ms)")
    axs[0].set_ylim(0, max(serie(filas, "temporal_fir", "tiempo_captura_p95_ms")/8)*1.2)
    axs[1].set(title="Pico adicional trazado durante la llamada\nExcluye entrada y coeficientes preasignados", ylabel="Asignaciones trazadas (KiB)")
    axs[1].set_ylim(0, max(serie(filas, "espectral", "memoria_pico_trazada_adicional_bytes")/1024)*1.18)
    for ax in axs:
        ax.set_xticks(x, ["Caso 1", "Caso 2", "Caso 3"])
        ax.grid(axis="y", alpha=.2)
        ax.legend(fontsize=8)
    fig.supxlabel(f"{entorno['cpu']} · 30 repeticiones · resultados de PC, no mediciones de ESP32", fontsize=8)
    return guardar(fig, carpeta, "recursos_pc")


def tabla(filas, columnas):
    lineas = ["| " + " | ".join(titulo for _, titulo, _ in columnas) + " |",
              "|" + "|".join("---" for _ in columnas) + "|"]
    for fila in filas:
        valores = []
        for clave, _, formato in columnas:
            valor = fila[clave]
            if valor is None:
                texto = "No aplica" if "banda" in clave else "Sin medición"
            elif clave == "metodo":
                texto = ETIQUETAS[valor]
            else:
                texto = format(valor, formato)
            valores.append(texto)
        lineas.append("| " + " | ".join(valores) + " |")
    return "\n".join(lineas)


def resumen_markdown(d):
    filas = d["filas"]
    comun = [("caso", "Caso", "d"), ("metodo", "Método", "")]
    calidad = tabla(filas, comun + [("snr_entrada_db", "SNR entrada (dB)", ".3f"),
        ("snr_salida_db", "SNR salida (dB)", ".3f"), ("delta_snr_db", "ΔSNR (dB)", ".3f"), ("mse", "MSE", ".6e")])
    energia = tabla(filas, comun + [("energia_util_conservada_pct", "Útil conservada (%)", ".3f"),
        ("energia_total_salida_pct", "Energía total (%)", ".3f"), ("atenuacion_ruido_total_db", "Ruido total: atenuación (dB)", ".3f"),
        ("atenuacion_interferencia_banda_db", "Interferencia en banda: atenuación (dB)", ".3f")])
    tonos = tabla(filas, comun + [(f"ganancia_util_{f}_Hz_db", f"Ganancia {f} Hz (dB)", ".4f") for f in (300, 700, 1100)])
    recursos = tabla(filas, comun + [("tiempo_equivalente_1024_mediana_ms", "Mediana por 1024 (ms)", ".3f"),
        ("tiempo_captura_p95_ms", "P95 captura (ms)", ".3f"), ("memoria_persistente_bytes", "Persistencia lógica (bytes)", "d"),
        ("memoria_pico_trazada_adicional_bytes", "Pico adicional trazado (bytes)", "d")])
    return f"""# Resultados comparativos verificados de 2.5

Tablas generadas desde `resultados_2_5.json` y contrastadas con `metricas.csv`
y las muestras NPZ. El redondeo se aplica solo a la presentación.

## Calidad reconstruida

8174 muestras comunes; FIR compensado 18 muestras; entrada y espectral sin
desplazamiento. La SNR de entrada se recalcula sobre ese mismo intervalo.

{calidad}

## Conservación útil y atenuación del ruido

La componente útil y el ruido residual se obtienen fijando las ganancias
aprendidas de la mezcla. La energía total incluye ruido; no se interpreta
como energía útil. Banda del caso 1: 2130–2170 Hz; caso 3: 900–1300 Hz.
El caso 2 no tiene una interferencia dominante única.

{energia}

## Ganancias de tonos útiles

Ajuste conjunto de senos, cosenos y DC sobre la componente útil separada.
Estos valores no son los de amplitud observada en la mezcla con ruido.

{tonos}

## Tiempo y memoria en PC

Equipo: {d['entorno']['cpu']}. Tres calentamientos y 30 repeticiones.
La mediana por 1024 muestras es el tiempo de captura dividido entre ocho;
el P95 corresponde a la captura completa. El método espectral usa 17 tramas
con relleno. El pico es adicional, excluye entrada y coeficientes previos y
puede omitir buffers nativos; no sumar las columnas de memoria. Entrada
float64: 65536 bytes. Persistencia espectral cero entre llamadas, con sus
matrices incluidas en el pico. Son implementaciones de PC: FIR con bucles
Python y espectral vectorizado en NumPy. No extrapolar estos tiempos a ESP32.

{recursos}

## Figuras

- [Caso 1](figuras/caso_1_comparacion.png).
- [Caso 2](figuras/caso_2_comparacion.png).
- [Caso 3](figuras/caso_3_comparacion.png).
- [Resumen de calidad](figuras/resumen_calidad.png).
- [Energía útil y tonos](figuras/energia_y_tonos.png).
- [Recursos de PC](figuras/recursos_pc.png).

Cada figura tiene una versión PNG de 300 dpi y una versión SVG. En los
espectros se usa un periodograma Hann unilateral sobre el tramo común,
sin quitar DC. Los ejes llegan hasta −180 dB; los valores inferiores se muestran
en ese piso solo en las gráficas, sin modificar las métricas.
El intervalo temporal ilustrado es 100–120 ms; no representa toda la captura.
El PSD del error incluye ruido y distorsión.

La decisión por caso y las condiciones de fallo se explican en el informe PDF.
El algoritmo espectral permanece fuera de línea. La comparación directa
sobre 8192 muestras se conserva en CSV/JSON, separada de estas tablas.
"""


def generar(carpeta=RESULTADOS):
    carpeta = Path(carpeta)
    d, senales, errores = comprobar_resultados(carpeta)
    destino = carpeta / "figuras"
    destino.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "none"})
    archivos = []
    for numero, curvas in senales.items():
        archivos.extend(figura_caso(numero, curvas, d["configuracion"]["fs_Hz"], destino))
    archivos.extend(figura_calidad(d["filas"], destino))
    archivos.extend(figura_energia(d["filas"], destino))
    if d["benchmark_ejecutado"]:
        archivos.extend(figura_recursos(d["filas"], d["entorno"], destino))
    (carpeta / "resumen_2_5.md").write_text(resumen_markdown(d), encoding="utf-8")
    auditoria = {"estado_numerico": "verificado", "revision_visual": "pendiente",
                 "filas_csv_json_verificadas": len(d["filas"]), "errores": errores,
                 "sha256_graficador": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 "sha256_resultados_json": hashlib.sha256((carpeta / "resultados_2_5.json").read_bytes()).hexdigest(),
                 "sha256_figuras": {a: hashlib.sha256((carpeta/a).read_bytes()).hexdigest() for a in archivos}}
    (carpeta / "revision_figuras.json").write_text(json.dumps(auditoria, indent=2, ensure_ascii=False)+"\n")
    print(f"Verificados nueve registros; generadas {len(archivos)//2} figuras PNG/SVG y cuatro tablas.")
    print(f"Resultados: {carpeta}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resultados", type=Path, default=RESULTADOS)
    args = parser.parse_args()
    generar(args.resultados)
