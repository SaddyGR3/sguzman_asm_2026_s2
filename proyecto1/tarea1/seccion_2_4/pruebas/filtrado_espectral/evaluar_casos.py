"""Tarea 1, apartado 2.4: evalua los tres casos oficiales de 2.2.

Este archivo organiza el experimento; el algoritmo esta en ``src``. Se
cargan ``contaminada`` y ``limpia`` del mismo NPZ para evitar comparar con
versiones WAV cuantizadas. Solo ``contaminada`` entra a filtrar_espectral;
``limpia`` se consulta despues para calcular SNR, MSE y cambios de tono.

Se ejecutan los tres metodos en cada caso. El tipo de ruido registrado por
2.2 determina cual salida se guarda. El barrido adicional de alpha sobre el
caso 2 ilustra el requisito 2.4 f) de la Tarea 1.

Ejecutar desde cualquier directorio:
    python seccion_2_4/pruebas/filtrado_espectral/evaluar_casos.py
"""

import csv
import json
import sys
from pathlib import Path
from time import perf_counter

import numpy as np


SECCION = Path(__file__).resolve().parents[2]
REPOSITORIO = SECCION.parent
sys.path.insert(0, str(SECCION / "src"))

from filtrado_espectral import (  # noqa: E402
    atenuacion_db,
    energia_util_conservada,
    filtrar_espectral,
    mse,
    snr_db,
)


FS = 8000
N = 1024
CASOS = REPOSITORIO / "seccion_2_2" / "2_2_generacionsenales" / "pruebas"
RESULTADOS = SECCION / "resultados"

# Se configura una banda util, no el bin de 2150 Hz. ``picos`` debe encontrar
# la frecuencia interferente en la entrada; un cambio de frecuencia no exige
# cambiar la configuracion (ver prueba de tono desplazado).
# Los parametros son comunes a los tres casos para cada metodo.
METODOS = {
    "picos": {
        "umbral": 6.0,
        "ancho_bins": 6,
        "atenuacion_db": 60.0,
        "banda_util": (0.0, 1200.0),
    },
    "resta": {
        "alpha": 3.0,
        "g_min": 0.05,
        "proteger_tonos": True,
        "banda_util": (0.0, 1200.0),
        "umbral_tono": 2.5,
        "ancho_tono_bins": 1,
    },
    "top_k": {"k": 12},
}
SELECCION = {"tonal": "picos", "blanco": "resta", "banda": "resta"}


def cargar_caso(numero):
    """Carga y valida las muestras exactas y metadatos de un caso de 2.2.

    Devuelve ``limpia``, ``contaminada`` y metadatos. La señal ``ruido`` del
    NPZ no se utiliza: los filtros deben trabajar con la entrada observada,
    sin recibir por separado el ruido original.
    """
    carpeta = CASOS / f"caso_{numero}"
    with (carpeta / "metadatos_prueba.json").open(encoding="utf-8") as archivo:
        metadatos = json.load(archivo)
    with np.load(carpeta / "muestras_exactas.npz") as datos:
        if not {"limpia", "contaminada", "fs"}.issubset(datos.files):
            raise ValueError(f"Faltan arreglos en {carpeta / 'muestras_exactas.npz'}")
        limpia = datos["limpia"].copy()
        contaminada = datos["contaminada"].copy()
        fs = int(datos["fs"])
    if fs != FS or int(metadatos["fs_Hz"]) != FS:
        raise ValueError(f"Caso {numero}: frecuencia de muestreo incompatible")
    if limpia.ndim != 1 or contaminada.shape != limpia.shape:
        raise ValueError(f"Caso {numero}: dimensiones de las senales incompatibles")
    if not np.all(np.isfinite(limpia)) or not np.all(np.isfinite(contaminada)):
        raise ValueError(f"Caso {numero}: hay muestras no finitas")
    return limpia, contaminada, metadatos


def amplitudes_tonos(senal, frecuencias, fs):
    """Estima la amplitud de tonos conocidos solo para medir distorsion.

    Ajusta simultaneamente senos, cosenos y DC por minimos cuadrados.
    Esto evita leer un solo bin de FFT, que seria inexacto cuando un tono cae
    entre bins. Las frecuencias vienen de los metadatos y no se pasan al
    algoritmo de filtrado.
    """
    t = np.arange(len(senal)) / fs
    columnas = [np.ones(len(senal))]
    for frecuencia in frecuencias:
        columnas.extend((np.sin(2 * np.pi * frecuencia * t),
                         np.cos(2 * np.pi * frecuencia * t)))
    coeficientes = np.linalg.lstsq(np.column_stack(columnas), senal, rcond=None)[0]
    return {
        str(frecuencia): float(np.hypot(*coeficientes[1 + 2 * i:3 + 2 * i]))
        for i, frecuencia in enumerate(frecuencias)
    }


