"""Planta ficticia con el PID y la conversion angular compilados del firmware.

La medicion es ideal y continua cada 20 ms. No simula el KY-033, interrupciones,
estados completos del firmware, alimentacion ni la fisica calibrada de la maqueta.
"""
import ctypes
import math
from pathlib import Path
import subprocess
import tempfile
from .referencias import CURVAS, evaluar_referencia


class Salida(ctypes.Structure):
    _fields_ = [(n, ctypes.c_float) for n in
                ('error', 'p', 'i', 'd', 'solicitada', 'limitada')] + [
        ('dt_us', ctypes.c_uint32), ('omitidos', ctypes.c_uint32),
        ('disponible', ctypes.c_int)]


class Simulacion:
    def __init__(self, firmware, rpm=1200, duracion=6, kp=.005, ki=0, kd=0, curva='lineal'):
        if not all(math.isfinite(x) for x in (rpm, duracion, kp, ki, kd)):
            raise ValueError('Los parametros deben ser finitos')
        if not 100 <= rpm <= 2000 or not 1 <= duracion <= 30 or not all(0 <= x <= 1 for x in (kp,ki,kd)):
            raise ValueError('Parametros de simulacion fuera del rango permitido')
        if not isinstance(curva,str) or curva not in CURVAS:
            raise ValueError('Figura de referencia desconocida')
        self.temporal = tempfile.TemporaryDirectory(prefix='banco_pid_')
        self.cerrada = False
        nativo = Path(__file__).parent / 'nativo'
        biblioteca = Path(self.temporal.name) / 'pid.so'
        try:
            subprocess.run(['g++','-std=c++11','-shared','-fPIC','-O2','-Wall','-Wextra','-Werror',
                '-I',str(nativo),'-I',str(firmware/'include'), str(nativo/'puente.cpp'),
                str(firmware/'src/pid.cpp'),str(firmware/'src/freno.cpp'),'-o',str(biblioteca)],
                check=True, capture_output=True, text=True, timeout=40)
            self.lib = ctypes.CDLL(str(biblioteca))
        except Exception:
            self.temporal.cleanup()
            raise
        self.lib.configurar.argtypes = [ctypes.c_float]*3
        self.lib.configurar.restype = ctypes.c_bool
        self.lib.calcular.argtypes = [ctypes.c_float,ctypes.c_float,ctypes.c_uint32,ctypes.c_bool]
        self.lib.calcular.restype = Salida
        self.lib.convertir.argtypes = [ctypes.c_float]
        self.lib.convertir.restype = ctypes.c_int
        if not self.lib.configurar(kp,ki,kd):
            self.cerrar()
            raise ValueError('Configuracion PID invalida')
        self.parametros = dict(rpm=rpm,duracion=duracion,kp=kp,ki=ki,kd=kd,curva=curva)
        self.rpm = 0.0
        self.t = 0.0
        self.modo = 'REPOSO'
        self.motor = 0
        for nombre in ('corteAutomatico','inicioAutomatico'):
            funcion=getattr(self.lib,nombre); funcion.argtypes=[]; funcion.restype=ctypes.c_float
        for nombre in ('limitePreparacion','limiteDescenso'):
            funcion=getattr(self.lib,nombre); funcion.argtypes=[]; funcion.restype=ctypes.c_uint32
        self.corte_rpm=self.lib.corteAutomatico()
        self.inicio_rpm=self.lib.inicioAutomatico()
        self.max_preparacion_s=self.lib.limitePreparacion()/1000
        self.max_descenso_s=self.lib.limiteDescenso()/1000
        self.liberado = self.lib.convertir(0)
        self.freno_maximo = self.lib.convertir(1)
        self.angulo = self.liberado
        self.automatico = False
        self.armado = None
        self.inicio_descenso = 0
        self.contacto = 0.0
        self.inicio = 0.0
        self.inicial = 0.0
        self.pico = False
        self.rechazados = 0
        self.confirmacion = None
        self.tiempo_final = 0
        self.eventos = []
        self.evento('REFERENCIA_TIPO', CURVAS[curva])

    def evento(self, tipo, valor=0):
        self.eventos.append(f'#EVENT,{round(self.t*1000)},{tipo},{valor}')

    def comando(self, comando):
        activo = self.modo in ('PREPARACION','DESCENSO_LIBRE','FIJO','PID')
        if comando.startswith('curva_'):
            curva=comando[6:]
            if curva not in CURVAS:
                self.evento('REFERENCIA_INVALIDA'); return
            if activo:
                self.evento('REFERENCIA_BLOQUEADA_ENSAYO'); return
            self.parametros['curva']=curva
            self.evento('REFERENCIA_TIPO',CURVAS[curva]); return
        if comando in ('cancelar','motor_off'):
            self.tiempo_final=max(0,self.t-self.inicio) if self.modo in ('PID','FIJO') else 0
            self.modo='CANCELADO'; self.motor=0; self.angulo=self.liberado
            self.automatico=False; self.armado=None
            self.lib.reiniciar(); self.evento('ENSAYO_CANCELADO'); return
        if comando in ('estado','?','v'):
            self.evento('CONSULTA_SIMULADA'); return
        if comando=='auto_preparar' or comando=='auto_pid' or comando.startswith('auto_fijo'):
            if comando=='auto_pid' and not any(self.parametros[k]>0 for k in ('kp','ki','kd')):
                self.evento('PID_GANANCIAS_NO_CONFIGURADAS'); return
            if not activo:
                if self.parametros['rpm']<=self.corte_rpm:
                    self.evento('AUTO_OBJETIVO_SIMULADO_INSUFICIENTE'); return
                self.comando('preparar')
                self.automatico=True; self.armado=None
                self.evento('AUTO_CORTE_OBJETIVO_RPM',round(self.corte_rpm))
                self.evento('AUTO_INICIO_OBJETIVO_RPM',round(self.inicio_rpm))
            if comando=='auto_preparar':
                if not self.automatico: self.evento('ENSAYO_OCUPADO')
                return
            if not self.automatico or self.armado is not None or self.modo not in ('PREPARACION','DESCENSO_LIBRE'):
                self.evento('ENSAYO_OCUPADO'); return
            if self.modo=='DESCENSO_LIBRE' and self.rpm<=self.inicio_rpm:
                self.evento('AUTO_ORDEN_TARDIA'); return
            self.armado='pid' if comando=='auto_pid' else comando[5:]
            self.evento('AUTO_PID_ARMADO' if comando=='auto_pid' else 'AUTO_FIJO_ARMADO',
                        self.liberado if comando=='auto_pid' else int(comando[9:]))
            return
        if activo and comando != 'pid' and not comando.startswith('fijo'):
            self.evento('ENSAYO_OCUPADO'); return
        if comando=='preparar' and not activo:
            self.motor=1; self.angulo=self.liberado; self.modo='PREPARACION'; self.inicio=self.t
            self.automatico=False; self.armado=None
            self.lib.reiniciar(); self.evento('PREPARACION_SIMULADA'); return
        if comando=='pid' and not any(self.parametros[k]>0 for k in ('kp','ki','kd')):
            self.evento('PID_GANANCIAS_NO_CONFIGURADAS'); return
        if comando=='pid' or comando.startswith('fijo'):
            if self.automatico:
                self.evento('AUTO_REQUIERE_ARMAR'); return
            if self.modo!='PREPARACION' or self.rpm<100:
                self.evento('REQUIERE_PREPARACION_Y_VELOCIDAD'); return
            self.modo='PID' if comando=='pid' else 'FIJO'
            self.angulo=self.liberado if comando=='pid' else int(comando[4:])
            self.motor=0; self.inicio=self.t; self.inicial=self.rpm
            self.confirmacion=None; self.lib.reiniciar()
            self.evento('REFERENCIA_TIPO',CURVAS[self.parametros['curva']])
            self.evento('ENSAYO_'+self.modo+'_INICIO',1); return
        if comando.startswith('tiempo'):
            self.parametros['duracion']=int(comando[6:])/1000; return
        if comando.startswith('g') or comando=='90':
            self.angulo=90 if comando=='90' else int(comando[1:]); return
        self.evento('COMANDO_NO_SIMULADO')

    def paso(self):
        self.t += .02
        if self.automatico and self.modo=='PREPARACION' and self.t-self.inicio>=self.max_preparacion_s:
            self.comando('cancelar'); self.modo='FALLO'; self.evento('FALLO_TIEMPO_PREPARACION')
        elif self.automatico and self.modo=='DESCENSO_LIBRE' and self.t-self.inicio_descenso>=self.max_descenso_s:
            self.comando('cancelar'); self.modo='FALLO'; self.evento('FALLO_TIEMPO_DESCENSO')
        elif self.automatico and not self.pico:
            if self.modo=='PREPARACION' and self.rpm>=self.corte_rpm:
                self.motor=0; self.modo='DESCENSO_LIBRE'; self.inicio_descenso=self.t
                self.evento('MOTOR_CMD',0)
                self.evento('AUTO_MOTOR_OFF_RPM_X100',round(self.rpm*100))
            elif self.modo=='DESCENSO_LIBRE' and self.rpm<=self.inicio_rpm:
                if self.armado is None:
                    self.comando('cancelar'); self.modo='FALLO'; self.evento('AUTO_SIN_ENSAYO_ARMADO')
                else:
                    orden=self.armado; self.automatico=False; self.armado=None
                    self.evento('AUTO_INICIO_RPM_X100',round(self.rpm*100))
                    self.modo='PREPARACION'
                    self.comando(orden)
        dt = max(0,self.t-self.inicio)
        activo = self.modo in ('FIJO','PID')
        ref = evaluar_referencia(self.inicial,self.parametros['duracion'],dt,self.parametros['curva']) if activo else 0.0 if self.modo=='FINALIZADO' else math.nan
        valida = self.rpm>0 and not self.pico
        if self.pico: self.rechazados+=1
        cruda = 14000 if self.pico else self.rpm if self.rpm>0 else math.nan
        estado = 'SOSPECHOSA' if self.pico else 'RECIENTE' if valida else 'SIN_PULSOS'
        r = self.lib.calcular(ref,self.rpm,round(self.t*1e6),valida) if activo else None
        if self.modo=='PID':
            self.angulo=self.lib.convertir(r.limitada) if r.disponible else self.liberado
        u = max(0,min(1,(self.liberado-self.angulo)/(self.liberado-self.freno_maximo)))
        aplicada = u if self.modo=='PID' else math.nan
        salida = [round(self.t*1000),cruda,self.rpm if valida else math.nan,estado,
            0,round(60000000/self.rpm) if self.rpm>0 else 0,round(self.t*50),0,self.rechazados,
            0,4286 if self.rechazados else 0,self.modo,self.motor,round((dt if activo else self.tiempo_final)*1000),
            ref,self.rpm-ref if valida and math.isfinite(ref) else math.nan,
            r.solicitada if r else math.nan,aplicada,r.limitada if r else math.nan,
            r.p if r else math.nan,r.i if r else math.nan,r.d if r else math.nan,
            ('CONTROLANDO' if self.modo=='PID' else 'OBSERVACION' if any(self.parametros[k]>0 for k in ('kp','ki','kd')) else 'GANANCIAS_CERO') if r and r.disponible else
            ('MEDICION_INVALIDA' if activo else 'INACTIVO'),r.dt_us if r else 0,r.omitidos if r else 0,0]
        lineas = self.eventos + [f'{round(self.t*1000)},{self.rpm},{self.angulo}',
                    '#DIAG,'+','.join(str(x) for x in salida)]
        self.eventos=[]; self.pico=False
        # Rozamiento proporcional y freno unilateral con retardo ficticio del servo.
        self.contacto += .02/(.12+.02)*(max(0,min(1,u))-self.contacto)
        if self.motor: self.rpm += .02*(self.parametros['rpm']-self.rpm)/.35
        else: self.rpm=max(0,self.rpm-.02*(.05*self.rpm+300*self.contacto))
        if self.modo=='PREPARACION' and self.t-self.inicio>=self.max_preparacion_s:
            self.comando('cancelar')
        if activo and dt>=self.parametros['duracion']:
            self.tiempo_final=dt
            if self.modo=='FIJO': self.modo='FINALIZADO'; self.angulo=self.liberado; self.evento('ENSAYO_FIN_DURACION')
            else:
                if valida and self.rpm<=100:
                    if self.confirmacion is None: self.confirmacion=self.t
                    if self.t-self.confirmacion>=.3:
                        self.modo='FINALIZADO'; self.angulo=self.liberado; self.evento('ENSAYO_PID_FIN_BAJA_RPM')
                else: self.confirmacion=None
                if self.modo=='PID' and dt>=self.parametros['duracion']+2:
                    self.modo='FALLO'; self.angulo=self.liberado; self.evento('PID_FIN_NO_CONFIRMADO')
        return lineas

    def cerrar(self):
        if not self.cerrada:
            self.cerrada=True
            self.temporal.cleanup()
