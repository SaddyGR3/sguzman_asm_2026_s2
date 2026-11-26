"""Pruebas de pantalla, comandos y sesion interactiva sin hardware ni navegador."""
import csv
import fcntl
import io
import json
import os
from pathlib import Path
import pty
import select
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import panel_frenado
from panel.terminal import minigrafica, procesar_orden, renderizar


class BancoSimulado:
    def __init__(self): self.ordenes=[]
    def enviar(self, comando):
        if comando=='invalido': raise ValueError('Comando invalido')
        self.ordenes.append(comando)


class PruebasTerminal(unittest.TestCase):
    def test_comandos_y_cierre_sin_orden_implicita(self):
        banco=BancoSimulado()
        for entrada, esperado in [('libre','auto_fijo45'),('curva coseno','curva_coseno'),
            ('figura exponencial','curva_exponencial'),('motor on','motor_on'),
            ('sensor on','sensor_on'),('sensor off','sensor_off'),('tiempo 6000','tiempo6000'),('fijo 30','fijo30'),('cancelar','cancelar')]:
            aviso,salir=procesar_orden(banco,entrada)
            self.assertFalse(salir)
            self.assertEqual(banco.ordenes[-1],esperado)
            self.assertIn('Orden enviada',aviso)
        n=len(banco.ordenes)
        self.assertFalse(procesar_orden(banco,'ayuda')[1])
        self.assertTrue(procesar_orden(banco,'salir')[1])
        self.assertEqual(len(banco.ordenes),n)
        self.assertIn('Comando invalido',procesar_orden(banco,'invalido')[0])

    def test_pantalla_huecos_y_controles(self):
        estado=dict(fuente='SIMULACION',curva='coseno',activo=True,edad_diag_s=2,
            ultimo=dict(rpm_validada=None,rpm_cruda=14000,estado_medicion='SOSPECHOSA',
                modo='PID',motor_encendido=0,angulo=90),
            historia=[{'rpm_validada':v,'referencia_rpm':1200,'u_aplicada':None} for v in (1200,None,1100)],
            eventos=[dict(hora='12.00.00',texto='Mensaje\x1b[2J\nextra')],carpeta='/tmp/prueba')
        vista=renderizar(estado,columnas=110,filas=34)
        self.assertIn('RPM —',vista)
        self.assertIn('SOSPECHOSA',vista)
        self.assertIn('14000',vista)
        self.assertIn('SIN DATOS RECIENTES',vista)
        self.assertIn('Coseno',vista)
        self.assertNotIn('\x1b',vista)
        self.assertLessEqual(len(vista.splitlines()),34)
        pequena=renderizar(estado,entrada='x'*100,columnas=30,filas=16)
        self.assertTrue(all(len(l)<=30 for l in pequena.splitlines()))
        self.assertIn('▌',pequena)
        grafica,_=minigrafica([1,None,2],10)
        self.assertEqual(grafica[1],'·')

    def test_diagnostico_sensor_csv_y_pantalla(self):
        banco=panel_frenado.Banco('/tmp/no-usado')
        archivo=io.StringIO()
        self.assertTrue(banco.recibir_sensor('#SENSOR_MODE,1,1000,1',archivo))
        for linea in ('#SENSOR,1,2000,1000,0,1,0', '#SENSOR,2,3000,1000,1,1,0',
                      '#SENSOR,3,3010,10,0,1,1', '#SENSOR_LOST,5'):
            self.assertTrue(banco.recibir_sensor(linea,archivo))
        estado=banco.estado_actual()
        self.assertEqual(estado['sensor']['perdidos'],5)
        self.assertEqual(estado['sensor']['cambios'][-1]['intervalo_us'],10)
        vista=renderizar(estado,columnas=110,filas=34)
        self.assertIn('DIAGNÓSTICO ACTIVO',vista)
        self.assertIn('CAPTURA INCOMPLETA',vista)
        self.assertIn('3010',vista)
        self.assertLessEqual(len(vista.splitlines()),34)
        n=len(archivo.getvalue())
        banco.recibir_sensor('#SENSOR,4,4000,10,7,1,0',archivo)
        self.assertEqual(len(archivo.getvalue()),n)
        banco.recibir_sensor('#SENSOR_MODE,0,5000,1',archivo)
        self.assertFalse(banco.estado_actual()['sensor']['activo'])
        filas=list(csv.reader(io.StringIO(archivo.getvalue())))
        self.assertEqual(filas[0][0],'INICIO')
        self.assertEqual(filas[-1][0],'FIN')
        self.assertEqual(filas[3],['CAMBIO','3','3010','10','0','1','1',''])
        mensajes=[]
        while not banco.salida_terminal.empty(): mensajes.append(banco.salida_terminal.get_nowait())
        self.assertTrue(any('ISR 3 | tiempo 3010 µs' in m for m in mensajes))

    def test_terminal_identifica_cero_estimado(self):
        estado=dict(fuente='ESP32',activo=True,ultimo=dict(rpm_mostrada=0,cero_estimado=True,
            rpm_validada=None,estado_medicion='SIN_SENAL'),historia=[],eventos=[])
        self.assertIn('RPM 0 (cero estimado)',renderizar(estado,columnas=110,filas=34))

    def test_terminal_no_inicia_servidor(self):
        with patch.object(sys,'argv',['panel_frenado.py','--modo','terminal','--vista-terminal','panel','--simular','--curva','coseno']), \
             patch('panel.terminal.ejecutar_terminal',return_value=0) as ejecutar, \
             patch.object(panel_frenado,'crear_servidor',side_effect=AssertionError('No debe abrir HTTP')):
            self.assertEqual(panel_frenado.main(),0)
            self.assertEqual(ejecutar.call_args.args[1]['curva'],'coseno')
            self.assertEqual(ejecutar.call_args.args[1]['fuente'],'SIMULACION')

    def test_terminal_lineas_predeterminado(self):
        with patch.object(sys,'argv',['panel_frenado.py','--modo','terminal','--simular']), \
             patch('panel.terminal.ejecutar_terminal_lineas',return_value=0) as ejecutar, \
             patch.object(panel_frenado,'crear_servidor',side_effect=AssertionError('Sin HTTP')):
            self.assertEqual(panel_frenado.main(),0)
            ejecutar.assert_called_once()

    def test_terminal_lineas_con_historial(self):
        with tempfile.TemporaryDirectory() as tmp:
            maestro,esclavo=pty.openpty()
            anterior=termios.tcgetattr(esclavo)
            proceso=subprocess.Popen([sys.executable,str(Path(panel_frenado.__file__)),
                '--modo','terminal','--simular','--salida',tmp],
                stdin=esclavo,stdout=esclavo,stderr=esclavo,close_fds=True)
            salida=bytearray()
            def esperar(texto):
                limite=time.monotonic()+5
                while time.monotonic()<limite:
                    if texto.encode() in salida:return
                    if select.select([maestro],[],[],.05)[0]:salida.extend(os.read(maestro,65536))
                raise AssertionError(salida.decode(errors='replace'))
            try:
                esperar('TERMINAL CON HISTORIAL')
                os.write(maestro,b'estado\n')
                esperar('Orden enviada · estado')
                esperar('REPOSO')
                os.write(maestro,b'salir\n')
                esperar('Captura guardada')
                proceso.wait(timeout=5)
                self.assertEqual(proceso.returncode,0)
                self.assertNotIn(b'\x1b',salida)
                self.assertEqual(termios.tcgetattr(esclavo),anterior)
            finally:
                if proceso.poll() is None:proceso.kill();proceso.wait()
                os.close(maestro);os.close(esclavo)

    def test_sesion_interactiva_captura_y_restauracion(self):
        with tempfile.TemporaryDirectory() as tmp:
            maestro,esclavo=pty.openpty()
            fcntl.ioctl(esclavo,termios.TIOCSWINSZ,struct.pack('HHHH',36,120,0,0))
            original=termios.tcgetattr(esclavo)
            salida=bytearray()
            proceso=subprocess.Popen([sys.executable,str(Path(panel_frenado.__file__)),
                '--modo','terminal','--vista-terminal','panel','--simular','--curva','coseno','--salida',tmp],
                stdin=esclavo,stdout=esclavo,stderr=esclavo,close_fds=True)
            def esperar(texto,desde=0,segundos=5):
                limite=time.monotonic()+segundos
                while time.monotonic()<limite:
                    if texto.encode() in salida[desde:]: return
                    if select.select([maestro],[],[],.05)[0]:
                        salida.extend(os.read(maestro,65536))
                    if proceso.poll() is not None: break
                raise AssertionError('No se recibio '+texto+'\n'+salida[-2000:].decode(errors='replace'))
            try:
                esperar('TERMINAL')
                esperar('Coseno')
                os.write(maestro,b'curva exponencial\n')
                esperar('Exponencial')
                os.write(maestro,b'preparar\n')
                esperar('PREPARACION')
                # Esperar que la preparacion tenga velocidad suficiente para iniciar.
                esperar('RPM 1')
                os.write(maestro,b'fijo45\n')
                esperar('ENSAYO_FIJO_INICIO')
                self.assertNotIn('http://',salida.decode(errors='replace'))
                os.write(maestro,b'cancelar\n')
                esperar('ENSAYO_CANCELADO')
                os.write(maestro,b'salir\n')
                proceso.wait(timeout=4)
                self.assertEqual(proceso.returncode,0)
                self.assertEqual(termios.tcgetattr(esclavo),original)
                # Vaciar la ultima salida para comprobar que se restauraron pantalla y cursor.
                while select.select([maestro],[],[],.05)[0]:
                    trozo=os.read(maestro,65536)
                    if not trozo: break
                    salida.extend(trozo)
                self.assertIn(b'\x1b[?1049l',salida)
                carpetas=list(Path(tmp).glob('simuladas/*'))
                self.assertEqual(len(carpetas),1)
                carpeta=carpetas[0]
                meta=json.loads((carpeta/'metadatos.json').read_text())
                self.assertEqual(meta['interfaz'],'terminal')
                eventos=list(csv.DictReader(io.StringIO((carpeta/'eventos_1.csv').read_text())))
                self.assertTrue(any(e['tipo']=='ENSAYO_CANCELADO' for e in eventos))
                self.assertTrue((carpeta/'diagnostico_1.csv').stat().st_size)
            finally:
                if proceso.poll() is None:
                    proceso.terminate();proceso.wait(timeout=4)
                os.close(maestro);os.close(esclavo)


if __name__=='__main__': unittest.main()