def reduccion_error_banda_db(limpia, entrada, salida, fs, limites):
    """Mide cuanta potencia de error se elimino dentro de una banda en Hz.

    El error es ``senal - limpia``. Se aplica Hann para reducir fuga al medir
    los extremos de banda. La referencia limpia se usa aqui para evaluar,
    despues de filtrar, no para crear las ganancias espectrales.
    """
    ventana = np.hanning(len(limpia))
    frecuencias = np.fft.rfftfreq(len(limpia), 1 / fs)
    banda = (frecuencias >= limites[0]) & (frecuencias <= limites[1])
    entrada_error = np.fft.rfft((entrada - limpia) * ventana)
    salida_error = np.fft.rfft((salida - limpia) * ventana)
    potencia_entrada = np.sum(np.abs(entrada_error[banda]) ** 2)
    potencia_salida = np.sum(np.abs(salida_error[banda]) ** 2)
    return float(10 * np.log10(potencia_entrada / max(potencia_salida, 1e-30)))


def atenuacion_fuera_tonos_db(entrada, salida, frecuencias_utiles, fs):
    """Mide la energia eliminada fuera de +/-20 Hz de cada tono util.

    En el caso 2 esa region contiene principalmente ruido blanco. Se usa
    como indicador de energia de ruido reducida en el barrido del inciso f).
    No se presenta como separacion perfecta de señal y ruido.
    """
    ventana = np.hanning(len(entrada))
    frecuencias = np.fft.rfftfreq(len(entrada), 1 / fs)
    fuera = np.ones(len(frecuencias), dtype=bool)
    for frecuencia in frecuencias_utiles:
        fuera &= np.abs(frecuencias - frecuencia) > 20
    potencia_entrada = np.sum(np.abs(np.fft.rfft(entrada * ventana)[fuera]) ** 2)
    potencia_salida = np.sum(np.abs(np.fft.rfft(salida * ventana)[fuera]) ** 2)
    return float(10 * np.log10(potencia_entrada / max(potencia_salida, 1e-30)))


def evaluar_compromiso():
    """Demuestra el inciso 2.4 f) variando una sola decision: ``alpha``.

    Se desactiva la proteccion tonal intencionalmente para mostrar el fallo
    que evita la configuracion elegida. Al aumentar alpha cae la energia
    fuera de los tonos, pero a partir de cierto punto tambien cae la amplitud
    del tono util y empeora el SNR. Esta ablacion es evidencia del compromiso,
    no es la salida propuesta para el caso 2.
    """
    limpia, contaminada, metadatos = cargar_caso(2)
    frecuencias = metadatos["frecuencias_utiles_Hz"]
    amplitud_limpia = amplitudes_tonos(limpia, frecuencias, FS)["1100"]
    filas = []
    for alpha in (0, 0.5, 1, 2, 3, 4, 8):
        salida, _ = filtrar_espectral(
            contaminada, FS, N, "resta", alpha=alpha, proteger_tonos=False
        )
        amplitud_salida = amplitudes_tonos(salida, frecuencias, FS)["1100"]
        filas.append({
            "alpha": alpha,
            "snr_salida_db": snr_db(limpia, salida),
            "mse": mse(limpia, salida),
            "atenuacion_fuera_tonos_db": atenuacion_fuera_tonos_db(
                contaminada, salida, frecuencias, FS
            ),
            "ganancia_1100_Hz_db": float(20 * np.log10(amplitud_salida / amplitud_limpia)),
        })
    return filas


