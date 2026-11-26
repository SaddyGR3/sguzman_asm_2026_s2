"""Pruebas del panel con planta ficticia y puerto simulado. Sin ESP32."""
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from panel_frenado import Banco, crear_servidor, validar_comando, FIRMWARE
from panel.simulacion import Simulacion
from registrar_ensayo import Registro


def esperar(condicion,segundos=3):
    fin=time.monotonic()+segundos
    while time.monotonic()<fin:
        if condicion(): return
        time.sleep(.01)
    raise AssertionError('No se cumplio la condicion')


class PruebasPanel(unittest.TestCase):
    def test_simulacion_nativa_y_captura(self):
        s=Simulacion(FIRMWARE)
        self.addCleanup(s.cerrar)
        self.assertEqual(s.lib.convertir(0),90)
        self.assertEqual(s.lib.convertir(1),47)
        self.assertEqual(s.lib.convertir(.5),69)
        s.comando('preparar')
        for _ in range(100): s.paso()
        self.assertGreater(s.rpm,1100)
        s.comando('pid')
        datos,eventos,diag=io.StringIO(),io.StringIO(),io.StringIO()
        r=Registro(datos,eventos,diag,silencioso=True)
        for i in range(330):
            if i==40: s.pico=True
            for linea in s.paso(): r.procesar(linea)
        filas=list(csv.DictReader(io.StringIO(diag.getvalue())))
        self.assertGreater(len(filas),300)
        pid=[f for f in filas if f['modo']=='PID']
        self.assertTrue(any(float(f['u_aplicada'])>0 for f in pid))
        self.assertTrue(any(f['estado_medicion']=='SOSPECHOSA' and f['rpm_validada']=='nan' for f in pid))
        self.assertTrue(all(0<=float(f['u_aplicada'])<=1 for f in pid))
        self.assertIn('ENSAYO_PID_INICIO',eventos.getvalue())
        self.assertEqual(s.modo,'FINALIZADO')
        s.comando('cancelar')
        self.assertEqual((s.modo,s.angulo,s.motor),('CANCELADO',90,0))

    def test_giro_libre_independiente_de_ganancias(self):
        finales=[]
        for kp in (0,1):
            sim=Simulacion(FIRMWARE,kp=kp,ki=0,kd=0)
            try:
                sim.comando('preparar')
                for _ in range(100): sim.paso()
                inicial=sim.rpm
                sim.comando(validar_comando('fijo90'))
                self.assertEqual((sim.modo,sim.motor,sim.angulo),('FIJO',0,90))
                for _ in range(300):
                    sim.paso()
                    self.assertEqual((sim.motor,sim.angulo,sim.contacto),(0,90,0))
                # Con accion mecanica nula solo queda el rozamiento ficticio.
                self.assertAlmostEqual(sim.rpm,inicial*(1-.02*.05)**300,places=7)
                finales.append(sim.rpm)
                for _ in range(10): sim.paso()
                self.assertEqual(sim.modo,'FINALIZADO')
                anterior=sim.rpm
                sim.paso()
                self.assertLess(sim.rpm,anterior)
                self.assertGreater(sim.rpm,0)
            finally:
                sim.cerrar()
        self.assertAlmostEqual(finales[0],finales[1],places=7)

    def test_reinicio_de_reloj(self):
        datos,eventos,diag=io.StringIO(),io.StringIO(),io.StringIO()
        registro=Registro(datos,eventos,diag,silencioso=True)
        registro.procesar('20000,1200,90')
        registro.procesar('#EVENT,-1,REINICIO,1')
        registro.procesar('100,1100,90')
        filas=list(csv.DictReader(io.StringIO(datos.getvalue())))
        self.assertEqual([f['tiempo_ms'] for f in filas],['20000','100'])

    def test_validacion(self):
        for c in ('preparar','pid','cancelar','fijo47','tiempo6000','g90'):
            self.assertEqual(validar_comando(c),c)
        for c in ('pid\ncancelar','g91','fijo46','tiempo30001',None,'__import__'):
            with self.assertRaises(ValueError): validar_comando(c)
        for parametros in ({'rpm':float('nan')},{'kp':-1},{'rpm':10000}):
            with self.assertRaises(ValueError): Simulacion(FIRMWARE,**parametros)

    def test_http_y_ciclo_de_sesion(self):
        with tempfile.TemporaryDirectory() as tmp:
            banco=Banco(tmp); servidor=crear_servidor(banco,0)
            hilo=threading.Thread(target=servidor.serve_forever,daemon=True); hilo.start()
            self.addCleanup(servidor.server_close); self.addCleanup(servidor.shutdown)
            self.addCleanup(banco.desconectar)
            base=f'http://127.0.0.1:{servidor.server_port}'
            html=urlopen(base).read().decode()
            token=html.split("const TOKEN='")[1].split("'")[0]
            def post(ruta,body,autorizado=True):
                req=Request(base+'/api/'+ruta,json.dumps(body).encode(),headers={
                    'X-Panel-Token':token if autorizado else '', 'Content-Type':'application/json'})
                return json.loads(urlopen(req).read())
            with self.assertRaises(HTTPError) as err: post('iniciar',{'fuente':'SIMULACION'},False)
            self.assertEqual(err.exception.code,403)
            err.exception.close()
            post('iniciar',{'fuente':'SIMULACION'})
            esperar(lambda:bool(banco.estado_actual()['historia']))
            with self.assertRaises(HTTPError) as duplicado: post('iniciar',{'fuente':'SIMULACION'})
            duplicado.exception.close()
            post('comando',{'comando':'preparar'}); time.sleep(.15)
            post('comando',{'comando':'pico_simulado'})
            esperar(lambda:banco.ultimo.get('saltos_rechazados',0)>0)
            estado=json.loads(urlopen(base+'/api/estado').read())
            self.assertEqual(estado['fuente'],'SIMULACION')
            self.assertNotIn('NaN',json.dumps(estado))
            post('comando',{'comando':'cancelar'})
            esperar(lambda:banco.ultimo.get('modo')=='CANCELADO')
            post('desconectar',{})
            self.assertFalse(banco.estado_actual()['activo'])
            carpeta=Path(estado['carpeta'])
            for nombre in ('datos_1.csv','eventos_1.csv','diagnostico_1.csv','serial.txt','metadatos.json'):
                self.assertTrue((carpeta/nombre).stat().st_size)
            self.assertEqual(json.loads((carpeta/'metadatos.json').read_text())['fuente'],'SIMULACION')
            post('iniciar',{'fuente':'SIMULACION'})
            esperar(lambda:bool(banco.estado_actual()['historia']))
            self.assertNotEqual(banco.carpeta,str(carpeta))

    def test_serial_fragmentado_y_perdida(self):
        linea=b'#DIAG,100,1200,1200,RECIENTE,0,50000,2,0,0,0,0,FIJO,0,100,1180,20,nan,nan,nan,nan,nan,nan,INACTIVO,0,0,0\n'
        class Puerto:
            def __init__(self): self.in_waiting=1; self.cerrado=False; self.partes=[b'100,1200,47\n'+linea[:28],linea[28:]]; self.ordenes=[]
            def read(self,n):
                if self.partes: return self.partes.pop(0)
                time.sleep(.01); return b''
            def write(self,b): self.ordenes.append(b)
            def flush(self): pass
            def close(self): self.cerrado=True
        p=Puerto()
        with tempfile.TemporaryDirectory() as tmp:
            banco=Banco(tmp)
            fake=type('SerialSimulado',(),{'Serial':lambda *a,**kw:p})
            with patch.dict(sys.modules,{'serial':fake}): banco.iniciar({'fuente':'ESP32','puerto':'ficticio'})
            try:
                esperar(lambda:bool(banco.historia))
                self.assertEqual(banco.ultimo['angulo'],47)
                self.assertEqual(banco.ultimo['rpm_validada'],1200)
                banco.enviar('cancelar'); esperar(lambda:bool(p.ordenes))
                self.assertEqual(p.ordenes,[b'cancelar\n'])
                with self.assertRaises(ValueError): banco.enviar('pico_simulado')
            finally: banco.desconectar()
            self.assertTrue(p.cerrado)
            # El cierre de captura no introduce comandos adicionales al dispositivo.
            self.assertEqual(p.ordenes,[b'cancelar\n'])
            with self.assertRaises(ValueError): banco.enviar('pid')


if __name__=='__main__': unittest.main()
