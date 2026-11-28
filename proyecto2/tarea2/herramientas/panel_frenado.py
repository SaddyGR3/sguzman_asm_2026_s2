#!/usr/bin/env python3
"""Banco de frenado con modos panel y terminal. El modo predeterminado abre el panel.

Python 3.10 o posterior. Solo el modo ESP32 requiere pyserial. La simulacion
requiere g++ y compila el PID y la conversion angular reales en una carpeta temporal.
No sube firmware ni modifica sus ganancias. El servidor escucha solo en 127.0.0.1.
"""
from __future__ import annotations
import argparse
from collections import deque
import csv
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import queue
import re
import secrets
import sys
import threading
import time
import webbrowser
from zoneinfo import ZoneInfo

from registrar_ensayo import Registro, ENCABEZADO, ENCABEZADO_DIAGNOSTICO
from panel.simulacion import Simulacion
from panel.referencias import CURVAS
from panel.presentacion import velocidad_para_pantalla

def ahora():
    return datetime.now(ZoneInfo('America/Costa_Rica'))


RAIZ = Path(__file__).resolve().parent
FIRMWARE = RAIZ.parents[1] / 'firmware' / 'freno abs'


def limpiar(objeto):
    if isinstance(objeto, float) and not math.isfinite(objeto): return None
    if isinstance(objeto, dict): return {k:limpiar(v) for k,v in objeto.items()}
    if isinstance(objeto, (list,tuple,deque)): return [limpiar(v) for v in objeto]
    return objeto


def validar_comando(comando):
    if not isinstance(comando,str): raise ValueError('Comando invalido')
    if comando in {'preparar','pid','cancelar','estado','v','?','motor_off','motor_on',
                   '90','+','-','c','f','m','r','s','0','sensor_on','sensor_off','auto_preparar','auto_pid'}: return comando
    if comando in {'curva_'+c for c in CURVAS}: return comando
    patron = re.fullmatch(r'(g|p|fijo|auto_fijo|tiempo)(\d+)',comando)
    if patron:
        tipo,numero=patron[1],int(patron[2])
        limites={'g':(0,90),'p':(1,10),'fijo':(25,45),'auto_fijo':(25,45),'tiempo':(100,30000)}
        if limites[tipo][0]<=numero<=limites[tipo][1]: return comando
    raise ValueError('Comando o valor fuera del rango permitido')


class DestinoCSV:
    """Recibe solo filas validadas por el capturador existente."""
    def __init__(self,archivo,tipo,panel): self.archivo,self.tipo,self.panel=archivo,tipo,panel
    def write(self,texto):
        self.archivo.write(texto)
        fila=next(csv.reader([texto]))
        if fila and fila[0]!='tiempo_ms': self.panel.fila(self.tipo,fila)
        return len(texto)
    def flush(self): self.archivo.flush()