def evaluar_caso(numero, guardar=True, carpeta_resultados=RESULTADOS):
    """Ejecuta los tres metodos y mide sus resultados sobre un caso oficial.

    La eleccion de salida usa ``tipo_ruido`` de los metadatos, antes de mirar
    las metricas. ``limpia`` no determina la seleccion ni modifica el filtro.
    Si ``guardar`` es verdadero, escribe solo la salida seleccionada en NPZ.
    """
    limpia, contaminada, metadatos = cargar_caso(numero)
    tipo = metadatos["tipo_ruido"]
    metodo_elegido = SELECCION[tipo]
    snr_entrada = snr_db(limpia, contaminada)
    amplitudes_limpias = amplitudes_tonos(
        limpia, metadatos["frecuencias_utiles_Hz"], FS
    )
    resultados = {}

    for metodo, parametros in METODOS.items():
        # El tiempo mide solo el filtro, no la carga de archivos ni metricas.
        inicio = perf_counter()
        salida, info = filtrar_espectral(contaminada, FS, N, metodo, **parametros)
        tiempo_ms = (perf_counter() - inicio) * 1000
        amplitudes_salida = amplitudes_tonos(
            salida, metadatos["frecuencias_utiles_Hz"], FS
        )
        resultado = {
            "snr_salida_db": snr_db(limpia, salida),
            "mse": mse(limpia, salida),
            "energia_salida_respecto_limpia_pct": energia_util_conservada(limpia, salida),
            "ganancia_tonos_db": {
                tono: float(20 * np.log10(amplitudes_salida[tono] / amplitudes_limpias[tono]))
                for tono in amplitudes_limpias
            },
            "fraccion_bins_modificados": info["fraccion_modificada"],
            "tiempo_ms": tiempo_ms,
        }
        if "tonos_protegidos_Hz" in info:
            resultado["tonos_protegidos_Hz"] = info["tonos_protegidos_Hz"]
        resultado["delta_snr_db"] = resultado["snr_salida_db"] - snr_entrada
        if tipo == "tonal":
            resultado["atenuacion_interferencia_db"] = atenuacion_db(
                contaminada, salida, FS, metadatos["frecuencia_interferencia_Hz"]
            )
        if tipo == "banda":
            resultado["reduccion_error_banda_db"] = reduccion_error_banda_db(
                limpia, contaminada, salida, FS, metadatos["banda_ruido_Hz"]
            )
        resultados[metodo] = resultado

        if guardar and metodo == metodo_elegido:
            destino = carpeta_resultados / f"caso_{numero}"
            destino.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(destino / "salida_filtrada.npz", salida=salida, fs=FS)

    return {
        "caso": numero,
        "tipo_ruido": tipo,
        "archivo_entrada": (CASOS / f"caso_{numero}" / "muestras_exactas.npz").relative_to(REPOSITORIO).as_posix(),
        "fs_Hz": FS,
        "N": N,
        "delta_f_Hz": FS / N,
        "hop": N // 2,
        "snr_entrada_db": snr_entrada,
        "metodo_elegido": metodo_elegido,
        "metodos": resultados,
    }


def main():
    """Regenera salidas NPZ, comparacion JSON y resumen CSV de la Tarea 1."""
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    casos = [evaluar_caso(i) for i in (1, 2, 3)]
    informe = {
        "configuracion_metodos": METODOS,
        "nota_metricas": "SNR y MSE directos contra limpia, sin compensar retardo; "
                         "la energia de salida incluye ruido residual.",
        "casos": casos,
        "compromiso_caso_2_sin_proteccion_tonal": evaluar_compromiso(),
    }
    with (RESULTADOS / "resultados_2_4.json").open("w", encoding="utf-8") as archivo:
        json.dump(informe, archivo, ensure_ascii=False, indent=2)
        archivo.write("\n")

    with (RESULTADOS / "resumen_2_4.csv").open("w", encoding="utf-8", newline="") as archivo:
        campos = ["caso", "tipo_ruido", "metodo", "snr_entrada_db", "snr_salida_db",
                  "delta_snr_db", "mse", "ganancia_1100_Hz_db"]
        escritor = csv.DictWriter(archivo, fieldnames=campos)
        escritor.writeheader()
        for caso in casos:
            for metodo, metricas in caso["metodos"].items():
                escritor.writerow({
                    "caso": caso["caso"],
                    "tipo_ruido": caso["tipo_ruido"],
                    "metodo": metodo,
                    "snr_entrada_db": caso["snr_entrada_db"],
                    "snr_salida_db": metricas["snr_salida_db"],
                    "delta_snr_db": metricas["delta_snr_db"],
                    "mse": metricas["mse"],
                    "ganancia_1100_Hz_db": metricas["ganancia_tonos_db"]["1100"],
                })

    for caso in casos:
        metodo = caso["metodo_elegido"]
        metricas = caso["metodos"][metodo]
        print(f"Caso {caso['caso']} ({caso['tipo_ruido']}): {metodo}; "
              f"SNR {caso['snr_entrada_db']:.2f} -> {metricas['snr_salida_db']:.2f} dB; "
              f"MSE {metricas['mse']:.6f}; tono 1100 Hz "
              f"{metricas['ganancia_tonos_db']['1100']:+.2f} dB")
    print(f"Resultados: {RESULTADOS}")


if __name__ == "__main__":
    main()
