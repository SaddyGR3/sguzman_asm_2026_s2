"""Pruebas del panel con planta ficticia y puerto simulado. Sin ESP32."""
import csv
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from panel_frenado import Banco, crear_servidor, validar_comando, FIRMWARE, seleccionar_puertos_usb
from panel.simulacion import Simulacion
from panel.referencias import CURVAS, evaluar_referencia
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
        self.assertEqual(s.lib.convertir(0),45)
        self.assertEqual(s.lib.convertir(1),15)
        self.assertEqual(s.lib.convertir(.5),30)
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
        self.assertEqual((s.modo,s.angulo,s.motor),('CANCELADO',45,0))

    def test_giro_libre_independiente_de_ganancias(self):
        finales=[]
        for kp in (0,1):
            sim=Simulacion(FIRMWARE,kp=kp,ki=0,kd=0)
            try:
                sim.comando('preparar')
                for _ in range(100): sim.paso()
                inicial=sim.rpm
                sim.comando(validar_comando('fijo45'))
                self.assertEqual((sim.modo,sim.motor,sim.angulo),('FIJO',0,45))
                for _ in range(300):
                    sim.paso()
                    self.assertEqual((sim.motor,sim.angulo,sim.contacto),(0,45,0))
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

    def test_formas_de_referencia(self):
        for curva in CURVAS:
            with self.subTest(curva=curva):
                self.assertEqual(evaluar_referencia(1200,6,0,curva),1200)
                self.assertEqual(evaluar_referencia(1200,6,-1,curva),1200)
                self.assertEqual(evaluar_referencia(1200,6,6,curva),0)
                self.assertEqual(evaluar_referencia(1200,6,60,curva),0)
                valores=[evaluar_referencia(1200,6,i*.006,curva) for i in range(1001)]
                self.assertTrue(all(0<=v<=1200 for v in valores))
                self.assertTrue(all(a>=b for a,b in zip(valores,valores[1:])))
                self.assertAlmostEqual(evaluar_referencia(900,9,4.5,curva)/900,
                                       evaluar_referencia(1200,6,3,curva)/1200)
        self.assertEqual(evaluar_referencia(1200,6,3,'lineal'),600)
        self.assertAlmostEqual(evaluar_referencia(1200,6,3,'coseno'),600)
        self.assertAlmostEqual(evaluar_referencia(1200,6,3,'exponencial'),
                               1200*(math.exp(-1.5)-math.exp(-3))/(1-math.exp(-3)))
        for args in [(1200,0,1,'lineal'),(-1,6,1,'lineal'),(1200,6,1,'otra'),
                     (float('nan'),6,1,'coseno'),(1200,6,float('nan'),'lineal')]:
            with self.assertRaises(ValueError): evaluar_referencia(*args)

    def test_figura_usada_por_simulacion_y_bloqueo(self):
        for curva in CURVAS:
            sim=Simulacion(FIRMWARE,curva=curva)
            try:
                sim.comando('preparar')
                sim.comando('curva_exponencial')
                self.assertEqual(sim.parametros['curva'],curva)
                self.assertIn('REFERENCIA_BLOQUEADA_ENSAYO',sim.eventos[-1])
                for _ in range(100): sim.paso()
                sim.comando('pid')
                self.assertEqual(sim.modo,'PID')
                inicial=sim.inicial
                for _ in range(150): lineas=sim.paso()
                diag=next(x for x in lineas if x.startswith('#DIAG')).split(',')[1:]
                self.assertAlmostEqual(float(diag[14]),evaluar_referencia(inicial,6,3,curva))
                self.assertAlmostEqual(float(diag[15]),float(diag[2])-float(diag[14]))
                sim.comando('cancelar');sim.comando('curva_coseno')
                self.assertEqual(sim.parametros['curva'],'coseno')
            finally:
                sim.cerrar()

    def test_reinicio_de_reloj(self):
        datos,eventos,diag=io.StringIO(),io.StringIO(),io.StringIO()
        registro=Registro(datos,eventos,diag,silencioso=True)
        registro.procesar('20000,1200,90')
        registro.procesar('#EVENT,-1,REINICIO,1')
        registro.procesar('100,1100,90')
        filas=list(csv.DictReader(io.StringIO(datos.getvalue())))
        self.assertEqual([f['tiempo_ms'] for f in filas],['20000','100'])

    def test_busqueda_omite_puertos_del_sistema(self):
        puertos=[SimpleNamespace(device='/dev/ttyS'+str(i),vid=None) for i in range(32)]
        resultado=seleccionar_puertos_usb(puertos)
        self.assertEqual(resultado['puertos'],[])
        self.assertEqual(resultado['omitidos'],32)
        puertos.extend([SimpleNamespace(device='/dev/ttyUSB0',vid=0x1a86),
                        SimpleNamespace(device='/dev/ttyACM0',vid=None),
                        SimpleNamespace(device='COM5',vid=0x10c4)])
        resultado=seleccionar_puertos_usb(puertos)
        self.assertEqual(set(resultado['puertos']),{'/dev/ttyUSB0','/dev/ttyACM0','COM5'})
        self.assertEqual(resultado['omitidos'],32)

    def test_cero_estimado_no_altera_medicion(self):
        banco=Banco('/tmp/no-usado')
        def muestra(estado,edad,aceptados=10,rpm='nan'):
            datos={k:'' for k in __import__('panel_frenado').ENCABEZADO_DIAGNOSTICO}
            datos.update(tiempo_ms='1000',estado_medicion=estado,antiguedad_us=str(edad),
                         pulsos_aceptados=str(aceptados),rpm_cruda='123',rpm_validada=rpm)
            banco.fila('diagnostico',[datos[k] for k in __import__('panel_frenado').ENCABEZADO_DIAGNOSTICO])
            return banco.estado_actual()['ultimo']
        d=muestra('RECIENTE',100,rpm='120')
        self.assertEqual(d['rpm_mostrada'],120)
        self.assertEqual(d['rpm_cruda_grafica'],123)
        d=muestra('ANTIGUA',300000)
        self.assertIsNone(d['rpm_mostrada'])
        self.assertIsNone(d['rpm_cruda_grafica'])
        self.assertFalse(d['cero_estimado'])
        d=muestra('SIN_SENAL',1100000)
        self.assertEqual(d['rpm_mostrada'],0)
        self.assertTrue(d['cero_estimado'])
        self.assertIsNone(d['rpm_validada'])
        self.assertEqual(d['rpm_cruda'],123)
        self.assertIsNone(d['rpm_cruda_grafica'])
        # Inicio sin detecciones y fallo de cola no se convierten en parada.
        for estado,cuenta in [('SIN_PULSOS',0),('DESBORDAMIENTO',10)]:
            d=muestra(estado,4294967295,cuenta)
            self.assertFalse(d['cero_estimado'])
            self.assertIsNone(d['rpm_mostrada'])
        d=muestra('RECIENTE',100,rpm='200')
        self.assertEqual(d['rpm_mostrada'],200)
        self.assertFalse(d['cero_estimado'])

    def test_ciclo_automatico_simulado(self):
        for angulo in (30,45):
            sim=Simulacion(FIRMWARE,rpm=1500)
            try:
                sim.comando('auto_fijo'+str(angulo))
                self.assertEqual((sim.modo,sim.motor,sim.angulo),('PREPARACION',1,45))
                eventos=[]; pasos=[]
                for _ in range(600):
                    lineas=sim.paso()
                    eventos.extend(l for l in lineas if l.startswith('#EVENT'))
                    pasos.extend(l for l in lineas if l.startswith('#DIAG'))
                    if sim.modo=='FINALIZADO':break
                self.assertEqual(sim.modo,'FINALIZADO')
                tabla=list(csv.reader(l[6:] for l in pasos))
                # Verificar el paso real por el importador, no solo las lineas del simulador.
                datos,eventos_csv,diagnostico=io.StringIO(),io.StringIO(),io.StringIO()
                capturador=Registro(datos,eventos_csv,diagnostico,silencioso=True)
                for linea in pasos: capturador.procesar(linea)
                guardadas=list(csv.DictReader(io.StringIO(diagnostico.getvalue())))
                self.assertEqual(len(guardadas),len(tabla))
                self.assertTrue(any(f['modo']=='DESCENSO_LIBRE' for f in guardadas))
                descenso=[f for f in tabla if f[11]=='DESCENSO_LIBRE']
                self.assertTrue(descenso)
                self.assertTrue(all(f[12]=='0' and f[14]=='nan' for f in descenso))
                ensayo=[f for f in tabla if f[11]=='FIJO']
                self.assertTrue(ensayo)
                self.assertLessEqual(float(ensayo[0][2]),1300)
                self.assertAlmostEqual(float(ensayo[0][14]),float(ensayo[0][2]),places=6)
                self.assertEqual(sim.angulo,45)
                self.assertEqual(sum('AUTO_MOTOR_OFF_RPM_X100' in e for e in eventos),1)
                self.assertEqual(sum('AUTO_INICIO_RPM_X100' in e for e in eventos),1)
            finally: sim.cerrar()
        sim=Simulacion(FIRMWARE,rpm=1500)
        try:
            sim.comando('auto_fijo30')
            for _ in range(100): sim.paso()
            sim.comando('cancelar')
            for _ in range(200):sim.paso()
            self.assertEqual((sim.modo,sim.motor,sim.angulo),('CANCELADO',0,45))
        finally:sim.cerrar()

    def test_validacion(self):
        for c in ('preparar','pid','cancelar','auto_preparar','auto_pid','auto_fijo15','auto_fijo30','auto_fijo45','fijo15','fijo30','fijo45','tiempo6000','g90','curva_coseno'):
            self.assertEqual(validar_comando(c),c)
        for c in ('pid\ncancelar','g91','auto_fijo14','auto_fijo46','auto_fijo30x','fijo14','fijo46','fijo90','tiempo30001',None,'__import__','curva_otra'):
            with self.assertRaises(ValueError): validar_comando(c)
        for parametros in ({'rpm':float('nan')},{'kp':-1},{'rpm':10000},{'curva':'otra'}):
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
            post('iniciar',{'fuente':'SIMULACION','curva':'exponencial'})
            esperar(lambda:bool(banco.estado_actual()['historia']))
            with self.assertRaises(HTTPError) as duplicado: post('iniciar',{'fuente':'SIMULACION'})
            duplicado.exception.close()
            self.assertEqual(banco.estado_actual()['curva'],'exponencial')
            post('comando',{'comando':'curva_coseno'})
            esperar(lambda:banco.estado_actual()['curva']=='coseno')
            post('comando',{'comando':'preparar'}); time.sleep(.15)
            post('comando',{'comando':'curva_lineal'})
            esperar(lambda:any('REFERENCIA_BLOQUEADA_ENSAYO' in e['texto'] for e in banco.eventos))
            self.assertEqual(banco.estado_actual()['curva'],'coseno')
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
            meta=json.loads((carpeta/'metadatos.json').read_text())
            self.assertEqual(meta['fuente'],'SIMULACION')
            self.assertEqual(meta['curva_inicial'],'exponencial')
            self.assertEqual(meta['codigos_referencia'],CURVAS)
            self.assertIn('REFERENCIA_TIPO,2',(carpeta/'eventos_1.csv').read_text())
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
            with self.assertRaisesRegex(ValueError,'solo admite referencia lineal'):
                Banco(tmp).iniciar({'fuente':'ESP32','curva':'coseno','puerto':'no_abrir'})
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
                with self.assertRaises(ValueError): banco.enviar('curva_coseno')
            finally: banco.desconectar()
            self.assertTrue(p.cerrado)
            # El cierre de captura no introduce comandos adicionales al dispositivo.
            self.assertEqual(p.ordenes,[b'cancelar\n'])
            with self.assertRaises(ValueError): banco.enviar('pid')


if __name__=='__main__': unittest.main()
