"""Pruebas con resultados conocidos y los tres casos oficiales."""

import copy
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scipy.signal import lfilter

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

import evaluar_comparacion as evaluador
from metricas import (
    atenuacion_banda_db, atenuacion_total_db, calidad, conservacion_pct,
    energia_banda, ganancias_tonos_db, recortar, serializable,
)


class MetricasConocidasTest(unittest.TestCase):
    def test_mse_snr_y_energia_util_no_cuentan_ruido(self):
        s = np.array([1., -1., 1., -1.])
        ruido = np.ones(4)
        y = s + ruido
        self.assertEqual(calidad(s, y), {"mse": 1., "snr_db": 0.})
        self.assertEqual(conservacion_pct(s, s), 100.)
        self.assertEqual(conservacion_pct(s, y), 200.)
        self.assertEqual(conservacion_pct(s, 2*s), 400.)
        self.assertAlmostEqual(atenuacion_total_db(ruido, ruido/2), 6.020599913279624)

    def test_alineamiento_fijo_recupera_secuencia_retardada(self):
        referencia = np.arange(1., 11.)
        retardada = np.concatenate((np.zeros(3), referencia[:-3]))
        alineada = recortar(retardada, 0, 7, retardo=3)
        np.testing.assert_array_equal(alineada, referencia[:7])
        self.assertEqual(calidad(referencia[:7], alineada)["mse"], 0.)
        self.assertGreater(calidad(referencia, retardada)["mse"], 0.)
        with self.assertRaises(ValueError):
            recortar(retardada, 0, 10, retardo=3)

    def test_energia_unilateral_respeta_parseval_par_e_impar(self):
        for k in (128, 129):
            x = np.random.default_rng(k).normal(size=k)
            w = 0.5-0.5*np.cos(2*np.pi*np.arange(k)/k)
            self.assertAlmostEqual(energia_banda(x, 8000, (0, 4000)), float(np.sum((x*w)**2)), places=11)
            self.assertAlmostEqual(atenuacion_banda_db(x, x/2, 8000, (0, 4000)), 6.020599913279624)
        self.assertIsNone(atenuacion_banda_db(x, x, 8000, None))

    def test_ajuste_tonos_entre_bins_y_ganancias_conocidas(self):
        fs, k = 8000, 8174
        t = np.arange(k)/fs
        frecuencias = [300, 700, 1100]
        s = sum(a*np.sin(2*np.pi*f*t+fase) for a, f, fase in
                zip([1, .55, .3], frecuencias, [.1, .2, .3])) + .07
        y = .5*s
        for ganancia in ganancias_tonos_db(s, y, fs, frecuencias).values():
            self.assertAlmostEqual(ganancia, -6.020599913279624, places=10)

    def test_ceros_no_finitos_y_referencia_invalida(self):
        s = np.ones(4)
        self.assertEqual(calidad(s, s)["snr_db"], float("inf"))
        self.assertEqual(atenuacion_total_db(s, np.zeros(4)), float("inf"))
        self.assertIsNone(atenuacion_total_db(np.zeros(4), np.zeros(4)))
        for ref, salida in ((np.zeros(4), s), (s, s[:2]), (s, np.full(4, np.nan))):
            with self.assertRaises(ValueError):
                calidad(ref, salida)
        texto = json.dumps(serializable([float("inf"), float("-inf"), float("nan")]), allow_nan=False)
        self.assertEqual(json.loads(texto), ["+inf", "-inf", None])


class IntegracionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = evaluador.cargar_protocolo()
        cls.b, cls.a = evaluador.disenar_temporal(cls.p)

    def test_rechaza_hash_modificado_y_protocolo_incoherente(self):
        caso = self.p["casos"][0]
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / caso["archivo"]
            ruta.parent.mkdir(parents=True)
            ruta.write_bytes((RAIZ / caso["archivo"]).read_bytes()+b"modificado")
            with self.assertRaisesRegex(ValueError, "hash"):
                evaluador.cargar_caso(caso, self.p, raiz=carpeta)
            protocolo = copy.deepcopy(self.p)
            protocolo["alineamiento_principal"]["desplazamiento_por_metodo"]["temporal_fir"] = 0
            archivo_p = Path(carpeta) / "protocolo.json"
            archivo_p.write_text(json.dumps(protocolo))
            with self.assertRaisesRegex(ValueError, "Tramo"):
                evaluador.cargar_protocolo(archivo_p)

    def test_rechaza_metadatos_modificados_aunque_npz_sea_original(self):
        caso = self.p["casos"][0]
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / caso["archivo"]
            ruta.parent.mkdir(parents=True)
            ruta.write_bytes((RAIZ / caso["archivo"]).read_bytes())
            meta = json.loads((RAIZ / caso["archivo"]).with_name("metadatos_prueba.json").read_text())
            meta["semilla"] += 1
            ruta.with_name("metadatos_prueba.json").write_text(json.dumps(meta))
            config = Path(carpeta) / "metadatos/configuraciones.json"
            config.parent.mkdir(parents=True)
            config.write_bytes((RAIZ / "metadatos/configuraciones.json").read_bytes())
            with self.assertRaisesRegex(ValueError, "metadato incompatible semilla"):
                evaluador.cargar_caso(caso, self.p, raiz=carpeta)

    def test_operador_congelado_identidad_y_linealidad(self):
        rng = np.random.default_rng(88)
        s, r = rng.normal(size=(2, 1333))
        n, hop = 256, 128
        tramas = int(np.ceil((len(s)+n-hop)/hop))
        identidad = np.ones((tramas, n//2+1))
        np.testing.assert_allclose(evaluador.espectral_congelado(s, identidad, n, hop), s, atol=1e-12, rtol=0)
        g = rng.uniform(.1, 1, size=identidad.shape)
        total = evaluador.espectral_congelado(s+r, g, n, hop)
        suma = evaluador.espectral_congelado(s, g, n, hop)+evaluador.espectral_congelado(r, g, n, hop)
        np.testing.assert_allclose(total, suma, atol=1e-12, rtol=0)

    def test_tres_casos_misma_referencia_y_filtros_originales(self):
        for caso in self.p["casos"]:
            with self.subTest(caso=caso["caso"]):
                with patch.object(evaluador, "filtrar_espectral", wraps=evaluador.filtrar_espectral) as espectral:
                    filas, fuentes, _, senales, diagnos, ops = evaluador.evaluar_calidad(caso, self.p, self.b, self.a)
                # La adaptación ocurre una sola vez, a partir de la mezcla.
                self.assertEqual(espectral.call_count, 1)
                np.testing.assert_array_equal(espectral.call_args.args[0], fuentes["contaminada"])
                np.testing.assert_allclose(senales["temporal_fir"]["salida"],
                                           lfilter(self.b, self.a, fuentes["contaminada"]), atol=1e-12, rtol=0)
                self.assertEqual({f["K_evaluacion"] for f in filas}, {8174})
                self.assertEqual(len({f["snr_entrada_db"] for f in filas}), 1)
                self.assertEqual(filas[0]["energia_util_conservada_pct"], 100)
                self.assertEqual(filas[0]["delta_snr_db"], 0)
                for nombre in ("temporal_fir", "espectral"):
                    self.assertLess(diagnos[nombre]["error_descomposicion_max"], 1e-12)
                self.assertEqual(diagnos["espectral"]["tramas_procesadas"], 17)
                if caso["caso"] == 2:
                    self.assertTrue(all(f["atenuacion_interferencia_banda_db"] is None for f in filas))
                # Exportación sin benchmark: conservar null en lugar de tiempos ficticios.
                evaluador.agregar_recursos(filas, diagnos, fuentes, ops, self.p, self.b, self.a, medir=False)
                with tempfile.TemporaryDirectory() as carpeta:
                    evaluador.exportar(filas, {"filas": filas, "infinito": float("inf")}, self.p, carpeta)
                    datos = json.loads((Path(carpeta)/"resultados_2_5.json").read_text())
                    self.assertEqual(datos["infinito"], "+inf")
                    self.assertIsNone(datos["filas"][1]["tiempo_captura_mediana_ms"])
                    with (Path(carpeta)/"metricas.csv").open() as f:
                        csv_filas = list(csv.DictReader(f))
                    self.assertEqual(len(csv_filas), 3)
                    self.assertEqual(csv_filas[1]["tiempo_captura_mediana_ms"], "")
                    self.assertEqual(float(csv_filas[1]["snr_salida_db"]), filas[1]["snr_salida_db"])


if __name__ == "__main__":
    unittest.main()
