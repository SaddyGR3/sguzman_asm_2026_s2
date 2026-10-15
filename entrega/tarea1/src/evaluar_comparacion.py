"""Evalúa los filtros existentes sin alterar datos ni algoritmos de 2.2–2.4.

Desde la carpeta del paquete: python src/evaluar_comparacion.py
El protocolo es la única fuente de parámetros. --sin-benchmark permite una
verificación rápida de calidad, exportando tiempos y pico de memoria como null.
"""

import argparse
import csv
import gc
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
from time import perf_counter_ns
import tracemalloc

import numpy as np
import scipy

from metricas import (
    atenuacion_banda_db, atenuacion_total_db, calidad, conservacion_pct,
    ganancias_tonos_db, recortar, serializable, vector_real,
)

RAIZ = Path(__file__).resolve().parents[1]
PROTOCOLO = RAIZ / "metadatos/protocolo.json"
RESULTADOS = RAIZ / "resultados/regenerados"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src"))

from filtros_temporales import aplicar_filtro_manual_bloque, disenar_fir_kaiser
from filtrado_espectral import _trocear, filtrar_espectral, ventana_sqrt_hann


def exigir(condicion, mensaje):
    # No usar assert en validaciones de entrada: también funcionan con -O.
    if not condicion:
        raise ValueError(mensaje)


def cargar_protocolo(ruta=PROTOCOLO):
    p = json.loads(Path(ruta).read_text(encoding="utf-8"))
    exigir(p["version"] == 1, "Versión de protocolo no soportada")
    exigir(p["dtype_real"] == "float64" and p["dtype_complejo"] == "complex128",
           "Esta referencia requiere float64/complex128")
    exigir(p["metodos_principales"] == ["entrada", "temporal_fir", "espectral"],
           "Métodos principales incompatibles")
    l, fs, n = p["muestras_captura"], p["fs_Hz"], p["bloque_nominal"]
    a, e, t = p["alineamiento_principal"], p["espectral"], p["temporal"]
    exigir(l > 0 and fs > 0 and n > 0 and l % n == 0, "Captura o bloque inválidos")
    exigir(e["N"] == n and n >= 4 and n & (n-1) == 0, "N debe ser potencia de dos")
    exigir(e["hop"] == n//2 and e["solape"] == 0.5 and
           e["ventana"] == "sqrt_hann_periodica", "Solape o ventana incompatibles")
    exigir(t["fs_Hz"] == fs and t["tipo"] == "fir_kaiser", "Diseño temporal incompatible")
    exigir(t["orden"] % 2 == 0 and t["retardo_muestras"] == t["orden"]//2,
           "Retardo incompatible con FIR simétrico")
    exigir(t["estado_inicial"] == "cero_por_captura" and
           t["conservar_estado_entre_bloques"], "Estados temporales incompatibles")
    exigir(a["referencia_inicio"] == 0 and a["K"] == l-t["retardo_muestras"] and
           a["referencia_fin_exclusivo"] == a["K"] and
           a["desplazamiento_por_metodo"] == {"entrada": 0, "temporal_fir": t["retardo_muestras"], "espectral": 0}
           and not a["descartar_transitorios_adicionales"], "Tramo de evaluación incompatible")
    exigir(p["evaluacion_directa"]["referencia_inicio"] == 0 and
           p["evaluacion_directa"]["referencia_fin_exclusivo"] == l and
           not p["evaluacion_directa"]["compensar_retardo"], "Evaluación directa incompatible")
    exigir(not p["energia_util"]["reestimar_ganancias_sobre_fuentes"] and
           not p["energia_util"]["limitar_a_100_pct"], "Criterio de energía incompatible")
    exigir(p["benchmark"]["repeticiones"] > 0 and p["benchmark"]["calentamientos"] >= 0 and
           p["benchmark"]["duracion_audio_s"] == l/fs and
           p["benchmark"]["bloques_nominales_equivalentes"] == l//n,
           "Configuración de benchmark inválida")
    exigir(len(p["columnas_csv_previstas"]) == len(set(p["columnas_csv_previstas"])),
           "Columnas CSV duplicadas")
    exigir([c["caso"] for c in p["casos"]] == [1, 2, 3] and
           len({c["semilla"] for c in p["casos"]}) == 3, "Casos o semillas incompatibles")
    return p


