"""Pruebas de reconstruccion, simetria y casos oficiales de 2.4."""

import sys
import unittest
from pathlib import Path

import numpy as np


SECCION = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SECCION / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from evaluar_casos import METODOS, SELECCION, cargar_caso, evaluar_compromiso  # noqa: E402
from filtrado_espectral import (  # noqa: E402
    atenuacion_db,
    filtrar_espectral,
    snr_db,
    verificar_simetria_conjugada,
)


class FiltradoEspectralTest(unittest.TestCase):
    def test_identidad_y_simetria(self):
        _, contaminada, _ = cargar_caso(1)
        salida, _ = filtrar_espectral(contaminada, 8000, 1024, "top_k", k=513)
        self.assertLess(np.max(np.abs(salida - contaminada)), 1e-12)
        error_imaginario = verificar_simetria_conjugada(
            contaminada[:1024], np.ones(513)
        )
        self.assertLess(error_imaginario, 1e-12)

    def test_mejora_en_los_tres_casos_oficiales(self):
        mejoras_minimas = {1: 20, 2: 10, 3: 8}
        for numero, mejora_minima in mejoras_minimas.items():
            with self.subTest(caso=numero):
                limpia, contaminada, metadatos = cargar_caso(numero)
                metodo = SELECCION[metadatos["tipo_ruido"]]
                salida, info = filtrar_espectral(contaminada, 8000, 1024, metodo, **METODOS[metodo])
                self.assertEqual(salida.shape, contaminada.shape)
                self.assertTrue(np.all(np.isfinite(salida)))
                self.assertGreater(
                    snr_db(limpia, salida) - snr_db(limpia, contaminada), mejora_minima
                )
                if numero == 3:
                    self.assertTrue(any(
                        abs(frecuencia - 1100) < 8000 / 1024
                        for frecuencia in info["tonos_protegidos_Hz"]
                    ))

    def test_compromiso_ruido_y_distorsion(self):
        filas = evaluar_compromiso()
        por_alpha = {fila["alpha"]: fila for fila in filas}
        self.assertGreater(
            por_alpha[8]["atenuacion_fuera_tonos_db"],
            por_alpha[2]["atenuacion_fuera_tonos_db"],
        )
        self.assertLess(por_alpha[8]["snr_salida_db"], por_alpha[2]["snr_salida_db"])
        self.assertLess(por_alpha[8]["ganancia_1100_Hz_db"], -10)

    def test_rechazo_sigue_a_la_interferencia_sin_bin_fijo(self):
        """La misma configuracion debe funcionar al mover el tono interferente."""
        limpia, contaminada, _ = cargar_caso(1)
        potencia_ruido = np.mean((contaminada - limpia) ** 2)
        amplitud = np.sqrt(2 * potencia_ruido)
        tiempo = np.arange(len(limpia)) / 8000
        for frecuencia in (2150, 2350):
            with self.subTest(frecuencia=frecuencia):
                entrada = limpia + amplitud * np.sin(2 * np.pi * frecuencia * tiempo)
                salida, _ = filtrar_espectral(
                    entrada, 8000, 1024, "picos", **METODOS["picos"]
                )
                self.assertGreater(
                    atenuacion_db(entrada, salida, 8000, frecuencia), 40
                )


if __name__ == "__main__":
    unittest.main()
