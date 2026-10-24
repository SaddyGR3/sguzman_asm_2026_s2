"""Deriva el análisis desde resultados guardados, sin ejecutar filtros."""
from pathlib import Path
import csv
import hashlib
import json
import numpy as np

RAIZ = Path(__file__).resolve().parents[2]


def main():
    archivos = [
        RAIZ / "seccion_2_5/resultados/metricas.csv",
        RAIZ / "seccion_2_5/resultados/resultados_2_5.json",
        RAIZ / "seccion_2_4/resultados/resultados_2_4.json",
    ]
    with archivos[0].open(newline="") as f:
        filas = list(csv.DictReader(f))
    casos = []
    for caso in (1, 2, 3):
        filas_caso = {r["metodo"]: r for r in filas if int(r["caso"]) == caso}
        fir, fft = filas_caso["temporal_fir"], filas_caso["espectral"]
        k = int(fir["K_evaluacion"])
        assert k == int(fft["K_evaluacion"]) == 8174
        archivo = RAIZ / f"seccion_2_5/resultados/caso_{caso}/senales_comparacion.npz"
        archivos.append(archivo)
        diagnosticos = {}
        with np.load(archivo) as z:
            s = z["limpia"][:k]
            bordes = np.zeros(k, dtype=bool)
            bordes[:512] = bordes[-512:] = True
            for metodo in ("temporal_fir", "espectral"):
                r = filas_caso[metodo]
                d = int(r["retardo_compensado_muestras"])
                y = z[f"{metodo}_salida"][d:d+k]
                u = z[f"{metodo}_util"][d:d+k]
                n = z[f"{metodo}_residual"][d:d+k]
                assert np.allclose(y, u+n, rtol=0, atol=1e-12)
                e = s-y
                mse = float(np.mean(e**2))
                assert np.isclose(mse, float(r["mse"]), rtol=1e-12, atol=1e-15)
                diagnosticos[metodo] = {
                    "mse_comun": mse,
                    "porcentaje_error_en_bordes": float(100*np.sum(e[bordes]**2)/np.sum(e**2)),
                    "mse_interior_diagnostico": float(np.mean(e[~bordes]**2)),
                    "mse_distorsion_util": float(np.mean((s-u)**2)),
                    "mse_ruido_residual": float(np.mean(n**2)),
                    "termino_cruzado_mse": float(-2*np.mean((s-u)*n)),
                }
        ganador = min((fir, fft), key=lambda r: float(r["mse"]))
        perdedor = fft if ganador is fir else fir
        casos.append({
            "caso": caso,
            "ganador_por_mse": ganador["metodo"],
            "ventaja_snr_db": float(ganador["snr_salida_db"])-float(perdedor["snr_salida_db"]),
            "razon_mse_perdedor_sobre_ganador": float(perdedor["mse"])/float(ganador["mse"]),
            "diagnosticos": diagnosticos,
        })
    previo = json.loads(archivos[2].read_text())
    salida = {
        "alcance": "Derivaciones de resultados existentes; no se ejecutan filtros ni benchmark.",
        "bordes_diagnosticos": {
            "muestras_por_extremo": 512,
            "porcentaje_intervalo": 100*1024/8174,
            "nota": "Diagnóstico exploratorio posterior; no cambia el intervalo principal ni la clasificación.",
        },
        "fuentes_sha256": {str(p.relative_to(RAIZ)): hashlib.sha256(p.read_bytes()).hexdigest() for p in archivos},
        "casos": casos,
        "ablacion_2_4": {
            "nota": "Caso 2, 8192 muestras, protección tonal desactivada; distinta configuración de la comparación principal.",
            "resultados": previo["compromiso_caso_2_sin_proteccion_tonal"],
        },
    }
    destino = Path(__file__).with_name("analisis_datos.json")
    destino.write_text(json.dumps(salida, indent=2, ensure_ascii=False, allow_nan=False)+"\n")
    print(f"Análisis derivado y MSE contrastado en los tres casos: {destino}")


if __name__ == "__main__":
    main()