def cargar_caso(caso, p, raiz=RAIZ):
    archivo = Path(raiz) / caso["archivo"]
    exigir(hashlib.sha256(archivo.read_bytes()).hexdigest() == caso["sha256"],
           f"Caso {caso['caso']}: hash de las señales modificado")
    meta = json.loads(archivo.with_name("metadatos_prueba.json").read_text(encoding="utf-8"))
    generales = json.loads((Path(raiz) / "metadatos/configuraciones.json").read_text())
    config = generales[f"caso_{caso['caso']}"]
    for campo in ("semilla", "fs_Hz", "N_bloque", "duracion_s", "frecuencias_utiles_Hz",
                  "tipo_ruido", "frecuencia_interferencia_Hz", "banda_ruido_Hz", "snr_objetivo_dB"):
        exigir(meta[campo] == config[campo], f"Caso {caso['caso']}: metadato incompatible {campo}")
    with np.load(archivo, allow_pickle=False) as datos:
        exigir({"limpia", "ruido", "contaminada", "fs"}.issubset(datos.files), "NPZ incompleto")
        fuentes = {k: vector_real(datos[k]).copy() for k in ("limpia", "ruido", "contaminada")}
        exigir(int(datos["fs"]) == p["fs_Hz"] == meta["fs_Hz"], "Muestreo incompatible")
    exigir(meta["semilla"] == caso["semilla"] and meta["N_bloque"] == p["bloque_nominal"],
           "Semilla o bloque incompatibles")
    exigir(meta["duracion_s"] == p["muestras_captura"]/p["fs_Hz"] and
           meta["frecuencias_utiles_Hz"] == p["ganancia_tonos"]["frecuencias_Hz"],
           "Duración o tonos incompatibles")
    exigir(all(v.size == p["muestras_captura"] for v in fuentes.values()), "Longitud incompatible")
    exigir(np.max(np.abs(fuentes["limpia"]+fuentes["ruido"]-fuentes["contaminada"])) < 1e-14,
           "La mezcla no coincide con limpia + ruido")
    exigir(abs(calidad(fuentes["limpia"], fuentes["contaminada"])["snr_db"]-
               meta["snr_objetivo_dB"]) < 1e-10, "SNR original incompatible")
    exigir({"tonal": "picos", "blanco": "resta", "banda": "resta"}[meta["tipo_ruido"]] ==
           p["espectral"]["seleccion_por_caso"][str(caso["caso"])] , "Selección espectral incompatible")
    return fuentes, meta


def disenar_temporal(p):
    t = p["temporal"]
    b, a, orden = disenar_fir_kaiser(t["fs_Hz"], t["fp_Hz"], t["fstop_Hz"], t["atenuacion_diseno_db"])
    exigir(orden == t["orden"] and np.allclose(b, b[::-1], rtol=0, atol=1e-14),
           "El diseño no coincide con el orden y simetría declarados")
    return b, a


def temporal_por_bloques(x, b, a, n):
    estado, partes = None, []
    for inicio in range(0, len(x), n):
        salida, estado = aplicar_filtro_manual_bloque(x[inicio:inicio+n], b, a, estado)
        partes.append(salida)
    return np.concatenate(partes), {"estado": estado, "tramas": len(partes)}


