"""Compara entrada, nodo 2 y nodo 3 contra la misma referencia de 8 kHz.

Ejecutar ``python -m sim.comparacion`` desde proyecto1/simulacion para
regenerar las tablas de P1–P5 y una figura temporal/espectral por prueba.
"""

import csv
import json
from pathlib import Path

import numpy as np

from sim import analogico, nodo2, nodo3, senales
from sim import metricas


RAIZ = Path(__file__).resolve().parents[1]
COLUMNAS = ("prueba", "nivel", "semilla", "ruta", "retardo_muestras", "mse",
            "snr_dB", "delta_snr_dB", "energia_util_pct", "atenuacion_total_dB",
            "atenuacion_banda_dB", "ganancias_tonos_dB")
METRICAS_NUMERICAS = ("retardo_muestras", "mse", "snr_dB", "delta_snr_dB",
                      "energia_util_pct", "atenuacion_total_dB", "atenuacion_banda_dB")


def cargar_configuraciones():
    """Reúne las cuatro configuraciones existentes y la nueva del nodo 3."""
    return {"pruebas": senales.cargar_config(),
            "analogica": analogico.cargar_config_analogica(),
            "nodo2": nodo2.cargar_config_nodo2(),
            "nodo3": nodo3.cargar_config_nodo3()}


def correr_caso(configs, prueba, semilla, nivel=None):
    """Genera una condición y calcula ambas rutas sobre idéntica entrada x8.

    El notch recibe la frecuencia declarada en P1/P5: sustituye en esta
    simulación la futura detección del nodo 1. Cada filtro del nodo 2 también
    se aplica por separado a s8 para distinguir ruido residual de señal útil.
    """
    config = configs["pruebas"]
    cfg_prueba = config["pruebas"][prueba]
    fs, N, H = (config["global"][clave] for clave in ("fs_Hz", "N", "H"))
    caso = senales.generar_caso(config, prueba, semilla)
    entrada = analogico.entrada_nodo1(caso["x"], caso["s"], configs["analogica"])
    x8, s8 = entrada["x"], entrada["s"]

    f0 = cfg_prueba.get("frecuencia_notch_Hz", cfg_prueba["ruido"].get("frecuencia_Hz"))
    q = None if nivel is None else nivel["q_notch"]
    b, a = nodo2.disenar_filtro_nodo2(cfg_prueba, configs["nodo2"], fs, f0_Hz=f0, q=q)
    y2 = nodo2.filtrar_por_bloques(b, a, x8, H)
    y2_s = nodo2.filtrar_por_bloques(b, a, s8, H)
    retardo2 = (len(b) - 1) // 2 if len(a) == 1 else 0

    metodo, alfa, proteccion = nodo3.parametros_nodo3(cfg_prueba, configs["nodo3"], nivel)
    resultado3 = nodo3.filtrar_espectral_causal(
        x8, metodo, cfg_prueba["banda_protegida_Hz"], configs["nodo3"],
        fs, N, H, alfa=alfa, proteccion=proteccion)
    y3_s = nodo3.aplicar_ganancias(s8, resultado3["G"], N, H)
    return {"s8": s8, "x8": x8, "y2": y2, "y2_s": y2_s,
            "y3": resultado3["y"], "y3_s": y3_s, "G": resultado3["G"],
            "retardo2": retardo2, "retardo3": nodo3.retardo_espectral(H),
            "tramas_calentamiento": resultado3["tramas_calentamiento"]}


def metricas_ruta(s8, x8, y, y_s, retardo, i0, i1, fs, banda, tonos):
    """Mide una ruta alineada sin estimar ni ocultar su retardo declarado.

    x8-s8 es el ruido en la entrada; y-y_s es la parte que deja pasar la ruta
    al aplicarle exactamente el mismo filtro o las mismas ganancias a s8.
    El tramo de s8 y x8 queda fijo; solo se desplaza el tramo de la salida.
    """
    s = metricas.recortar(s8, i0, i1)
    x = metricas.recortar(x8, i0, i1)
    salida = metricas.recortar(y, i0, i1, retardo)
    util = metricas.recortar(y_s, i0, i1, retardo)
    ruido = x - s
    residual = salida - util
    calidad = metricas.calidad(s, salida)
    snr_entrada = metricas.calidad(s, x)["snr_db"]
    return {"mse": calidad["mse"],
            "snr_dB": calidad["snr_db"],
            "delta_snr_dB": calidad["snr_db"] - snr_entrada,
            "energia_util_pct": metricas.conservacion_pct(s, util),
            "atenuacion_total_dB": metricas.atenuacion_total_db(ruido, residual),
            "atenuacion_banda_dB": metricas.atenuacion_banda_db(ruido, residual, fs, banda),
            "ganancias_tonos_dB": metricas.ganancias_tonos_db(s, util, fs, tonos)
                                   if tonos else {}}


def comparar_todo(configs):
    """Devuelve una fila por ruta para cada semilla y nivel de P1–P5."""
    config = configs["pruebas"]
    fs = config["global"]["fs_Hz"]
    evaluacion = configs["nodo3"]["evaluacion"]
    i0 = round(evaluacion["inicio_s"] * fs)
    i1 = round(evaluacion["fin_s"] * fs)
    filas = []
    for prueba, cfg in config["pruebas"].items():
        senal = cfg["senal"]
        tonos = ([senal["frecuencia_Hz"]] if senal["tipo"] == "tono" else
                 senal["frecuencias_Hz"] if senal["tipo"] == "multitono" else [])
        for nivel in cfg.get("barrido", [None]):
            for semilla in cfg["semillas"]:
                caso = correr_caso(configs, prueba, semilla, nivel)
                rutas = (("entrada", caso["x8"], caso["s8"], 0),
                         ("nodo2", caso["y2"], caso["y2_s"], caso["retardo2"]),
                         ("nodo3", caso["y3"], caso["y3_s"], caso["retardo3"]))
                for nombre, y, y_s, retardo in rutas:
                    medidas = metricas_ruta(caso["s8"], caso["x8"], y, y_s, retardo,
                                           i0, i1, fs, cfg["banda_atenuacion_Hz"], tonos)
                    medidas["ganancias_tonos_dB"] = json.dumps(
                        medidas["ganancias_tonos_dB"], ensure_ascii=False)
                    filas.append({"prueba": prueba, "nivel": "" if nivel is None else nivel["nivel"],
                                  "semilla": semilla, "ruta": nombre,
                                  "retardo_muestras": retardo, **medidas})
    return filas


