"""Pruebas de la ventana nativa sin abrir puertos ni controlar hardware."""
import copy
import csv
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

if importlib.util.find_spec('PySide6') is None:
    raise unittest.SkipTest('La interfaz de escritorio requiere PySide6')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication, QFileDialog, QScrollArea
from escritorio.ventana import VentanaBanco
from panel_frenado import Banco
import banco_frenado


class BancoFalso:
    def __init__(self):
        self.secuencia = 0
        self.ordenes = []
        self.desconexiones = 0
        self.estado = dict(activo=False, fuente='SIN CONEXION', ultimo={}, historia=[],
                           eventos=[], curva='lineal', carpeta='', sensor={})

    def estado_actual(self):
        return copy.deepcopy(self.estado)

    def enviar(self, comando):
        self.ordenes.append(comando)

    def desconectar(self):
        self.desconexiones += 1
        self.estado['activo'] = False

    def iniciar(self, opciones):
        raise OSError('Puerto de prueba no disponible')


class PruebasEscritorio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def esperar(self, condicion, ventana=None, segundos=6):
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            self.app.processEvents()
            if ventana:
                ventana.actualizar()
            if condicion():
                return
            time.sleep(.01)
        raise AssertionError('La ventana no llegó al estado esperado')

    def crear(self, banco=None):
        ventana = VentanaBanco(banco=banco or BancoFalso(), busqueda=lambda: {'puertos': []}, temporizadores=False)
        self.addCleanup(self.limpiar, ventana)
        return ventana

    def limpiar(self, ventana):
        self.esperar(lambda: not ventana._trabajos, segundos=8)
        ventana._espera_cancelacion = None
        if isinstance(ventana.banco, BancoFalso):
            ventana.banco.estado['activo'] = False
            ventana.banco.estado['ultimo'] = {}
        else:
            ventana.banco.desconectar()
        ventana.close()
        self.app.processEvents()

    def test_seleccion_usb_no_abre_ni_elige_entre_varios(self):
        ventana = self.crear()
        ventana.mostrar_puertos({'puertos': ['/dev/ttyUSB0']})
        self.assertEqual(ventana.puerto.currentText(), '/dev/ttyUSB0')
        ventana.mostrar_puertos({'puertos': ['/dev/ttyUSB1', '/dev/ttyUSB2']})
        self.assertEqual(ventana.puerto.currentText(), '')
        ventana.puerto.setCurrentText('/dev/ttyUSB2')
        ventana.mostrar_puertos({'puertos': ['/dev/ttyUSB1', '/dev/ttyUSB2']})
        self.assertEqual(ventana.puerto.currentText(), '/dev/ttyUSB2')
        self.assertEqual(ventana.banco.ordenes, [])
        self.assertFalse(ventana.banco.estado['activo'])

    def test_distribucion_paralela_y_diagnostico_completo(self):
        ventana = self.crear()
        ventana.fuente.setCurrentIndex(1)
        ventana.show()
        for ancho in (1080, 1440):
            ventana.resize(ancho, 940)
            self.app.processEvents()
            ganancias = list(ventana.ganancias.values())
            self.assertEqual(len({campo.y() for campo in ganancias}), 1)
            self.assertEqual([campo.x() for campo in ganancias], sorted(campo.x() for campo in ganancias))
            for campo in ganancias:
                self.assertGreater(campo.lineEdit().width(), 40)
            cajas = ventana.cajas_diagnostico
            self.assertEqual(len({caja.y() for caja in cajas}), 1)
            self.assertLess(cajas[0].x(), cajas[1].x())
            self.assertLess(cajas[1].x(), cajas[2].x())
            self.assertEqual(len(ventana.etiquetas_diagnostico), 15)
            self.assertFalse(cajas[0].findChildren(QScrollArea))
            for etiqueta in ventana.etiquetas_diagnostico.values():
                self.assertTrue(cajas[0].rect().contains(etiqueta.geometry()))

    def test_error_conexion_libera_controles(self):
        ventana = self.crear()
        ventana.puerto.setCurrentText('/dev/puerto-de-prueba')
        ventana.conectar()
        self.esperar(lambda: not ventana._trabajos)
        self.assertIn('Puerto de prueba no disponible', ventana.aviso.text())
        self.assertTrue(ventana.boton_conectar.isEnabled())

    def test_exponencial_esp32(self):
        banco = BancoFalso()
        banco.estado.update(activo=True, fuente='ESP32', ultimo={'modo': 'REPOSO'}, curva=None)
        ventana = self.crear(banco)
        ventana.actualizar()
        self.assertTrue(ventana.curva.isEnabled())
        self.assertTrue(ventana.boton_curva.isEnabled())
        self.assertFalse(ventana.curva.model().item(ventana.curva.findData('coseno')).isEnabled())
        ventana.curva.setCurrentIndex(ventana.curva.findData('exponencial'))
        ventana.boton_curva.click()
        self.assertEqual(banco.ordenes[-1], 'curva_exponencial')
        banco.estado['curva'] = 'exponencial'
        ventana.actualizar()
        self.assertIn('Exponencial', ventana.estado_curva.text())
        banco.estado['ultimo']['modo'] = 'PID'
        ventana.actualizar()
        self.assertFalse(ventana.curva.isEnabled())
        self.assertFalse(ventana.boton_curva.isEnabled())

    def test_pausa_cero_y_limites(self):
        banco = BancoFalso()
        banco.estado.update(activo=True, fuente='ESP32', edad_diag_s=.1,
            ultimo=dict(modo='REPOSO', rpm_mostrada=0, cero_estimado=True,
                        estado_medicion='SIN_SENAL', motor_encendido=0),
            historia=[dict(t_pc_s=1, rpm_mostrada=0)])
        ventana = self.crear(banco)
        ventana.actualizar()
        self.assertEqual(ventana.valores['rpm_mostrada'].text(), '0')
        self.assertIn('estimado', ventana.unidades['rpm_mostrada'].text())
        self.assertEqual((ventana.angulo_fijo.minimum(), ventana.angulo_fijo.maximum()), (25, 45))
        self.assertTrue(ventana.curva.isEnabled())
        self.assertFalse(ventana.boton_pico.isEnabled())
        ventana.alternar_pausa()
        banco.estado['historia'].append(dict(t_pc_s=2, rpm_mostrada=50))
        banco.estado['ultimo']['rpm_mostrada'] = 50
        ventana.actualizar()
        self.assertEqual(ventana.valores['rpm_mostrada'].text(), '0')
        self.assertEqual(ventana.graficas['velocidad'].historia[-1]['t_pc_s'], 1)
        ventana.alternar_pausa()
        self.assertEqual(ventana.valores['rpm_mostrada'].text(), '50')
        self.assertEqual(ventana.graficas['velocidad'].historia[-1]['t_pc_s'], 2)
        ventana.cruda.setChecked(False)
        self.assertNotIn('rpm_cruda_grafica', [s[0] for s in ventana.graficas['velocidad'].series_visibles()])

    def test_ciclo_envia_duracion_y_no_cambia_lo_armado(self):
        banco = BancoFalso()
        banco.estado.update(activo=True, fuente='ESP32', ultimo={'modo': 'REPOSO'})
        ventana = self.crear(banco)
        ventana.duracion.setValue(7)
        ventana.boton_fijo.click()
        self.assertEqual(banco.ordenes, ['tiempo7000', 'auto_fijo30'])
        banco.ordenes.clear()
        banco.estado['ultimo']['modo'] = 'PREPARACION'
        ventana.actualizar()
        ventana.boton_libre.click()
        self.assertEqual(banco.ordenes, ['auto_fijo45'])

    def test_cancelacion_confirmada_antes_de_desconectar(self):
        banco = BancoFalso()
        banco.estado.update(activo=True, fuente='ESP32', ultimo={'modo': 'PREPARACION', 'motor_encendido': 1})
        ventana = self.crear(banco)
        with patch.object(ventana, 'confirmar_cancelacion', return_value=True):
            ventana.desconectar()
        self.assertEqual(banco.ordenes, ['cancelar'])
        self.assertEqual(banco.desconexiones, 0)
        banco.estado['ultimo'].update(modo='CANCELADO', motor_encendido=0)
        ventana.actualizar()
        self.assertEqual(banco.desconexiones, 0)
        banco.secuencia = 1
        banco.estado['eventos'] = [dict(id=1, hora='00.00.00', texto='ENSAYO_CANCELADO')]
        ventana.actualizar()
        self.esperar(lambda: not ventana._trabajos)
        self.assertEqual(banco.desconexiones, 1)

    def test_cancelacion_sin_confirmacion_no_cierra(self):
        banco = BancoFalso()
        banco.estado.update(activo=True, fuente='ESP32', ultimo={'modo': 'PREPARACION', 'motor_encendido': 1})
        ventana = self.crear(banco)
        with patch.object(ventana, 'confirmar_cancelacion', return_value=True):
            ventana.desconectar()
        ventana._espera_cancelacion = (time.monotonic() - 1, 0)
        ventana.actualizar()
        self.assertIn('No se confirmó', ventana.aviso.text())
        self.assertEqual(banco.desconexiones, 0)
        self.assertTrue(banco.estado['activo'])

    def test_perdida_conexion_no_afirma_una_parada(self):
        banco = BancoFalso()
        banco.estado.update(activo=False, fuente='ESP32', ultimo={'modo': 'PREPARACION', 'motor_encendido': 1})
        ventana = self.crear(banco)
        with patch.object(ventana, 'confirmar_sin_conexion', return_value=False) as confirmar:
            ventana.desconectar(cerrar=True)
        confirmar.assert_called_once_with(True)
        self.assertEqual(banco.desconexiones, 0)
        self.assertEqual(banco.ordenes, [])
        with patch.object(ventana, 'confirmar_sin_conexion', return_value=True):
            ventana.desconectar()
        self.esperar(lambda: not ventana._trabajos)
        self.assertEqual(banco.desconexiones, 1)

    def test_cerrar_durante_una_operacion_espera_su_fin(self):
        banco = BancoFalso()
        def abrir(opciones):
            time.sleep(.08)
            banco.estado.update(activo=True, fuente='SIMULACION', ultimo={'modo': 'REPOSO'})
        banco.iniciar = abrir
        ventana = self.crear(banco)
        ventana.fuente.setCurrentIndex(1)
        ventana.show()
        ventana.conectar()
        ventana.close()
        self.esperar(lambda: banco.desconexiones == 1 and not ventana._trabajos and not ventana.isVisible())

    def test_simulacion_real_csv_y_exportacion_sin_http(self):
        with tempfile.TemporaryDirectory() as temporal:
            banco = Banco(temporal)
            ventana = self.crear(banco)
            ventana.fuente.setCurrentIndex(1)
            ventana.duracion.setValue(1)
            ventana.show()
            with patch('panel_frenado.crear_servidor', side_effect=AssertionError('No debe abrir HTTP')):
                ventana.conectar()
                self.esperar(lambda: banco.estado_actual()['activo'] and not ventana._trabajos, ventana)
                ventana.boton_fijo.click()
                fases = set()
                def terminado():
                    fases.add(banco.estado_actual()['ultimo'].get('modo'))
                    return 'FINALIZADO' in fases
                self.esperar(terminado, ventana, segundos=7)
            self.assertTrue({'PREPARACION', 'DESCENSO_LIBRE', 'FIJO', 'FINALIZADO'} <= fases)
            carpeta = Path(banco.carpeta)
            self.assertEqual(json.loads((carpeta / 'metadatos.json').read_text())['interfaz'], 'escritorio')
            with (carpeta / 'diagnostico_1.csv').open() as archivo:
                filas = list(csv.DictReader(archivo))
            self.assertTrue(any(f['modo'] == 'DESCENSO_LIBRE' for f in filas))
            self.assertTrue(any(f['modo'] == 'FIJO' for f in filas))
            png = str(carpeta / 'grafica.png')
            with patch.object(QFileDialog, 'getSaveFileName', return_value=(png, 'PNG')):
                ventana.guardar_grafica()
            self.assertEqual(Path(png).read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
            # Comprobar que los controles caben sin desplazamiento horizontal.
            self.app.processEvents()
            lateral = ventana.findChildren(QScrollArea)[0]
            self.assertLessEqual(lateral.widget().minimumSizeHint().width(), lateral.viewport().width())
            ventana.desconectar()
            self.esperar(lambda: not ventana._trabajos)
            self.assertFalse(banco.estado_actual()['activo'])

    def test_lanzador_desde_otra_carpeta(self):
        with tempfile.TemporaryDirectory() as temporal:
            python = '/usr/bin/python3' if Path('/usr/bin/python3').exists() else sys.executable
            resultado = subprocess.run([python, str(Path(banco_frenado.__file__)),
                '--comprobar', '--sin-instalar'], cwd=temporal, capture_output=True, text=True, timeout=20)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn('Entorno listo', resultado.stdout)
        self.assertIn('pyserial', resultado.stdout)