def espectral_congelado(x, ganancias, n, hop):
    """Instrumentación de evaluación; no vuelve a estimar el piso ni tonos.

    Reutiliza el relleno y ventana de 2.4. Con ganancias fijas, restar y
    restaurar DC es lineal y permite separar contribuciones de las fuentes.
    """
    x = vector_real(x)
    bloques, pre, total = _trocear(x-x.mean(), n, hop)
    w = ventana_sqrt_hann(n)
    exigir(ganancias.shape == (bloques.shape[0], n//2+1) and
           np.all(np.isfinite(ganancias)), "Ganancias incompatibles con la captura")
    reconstruidos = np.fft.irfft(np.fft.rfft(bloques*w, axis=1)*ganancias, n=n, axis=1)*w
    salida = np.zeros(total)
    for i, bloque in enumerate(reconstruidos):
        salida[i*hop:i*hop+n] += bloque
    return salida[pre:pre+x.size] + x.mean()


def operaciones(p, numero, b, a):
    e = p["espectral"]
    metodo = e["seleccion_por_caso"][str(numero)]
    return {
        "temporal_fir": lambda x: temporal_por_bloques(x, b, a, p["bloque_nominal"]),
        "espectral": lambda x: filtrar_espectral(
            x, p["fs_Hz"], e["N"], metodo, solape=e["solape"], **e["parametros_por_metodo"][metodo]),
    }


def fila_calidad(numero, metodo, fuentes, salida, util, residual, p):
    a = p["alineamiento_principal"]
    inicio, fin = a["referencia_inicio"], a["referencia_fin_exclusivo"]
    d = a["desplazamiento_por_metodo"][metodo]
    s, x, r = (recortar(fuentes[k], inicio, fin) for k in ("limpia", "contaminada", "ruido"))
    y, ys, yr = (recortar(v, inicio, fin, d) for v in (salida, util, residual))
    entrada, resultado = calidad(s, x), calidad(s, y)
    directo_entrada = calidad(fuentes["limpia"], fuentes["contaminada"])
    directo = calidad(fuentes["limpia"], salida)
    banda = p["atenuacion"]["bandas_Hz_por_caso"][str(numero)]
    ganancias = ganancias_tonos_db(s, ys, p["fs_Hz"], p["ganancia_tonos"]["frecuencias_Hz"])
    fila = {
        "caso": numero, "metodo": metodo, "fs_Hz": p["fs_Hz"], "N": p["bloque_nominal"],
        "hop": p["espectral"]["hop"] if metodo == "espectral" else p["bloque_nominal"],
        "K_evaluacion": s.size, "retardo_compensado_muestras": d,
        "snr_entrada_db": entrada["snr_db"], "mse": resultado["mse"],
        "snr_salida_db": resultado["snr_db"], "delta_snr_db": resultado["snr_db"]-entrada["snr_db"],
        "energia_util_conservada_pct": conservacion_pct(s, ys),
        "energia_total_salida_pct": conservacion_pct(s, y),
        "atenuacion_ruido_total_db": atenuacion_total_db(r, yr),
        "banda_interferencia_inicio_Hz": None if banda is None else banda[0],
        "banda_interferencia_fin_Hz": None if banda is None else banda[1],
        "atenuacion_interferencia_banda_db": atenuacion_banda_db(r, yr, p["fs_Hz"], banda),
        "K_directo": fuentes["limpia"].size, "mse_directo": directo["mse"],
        "snr_entrada_directo_db": directo_entrada["snr_db"], "snr_salida_directo_db": directo["snr_db"],
        "delta_snr_directo_db": directo["snr_db"]-directo_entrada["snr_db"],
    }
    fila.update({f"ganancia_util_{f}_Hz_db": v for f, v in ganancias.items()})
    return fila


def evaluar_calidad(caso, p, b, a, raiz=RAIZ):
    fuentes, meta = cargar_caso(caso, p, raiz)
    x = fuentes["contaminada"]
    ops = operaciones(p, caso["caso"], b, a)
    senales = {"entrada": {"salida": x, "util": fuentes["limpia"], "residual": fuentes["ruido"]}}
    diagnosticos = {}
    for nombre, op in ops.items():
        y, info = op(x)
        exigir(y.shape == x.shape and np.all(np.isfinite(y)), f"Salida inválida: {nombre}")
        if nombre == "temporal_fir":
            util = op(fuentes["limpia"])[0]
            residual = op(fuentes["ruido"])[0]
            tramas = info["tramas"]
        else:
            e = p["espectral"]
            util = espectral_congelado(fuentes["limpia"], info["ganancias"], e["N"], e["hop"])
            residual = espectral_congelado(fuentes["ruido"], info["ganancias"], e["N"], e["hop"])
            tramas = info["ganancias"].shape[0]
            exigir(tramas == e["tramas_incluido_relleno"], "Número de tramas espectrales incompatible")
        error = float(np.max(np.abs(y-util-residual)))
        exigir(error < p["energia_util"]["tolerancia_descomposicion_abs"], "Descomposición inconsistente")
        senales[nombre] = {"salida": y, "util": util, "residual": residual}
        diagnosticos[nombre] = {"error_descomposicion_max": error, "tramas_procesadas": tramas}
        if nombre == "espectral":
            diagnosticos[nombre]["ganancias"] = info["ganancias"]
            diagnosticos[nombre]["metodo_2_4"] = p["espectral"]["seleccion_por_caso"][str(caso["caso"])]
    filas = [fila_calidad(caso["caso"], nombre, fuentes, **{
        "salida": senales[nombre]["salida"], "util": senales[nombre]["util"],
        "residual": senales[nombre]["residual"]}, p=p) for nombre in p["metodos_principales"]]
    identidad = filas[0]
    exigir(identidad["energia_util_conservada_pct"] == 100 and identidad["delta_snr_db"] == 0 and
           identidad["atenuacion_ruido_total_db"] == 0, "La referencia identidad no cumple invariantes")
    return filas, fuentes, meta, senales, diagnosticos, ops


def medir_tiempos(ops, x, p):
    cfg = p["benchmark"]
    nombres = list(ops)
    for _ in range(cfg["calentamientos"]):
        for nombre in nombres:
            ops[nombre](x)
    tiempos = {nombre: [] for nombre in nombres}
    for repeticion in range(cfg["repeticiones"]):
        orden = nombres if repeticion % 2 == 0 else nombres[::-1]
        for nombre in orden:
            inicio = perf_counter_ns()
            resultado = ops[nombre](x)
            elapsed_ms = (perf_counter_ns()-inicio)/1e6
            tiempos[nombre].append(elapsed_ms)
            del resultado
    return tiempos


def medir_pico(op, x):
    exigir(not tracemalloc.is_tracing(), "La medición requiere tracemalloc inactivo al entrar")
    gc.collect()
    tracemalloc.start()
    try:
        resultado = op(x)
        _, pico = tracemalloc.get_traced_memory()
        del resultado
    finally:
        tracemalloc.stop()
    return pico


def agregar_recursos(filas, diagnosticos, fuentes, ops, p, b, a, medir=True):
    tiempos = medir_tiempos(ops, fuentes["contaminada"], p) if medir else {}
    picos = {nombre: medir_pico(op, fuentes["contaminada"]) for nombre, op in ops.items()} if medir else {}
    for fila in filas:
        nombre = fila["metodo"]
        if nombre == "entrada":
            tramas, persistente, pico = 0, 0, 0
            mediana = p95 = maximo = 0.0
        else:
            tramas = diagnosticos[nombre]["tramas_procesadas"]
            # Coeficientes b,a y estado lógico x_prev/y_prev. El estado también
            # está incluido en el pico adicional: estas columnas no se suman.
            persistente = b.nbytes+a.nbytes+8*(len(b)+len(a)-2) if nombre == "temporal_fir" else 0
            pico = picos.get(nombre)
            muestras = tiempos.get(nombre)
            mediana = float(np.median(muestras)) if muestras else None
            p95 = float(np.percentile(muestras, 95)) if muestras else None
            maximo = float(np.max(muestras)) if muestras else None
        fila.update({
            "tiempo_captura_mediana_ms": mediana, "tiempo_captura_p95_ms": p95,
            "tiempo_captura_max_ms": maximo,
            "tiempo_equivalente_1024_mediana_ms": None if mediana is None else mediana/p["benchmark"]["bloques_nominales_equivalentes"],
            "razon_tiempo_audio": None if mediana is None else mediana/(1000*p["benchmark"]["duracion_audio_s"]),
            "tramas_procesadas": tramas,
            "tiempo_amortizado_trama_mediana_ms": None if mediana is None or tramas == 0 else mediana/tramas,
            "memoria_entrada_bytes": fuentes["contaminada"].nbytes,
            "memoria_persistente_bytes": persistente, "memoria_pico_trazada_adicional_bytes": pico,
        })
    return {"repeticiones_ms": tiempos, "picos_trazados_bytes": picos,
            "coeficientes_preasignados_bytes": {"temporal_fir": b.nbytes+a.nbytes, "espectral": 0}}


def exportar(filas, detalle, p, destino):
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    campos = p["columnas_csv_previstas"]
    for fila in filas:
        exigir(set(fila) == set(campos), "Las columnas no coinciden con el protocolo")
    with (destino / "metricas.csv").open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(serializable(filas))
    (destino / "resultados_2_5.json").write_text(
        json.dumps(serializable(detalle), indent=2, ensure_ascii=False, allow_nan=False)+"\n", encoding="utf-8")


def entorno_ejecucion():
    cpu = platform.processor()
    cpuinfo = Path("/proc/cpuinfo")
    if not cpu and cpuinfo.exists():
        for linea in cpuinfo.read_text().splitlines():
            if linea.startswith("model name"):
                cpu = linea.split(":", 1)[1].strip()
                break
    return {"python": platform.python_version(), "numpy": np.__version__,
            "scipy": scipy.__version__, "sistema": platform.platform(),
            "maquina": platform.machine(), "cpu": cpu or "no disponible",
            "cpu_logicas": os.cpu_count(), "interprete": sys.executable}


def ejecutar(protocolo=PROTOCOLO, destino=RESULTADOS, benchmark=True):
    p = cargar_protocolo(protocolo)
    b, a = disenar_temporal(p)
    filas, casos = [], []
    destino = Path(destino)
    for caso in p["casos"]:
        print(f"Caso {caso['caso']}: calidad, separación de fuentes y recursos…", flush=True)
        nuevas, fuentes, meta, senales, diagnosticos, ops = evaluar_calidad(caso, p, b, a)
        recursos = agregar_recursos(nuevas, diagnosticos, fuentes, ops, p, b, a, medir=benchmark)
        carpeta = destino / f"caso_{caso['caso']}"
        carpeta.mkdir(parents=True, exist_ok=True)
        arrays = dict(fuentes)
        for nombre, componentes in senales.items():
            if nombre != "entrada":
                arrays.update({f"{nombre}_{clave}": valor for clave, valor in componentes.items()})
        arrays["ganancias_espectrales"] = diagnosticos["espectral"].pop("ganancias")
        np.savez_compressed(carpeta / "senales_comparacion.npz", fs=p["fs_Hz"], **arrays)
        casos.append({"caso": caso["caso"], "sha256_entrada": caso["sha256"],
                      "metadatos": meta, "diagnosticos": diagnosticos, "recursos": recursos,
                      "archivo_senales": f"caso_{caso['caso']}/senales_comparacion.npz"})
        filas.extend(nuevas)
    detalle = {
        "estado": "evaluacion_completada", "benchmark_ejecutado": benchmark,
        "configuracion": p, "sha256_protocolo": hashlib.sha256(Path(protocolo).read_bytes()).hexdigest(),
        "entorno": entorno_ejecucion(),
        "sha256_codigo": {str(ruta.relative_to(RAIZ)): hashlib.sha256(ruta.read_bytes()).hexdigest()
                          for ruta in (Path(__file__), Path(__file__).with_name("metricas.py"),
                                       RAIZ / "src/filtros_temporales.py",
                                       RAIZ / "src/filtrado_espectral.py")},
        "coeficientes_temporales": {"b": b, "a": a}, "filas": filas, "casos": casos,
        "notas": [
            f"Calidad principal: {p['alineamiento_principal']['K']} muestras comunes, retardo FIR compensado; "
            f"directa: {p['muestras_captura']} muestras.",
            "Energía útil y ruido: operador condicionado a ganancias aprendidas únicamente de la mezcla.",
            "Espectral fuera de línea; tiempos de PC no validan tiempo real ni latencia en ESP32.",
            "Pico tracemalloc adicional: excluye entrada/coeficientes preasignados y puede omitir buffers nativos.",
            "Memoria persistente lógica FIR incluye a=[1] y estados; estados también incluidos en pico: no sumar columnas.",
            "Persistencia espectral cero fuera de la llamada; ventana, matrices y ganancias están en el pico.",
            "Tiempo por 1024 y por trama son promedios amortizados, no latencias medidas de streaming.",
        ],
    }
    exportar(filas, detalle, p, destino)
    for fila in filas:
        print(f"Caso {fila['caso']} {fila['metodo']}: SNR {fila['snr_salida_db']:.3f} dB; "
              f"energía útil {fila['energia_util_conservada_pct']:.3f} %")
    print(f"Resultados: {destino}")
    return detalle


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocolo", type=Path, default=PROTOCOLO)
    parser.add_argument("--salida", type=Path, default=RESULTADOS)
    parser.add_argument("--sin-benchmark", action="store_true")
    args = parser.parse_args()
    ejecutar(args.protocolo, args.salida, benchmark=not args.sin_benchmark)