def resumir(filas):
    """Agrupa tres semillas por prueba, nivel y ruta; desviación muestral."""
    grupos = {}
    for fila in filas:
        clave = fila["prueba"], fila["nivel"], fila["ruta"]
        grupos.setdefault(clave, []).append(fila)
    resumen = []
    for (prueba, nivel, ruta), grupo in grupos.items():
        fila = {"prueba": prueba, "nivel": nivel, "ruta": ruta, "n": len(grupo)}
        for nombre in METRICAS_NUMERICAS:
            valores = [float(item[nombre]) for item in grupo if item[nombre] is not None]
            fila[f"{nombre}_media"] = float(np.mean(valores)) if valores else None
            fila[f"{nombre}_desv"] = (float(np.std(valores, ddof=1))
                                      if len(valores) > 1 else None)
        resumen.append(fila)
    return resumen


def figura_prueba(caso, prueba, destino, fs, i0, i1):
    """Guarda señal temporal y espectro con las tres rutas alineadas."""
    # Solo se carga matplotlib al pedir figuras; las pruebas numéricas no lo necesitan.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (eje_t, eje_f) = plt.subplots(2, 1, figsize=(11, 7), constrained_layout=True)
    inicio = round(5 * fs)
    fin = inicio + round(0.04 * fs)
    tiempo = np.arange(inicio, fin) / fs
    rutas = (("limpia (s)", caso["s8"], 0),
             ("contaminada (x)", caso["x8"], 0),
             ("nodo 2", caso["y2"], caso["retardo2"]),
             ("nodo 3", caso["y3"], caso["retardo3"]))
    for nombre, senal, retardo in rutas:
        eje_t.plot(tiempo, senal[inicio + retardo:fin + retardo], label=nombre)
        tramo = senal[i0 + retardo:i1 + retardo]
        ventana = np.hanning(tramo.size + 1)[:-1]  # Hann periódica
        espectro = np.abs(np.fft.rfft(tramo * ventana))
        frecuencias = np.fft.rfftfreq(tramo.size, 1 / fs)
        # Piso numérico únicamente para dibujar magnitudes exactamente nulas.
        eje_f.plot(frecuencias, 20 * np.log10(np.maximum(espectro, 1e-10)), label=nombre)
    eje_t.set(title=f"{prueba}: señales alineadas", xlabel="Tiempo (s)")
    eje_t.set_ylabel("Amplitud normalizada")
    eje_t.grid(True)
    eje_t.legend()
    eje_f.set(title="Espectro del tramo de evaluación", xlabel="Frecuencia (Hz)",
              ylabel="Magnitud (dB)")
    eje_f.set_xlim(0, fs / 2)
    eje_f.set_ylim(bottom=-100)  # El piso de -200 dB es solo numérico y no aporta a la comparación.
    eje_f.grid(True)
    eje_f.legend()
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=150)
    plt.close(fig)


def _escribir_csv(ruta, filas, columnas):
    """Escribe columnas en orden estable para el informe y otros scripts."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(filas)


if __name__ == "__main__":
    configuraciones = cargar_configuraciones()
    filas = comparar_todo(configuraciones)
    resumen = resumir(filas)
    salida = RAIZ / "resultados"
    _escribir_csv(salida / "comparacion.csv", filas, COLUMNAS)
    columnas_resumen = ("prueba", "nivel", "ruta", "n") + tuple(
        columna for nombre in METRICAS_NUMERICAS
        for columna in (f"{nombre}_media", f"{nombre}_desv"))
    _escribir_csv(salida / "comparacion_resumen.csv", resumen, columnas_resumen)
    config = configuraciones["pruebas"]
    fs = config["global"]["fs_Hz"]
    evaluacion = configuraciones["nodo3"]["evaluacion"]
    i0, i1 = (round(evaluacion[clave] * fs) for clave in ("inicio_s", "fin_s"))
    for prueba, cfg in config["pruebas"].items():
        nivel = next((n for n in cfg.get("barrido", []) if n["nivel"] == "referencia"), None)
        caso = correr_caso(configuraciones, prueba, cfg["semillas"][0], nivel)
        figura_prueba(caso, prueba, salida / "figuras" / f"{prueba}.png", fs, i0, i1)
    print("Prueba  Nivel        Entrada Delta SNR   Nodo 2 Delta SNR   Nodo 3 Delta SNR (dB)")
    for prueba, cfg in config["pruebas"].items():
        for nivel in cfg.get("barrido", [None]):
            nombre_nivel = "" if nivel is None else nivel["nivel"]
            valores = {fila["ruta"]: fila["delta_snr_dB_media"] for fila in resumen
                       if fila["prueba"] == prueba and fila["nivel"] == nombre_nivel}
            print(f"{prueba:7} {nombre_nivel:12} {valores['entrada']:12.2f} "
                  f"{valores['nodo2']:13.2f} {valores['nodo3']:13.2f}")