class Banco:
    def __init__(self,salida):
        self.salida=Path(salida)
        self.lock=threading.RLock()
        self.operacion=threading.Lock()
        self.historia=deque(maxlen=3000)
        self.eventos=deque(maxlen=160)
        self.ultimo={}
        self.fuente='SIN CONEXION'
        self.curva='lineal'
        self.estado='DESCONECTADO'
        self.error=''
        self.carpeta=''
        self.recibido=None
        self.diagnosticado=None
        self.rpm_csv=None
        self.inicio=time.monotonic()
        self.detener=threading.Event()
        self.ordenes=queue.Queue(maxsize=64)
        self.hilo=None
        self.angulo=None
        self.simulador=None
        self.salida_terminal=queue.Queue(maxsize=1024)
        self.salida_terminal_perdida=0
        self.secuencia=0
        self.sensor=dict(activo=False,nivel=None,perdidos=0,cambios=deque(maxlen=12))

    def publicar_terminal(self,texto):
        try: self.salida_terminal.put_nowait(str(texto))
        except queue.Full:
            with self.lock: self.salida_terminal_perdida+=1

    def evento(self,texto):
        with self.lock:
            self.secuencia+=1
            self.eventos.append(dict(id=self.secuencia,hora=ahora().strftime('%H.%M.%S'),texto=str(texto)))
        self.publicar_terminal(texto)

    def fila(self,tipo,fila):
        with self.lock:
            self.recibido=time.monotonic()
            if tipo=='eventos':
                if fila[1]=='REFERENCIA_TIPO':
                    self.curva=next((c for c,v in CURVAS.items() if str(v)==fila[2]),self.curva)
                self.evento(' · '.join(fila)); return
            if tipo=='datos':
                self.angulo=int(fila[2])
                # El CSV antiguo no certifica validez y no se usa como RPM validada.
                self.rpm_csv=float(fila[1]); self.ultimo['rpm_csv']=self.rpm_csv; return
            d=dict(zip(ENCABEZADO_DIAGNOSTICO,fila))
            for k,v in list(d.items()):
                if k not in {'estado_medicion','modo','pid_estado'}:
                    d[k]=float(v) if v else math.nan
            self.diagnosticado=time.monotonic()
            d['rpm_csv']=self.rpm_csv
            d['angulo']=self.angulo
            d['t_pc_s']=time.monotonic()-self.inicio
            d.update(velocidad_para_pantalla(d))
            self.ultimo=d
            self.historia.append(d.copy())

    def recibir_sensor(self,linea,archivo):
        """Valida cambios GPIO independientes de las muestras de RPM a 10 Hz."""
        if not linea.startswith(('#SENSOR,','#SENSOR_MODE,','#SENSOR_LOST,')):
            return False
        campos=linea.split(',')
        try:
            valores=[int(v) for v in campos[1:]]
            if any(v<0 or v>4294967295 for v in valores): raise ValueError()
            tipo=campos[0]
            if tipo=='#SENSOR' and len(valores)==6 and valores[3] in (0,1):
                numero,tiempo,intervalo,nivel,aceptados,cortos=valores
                fila=['CAMBIO',numero,tiempo,intervalo,nivel,aceptados,cortos,'']
                with self.lock:
                    self.sensor['nivel']=nivel
                    self.sensor['cambios'].append(dict(numero=numero,tiempo_us=tiempo,
                        intervalo_us=intervalo,nivel=nivel,aceptados=aceptados,cortos=cortos))
            elif tipo=='#SENSOR_MODE' and len(valores)==3 and valores[0] in (0,1) and valores[2] in (0,1):
                activo,tiempo,nivel=valores
                fila=['INICIO' if activo else 'FIN','',tiempo,'',nivel,'','','']
                with self.lock:
                    if activo: self.sensor['cambios'].clear(); self.sensor['perdidos']=0
                    self.sensor['activo']=bool(activo); self.sensor['nivel']=nivel
                self.evento('Diagnóstico GPIO34 '+('ACTIVO' if activo else 'DESACTIVADO'))
            elif tipo=='#SENSOR_LOST' and len(valores)==1:
                fila=['PERDIDA','','','','','','',valores[0]]
                with self.lock: self.sensor['perdidos']=valores[0]
                self.evento('Diagnóstico GPIO34 perdió '+str(valores[0])+' cambios. Captura incompleta.')
            else: raise ValueError()
        except ValueError:
            self.evento('Registro GPIO34 inválido. Revisa serial.txt')
            return True
        csv.writer(archivo).writerow(fila); archivo.flush()
        if campos[0]=='#SENSOR':
            self.publicar_terminal(f"ISR {numero} | tiempo {tiempo} µs | intervalo {intervalo} µs | nivel {nivel} | aceptados {aceptados} | cortos {cortos}")
        return True

    def estado_actual(self):
        with self.lock:
            edad=None if self.recibido is None else time.monotonic()-self.recibido
            return limpiar(dict(fuente=self.fuente,curva=self.curva,conexion=self.estado,error=self.error,
                carpeta=self.carpeta,edad_s=edad,edad_diag_s=None if self.diagnosticado is None else time.monotonic()-self.diagnosticado,ultimo=self.ultimo,historia=self.historia,
                eventos=self.eventos,sensor=self.sensor,activo=self.hilo is not None and self.hilo.is_alive()))

    def iniciar(self,opciones):
        with self.operacion:
            if self.hilo and self.hilo.is_alive(): raise ValueError('Desconecta la fuente actual antes de cambiar')
            fuente=opciones.get('fuente')
            if fuente not in ('SIMULACION','ESP32'): raise ValueError('Fuente desconocida')
            curva=opciones.get('curva','lineal')
            if not isinstance(curva,str) or curva not in CURVAS:
                raise ValueError('Figura de referencia desconocida')
            if fuente=='ESP32' and curva not in ('lineal','exponencial'):
                raise ValueError('La ESP32 admite lineal y exponencial; coseno sigue solo en simulacion')
            simulador=None; puerto=None
            if fuente=='SIMULACION':
                valores={k:float(opciones.get(k,v)) for k,v in dict(rpm=1500,duracion=6,kp=.005,ki=0,kd=0).items()}
                simulador=Simulacion(FIRMWARE,curva=curva,**valores)
            else:
                import serial
                nombre=opciones.get('puerto','')
                if not isinstance(nombre,str) or not nombre or len(nombre)>200: raise ValueError('Indica un puerto serial')
                puerto=serial.Serial(nombre,115200,timeout=.1,write_timeout=.5,exclusive=True)
            try:
                carpeta=self.salida/('simuladas' if simulador else 'reales')/ahora().strftime('%Y%m%d_%H%M%S_%f')
                carpeta.mkdir(parents=True,exist_ok=False)
                meta=dict(fuente=fuente,interfaz=opciones.get('interfaz','panel'),curva_inicial=curva if simulador else None,codigos_referencia=CURVAS,fecha=ahora().isoformat(),
                    puerto=opciones.get('puerto') if puerto else None,
                    parametros=simulador.parametros if simulador else None,
                    modelo='dRPM/dt = -0.05*RPM - 300*u; retardo servo 0.12 s' if simulador else None,
                    medicion='ideal continua a 50 Hz, sin emulacion KY-033' if simulador else 'diagnostico del firmware')
                (carpeta/'metadatos.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
            except Exception:
                if puerto: puerto.close()
                if simulador: simulador.cerrar()
                raise
            with self.lock:
                self.fuente=fuente; self.curva=curva if simulador else None; self.estado='CONECTADO'; self.error=''; self.carpeta=str(carpeta)
                self.historia.clear(); self.ultimo={}; self.angulo=None; self.recibido=None
                self.sensor=dict(activo=False,nivel=None,perdidos=0,cambios=deque(maxlen=12))
                self.diagnosticado=None; self.rpm_csv=None
                self.inicio=time.monotonic(); self.simulador=simulador
                self.detener=threading.Event(); self.ordenes=queue.Queue(maxsize=64)
                self.hilo=threading.Thread(target=self.ejecutar,args=(carpeta,puerto,simulador),daemon=True)
                self.hilo.start()
            self.evento('Fuente conectada. Captura iniciada')

    def ejecutar(self,carpeta,puerto,simulador):
        try:
            with (carpeta/'datos_1.csv').open('x',newline='',encoding='utf-8') as datos, \
                 (carpeta/'eventos_1.csv').open('x',newline='',encoding='utf-8') as eventos, \
                 (carpeta/'diagnostico_1.csv').open('x',newline='',encoding='utf-8') as diagnostico, \
                 (carpeta/'serial.txt').open('x',encoding='utf-8') as crudo, \
                 (carpeta/'sensor_1.csv').open('x',newline='',encoding='utf-8') as sensor:
                csv.writer(sensor).writerow(['tipo','numero','tiempo_us','intervalo_us','nivel','aceptados','cortos','perdidos'])
                sensor.flush()
                registro=Registro(DestinoCSV(datos,'datos',self),DestinoCSV(eventos,'eventos',self),
                    DestinoCSV(diagnostico,'diagnostico',self),silencioso=True)
                pendiente=bytearray(); siguiente=time.monotonic(); numero=0
                while not self.detener.is_set():
                    while True:
                        try: orden=self.ordenes.get_nowait()
                        except queue.Empty: break
                        if orden=='pico_simulado': simulador.pico=True
                        elif simulador: simulador.comando(orden)
                        else: puerto.write((orden+'\n').encode('ascii')); puerto.flush()
                        self.evento('Orden enviada · '+orden)
                    if simulador:
                        espera=siguiente-time.monotonic()
                        if espera>0 and self.detener.wait(espera): break
                        lineas=simulador.paso(); numero+=1
                        # Se conserva diagnostico a 10 Hz y todo evento.
                        lineas=[x for x in lineas if x.startswith('#EVENT') or numero%5==0 or 'SOSPECHOSA' in x]
                        siguiente=max(siguiente+.02,time.monotonic())
                    else:
                        trozo=puerto.read(min(max(puerto.in_waiting,1),4096))
                        pendiente.extend(trozo)
                        if len(pendiente)>65536: raise ValueError('Linea serial demasiado larga o incompleta')
                        lineas=[]
                        while b'\n' in pendiente:
                            linea,_,resto=pendiente.partition(b'\n'); pendiente=bytearray(resto)
                            lineas.append(linea.decode('utf-8',errors='replace').strip())
                    for linea in lineas:
                        crudo.write(linea+'\n'); crudo.flush()
                        if self.recibir_sensor(linea,sensor): continue
                        if linea.startswith(('#ESTADO,','#READY','#HELP')): self.evento(linea)
                        registro.procesar(linea)
        except Exception as exc:
            with self.lock: self.error=str(exc)
            self.evento('Error de captura · '+str(exc))
        finally:
            if puerto: puerto.close()
            if simulador: simulador.cerrar()
            with self.lock: self.estado='DESCONECTADO'; self.simulador=None
            self.evento('Captura cerrada. No se envio cancelacion al dispositivo')

    def enviar(self,comando):
        with self.lock:
            if not self.hilo or not self.hilo.is_alive() or self.detener.is_set(): raise ValueError('No hay fuente conectada')
            if isinstance(comando,str) and comando.startswith('curva_'):
                validar_comando(comando)
                if self.fuente=='ESP32' and comando not in ('curva_lineal','curva_exponencial'):
                    raise ValueError('El coseno sigue disponible solo en simulacion')
            if comando in ('sensor_on','sensor_off') and self.fuente!='ESP32':
                raise ValueError('El diagnóstico GPIO34 requiere la ESP32 física')
            if comando=='pico_simulado':
                if self.fuente!='SIMULACION': raise ValueError('Disponible solo en simulacion')
            else: validar_comando(comando)
            try: self.ordenes.put_nowait(comando)
            except queue.Full: raise ValueError('Hay demasiadas ordenes pendientes')

    def desconectar(self):
        with self.operacion:
            self.detener.set()
            if self.hilo:
                self.hilo.join(timeout=3)
                if self.hilo.is_alive(): raise ValueError('La captura todavia se esta cerrando')


def seleccionar_puertos_usb(puertos):
    """Sugiere USB y omite ttyS del sistema. El campo manual sigue disponible."""
    encontrados=list(puertos)
    candidatos=[p.device for p in encontrados if getattr(p,'vid',None) is not None
                or p.device.startswith(('/dev/ttyUSB','/dev/ttyACM'))]
    candidatos=sorted(set(candidatos))
    aviso=(str(len(candidatos))+' puertos USB detectados' if candidatos else
           'No se detecta un puerto USB. Revisa la conexion o escribe el puerto manualmente.')
    return dict(puertos=candidatos,omitidos=len(encontrados)-len(candidatos),aviso=aviso)


def crear_servidor(banco,puerto=8765):
    token=secrets.token_urlsafe(32)
    class Manejador(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def responder(self,estado,contenido,tipo='application/json'):
            datos=contenido.encode('utf-8') if isinstance(contenido,str) else json.dumps(limpiar(contenido),allow_nan=False,ensure_ascii=False).encode('utf-8')
            self.send_response(estado); self.send_header('Content-Type',tipo+'; charset=utf-8')
            self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Length',str(len(datos))); self.end_headers()
            self.wfile.write(datos)
        def do_GET(self):
            if self.path=='/':
                html=(RAIZ/'panel/index.html').read_text(encoding='utf-8').replace('__TOKEN__',token)
                self.responder(200,html,'text/html')
            elif self.path=='/api/estado': self.responder(200,banco.estado_actual())
            elif self.path=='/api/puertos':
                try:
                    from serial.tools.list_ports import comports
                    self.responder(200,seleccionar_puertos_usb(comports()))
                except ImportError: self.responder(200,dict(puertos=[],aviso='Instala pyserial para usar la ESP32'))
            else: self.responder(404,dict(error='Ruta desconocida'))
        def do_POST(self):
            if not secrets.compare_digest(self.headers.get('X-Panel-Token',''),token):
                self.responder(403,dict(error='Sesion no autorizada')); return
            try:
                largo=int(self.headers.get('Content-Length','0'))
                if not 0<largo<=4096: raise ValueError('Solicitud invalida')
                datos=json.loads(self.rfile.read(largo))
                if not isinstance(datos,dict): raise ValueError('Solicitud invalida')
                if self.path=='/api/iniciar': banco.iniciar(datos)
                elif self.path=='/api/comando': banco.enviar(datos.get('comando'))
                elif self.path=='/api/desconectar': banco.desconectar()
                else: self.responder(404,dict(error='Ruta desconocida')); return
                self.responder(200,dict(ok=True))
            except Exception as exc: self.responder(400,dict(error=str(exc)))
    return ThreadingHTTPServer(('127.0.0.1',puerto),Manejador)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modo',choices=('panel','terminal'),default='panel')
    parser.add_argument('--puerto-web',type=int,default=8765)
    parser.add_argument('--salida',type=Path)
    parser.add_argument('--sin-abrir',action='store_true')
    fuente=parser.add_mutually_exclusive_group()
    fuente.add_argument('--simular',action='store_true',help='Simulacion en modo terminal')
    fuente.add_argument('--puerto-serial',help='Puerto ESP32 para el modo terminal')
    parser.add_argument('--curva',choices=tuple(CURVAS),default='lineal',help='Figura inicial de la simulacion en terminal')
    parser.add_argument('--rpm',type=float,default=1500)
    parser.add_argument('--duracion',type=float,default=6)
    parser.add_argument('--kp',type=float,default=.005)
    parser.add_argument('--ki',type=float,default=0)
    parser.add_argument('--kd',type=float,default=0)
    parser.add_argument('--vista-terminal',choices=('lineas','panel'),default='lineas',help='Terminal con historial de líneas o pantalla que se redibuja')
    parser.add_argument('--sin-color',action='store_true',help='Terminal sin colores, conserva actualizacion de pantalla')
    args=parser.parse_args()
    banco=Banco(args.salida or RAIZ.parent/'capturas'/args.modo)
    if args.modo=='terminal':
        if not args.simular and not args.puerto_serial:
            parser.error('En modo terminal elige --simular o --puerto-serial')
        from panel.terminal import ejecutar_terminal, ejecutar_terminal_lineas
        opciones=dict(fuente='SIMULACION' if args.simular else 'ESP32',puerto=args.puerto_serial,
            curva=args.curva,rpm=args.rpm,duracion=args.duracion,kp=args.kp,ki=args.ki,kd=args.kd)
        try:
            ejecutar=ejecutar_terminal if args.vista_terminal=='panel' else ejecutar_terminal_lineas
            return ejecutar(banco,opciones,args.sin_color)
        except (OSError,RuntimeError,ValueError,ImportError) as exc:
            print('No se pudo iniciar la terminal · '+str(exc),file=sys.stderr)
            return 1
    if args.simular or args.puerto_serial:
        parser.error('--simular y --puerto-serial se usan con --modo terminal')
    try:
        servidor=crear_servidor(banco,args.puerto_web)
    except OSError as exc:
        if exc.errno==98:
            print('El puerto '+str(args.puerto_web)+' esta ocupado. Cierra la otra instancia o usa --puerto-web con otro numero.',file=sys.stderr)
        else:
            print('No se pudo abrir el panel · '+str(exc),file=sys.stderr)
        return 1
    url=f'http://127.0.0.1:{servidor.server_port}'
    print('Panel del banco de frenado · '+url)
    print('Cerrar el navegador no cancela el ensayo. Usa Cancelar antes de desconectar.')
    if not args.sin_abrir: webbrowser.open(url)
    try: servidor.serve_forever()
    except KeyboardInterrupt: pass
    finally: banco.desconectar(); servidor.server_close()
    return 0


if __name__=='__main__': raise SystemExit(main())
