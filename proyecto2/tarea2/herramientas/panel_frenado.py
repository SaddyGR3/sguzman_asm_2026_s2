#!/usr/bin/env python3
"""Panel local del banco de frenado. Ejecutar y abrir la direccion mostrada.

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
import threading
import time
import webbrowser
from zoneinfo import ZoneInfo

from registrar_ensayo import Registro, ENCABEZADO, ENCABEZADO_DIAGNOSTICO
from panel.simulacion import Simulacion

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
                   '90','+','-','c','f','m','r','s','0'}: return comando
    patron = re.fullmatch(r'(g|p|fijo|tiempo)(\d+)',comando)
    if patron:
        tipo,numero=patron[1],int(patron[2])
        limites={'g':(0,90),'p':(1,10),'fijo':(47,90),'tiempo':(100,30000)}
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
        self.secuencia=0

    def evento(self,texto):
        with self.lock:
            self.secuencia+=1
            self.eventos.append(dict(id=self.secuencia,hora=ahora().strftime('%H.%M.%S'),texto=str(texto)))

    def fila(self,tipo,fila):
        with self.lock:
            self.recibido=time.monotonic()
            if tipo=='eventos': self.evento(' · '.join(fila)); return
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
            self.ultimo=d
            self.historia.append(d.copy())

    def estado_actual(self):
        with self.lock:
            edad=None if self.recibido is None else time.monotonic()-self.recibido
            return limpiar(dict(fuente=self.fuente,conexion=self.estado,error=self.error,
                carpeta=self.carpeta,edad_s=edad,edad_diag_s=None if self.diagnosticado is None else time.monotonic()-self.diagnosticado,ultimo=self.ultimo,historia=self.historia,
                eventos=self.eventos,activo=self.hilo is not None and self.hilo.is_alive()))

    def iniciar(self,opciones):
        with self.operacion:
            if self.hilo and self.hilo.is_alive(): raise ValueError('Desconecta la fuente actual antes de cambiar')
            fuente=opciones.get('fuente')
            if fuente not in ('SIMULACION','ESP32'): raise ValueError('Fuente desconocida')
            simulador=None; puerto=None
            if fuente=='SIMULACION':
                valores={k:float(opciones.get(k,v)) for k,v in dict(rpm=1200,duracion=6,kp=.005,ki=0,kd=0).items()}
                simulador=Simulacion(FIRMWARE,**valores)
            else:
                import serial
                nombre=opciones.get('puerto','')
                if not isinstance(nombre,str) or not nombre or len(nombre)>200: raise ValueError('Indica un puerto serial')
                puerto=serial.Serial(nombre,115200,timeout=.1,write_timeout=.5,exclusive=True)
            try:
                carpeta=self.salida/('simuladas' if simulador else 'reales')/ahora().strftime('%Y%m%d_%H%M%S_%f')
                carpeta.mkdir(parents=True,exist_ok=False)
                meta=dict(fuente=fuente,fecha=ahora().isoformat(),
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
                self.fuente=fuente; self.estado='CONECTADO'; self.error=''; self.carpeta=str(carpeta)
                self.historia.clear(); self.ultimo={}; self.angulo=None; self.recibido=None
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
                 (carpeta/'serial.txt').open('x',encoding='utf-8') as crudo:
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
                    self.responder(200,dict(puertos=[p.device for p in comports()]))
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
    parser.add_argument('--puerto-web',type=int,default=8765)
    parser.add_argument('--salida',type=Path,default=RAIZ.parent/'capturas'/'panel')
    parser.add_argument('--sin-abrir',action='store_true')
    args=parser.parse_args()
    banco=Banco(args.salida); servidor=crear_servidor(banco,args.puerto_web)
    url=f'http://127.0.0.1:{servidor.server_port}'
    print('Panel del banco de frenado · '+url)
    print('Cerrar el navegador no cancela el ensayo. Usa Cancelar antes de desconectar.')
    if not args.sin_abrir: webbrowser.open(url)
    try: servidor.serve_forever()
    except KeyboardInterrupt: pass
    finally: banco.desconectar(); servidor.server_close()


if __name__=='__main__': main()
