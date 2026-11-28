#!/usr/bin/env python3
"""Compara P y PI con actualizaciones por pulsos y rango propuesto de 45 a 25 grados.

Estudio local, sin puertos ni carga en la ESP32. Los sectores desiguales, la
interpolacion de frenado y la dinamica del contacto siguen siendo hipotesis.
"""
from __future__ import annotations
import argparse
import ctypes
import json
import math
import re
import shutil
import tempfile
from pathlib import Path
import simular_modelo_medido as base
from panel.simulacion import Simulacion, Salida


def modelo_actual():
    modelo=base.cargar_modelo()
    fuerte=base.RESULTADOS/'frenado_fuerte_25_26_27/resumen_angulos.csv'
    dos=base.RESULTADOS/'primeras_pruebas_dos_marcas/resumen_angulos.csv'
    for fuente in (fuerte,dos):
        for r in base.tabla(fuente):
            modelo['nodos'][int(r['servo_grados'])]=float(r['c_comun_rpm_s'])
        modelo['fuentes'].append(str(fuente))
    return modelo


def aporte(modelo, angulo, factor):
    puntos=sorted(modelo['nodos'])
    if not 25<=angulo<=45:
        raise ValueError('Angulo fuera del rango de este estudio')
    for izq,der in zip(puntos,puntos[1:]):
        if izq<=angulo<=der:
            x=(angulo-izq)/(der-izq)
            return factor*((1-x)*modelo['nodos'][izq]+x*modelo['nodos'][der])
    raise ValueError('Angulo sin intervalo')


def paso(n,c,objetivo,dt,modelo,tau):
    nn,cc=base.avanzar(n,c,objetivo,dt,modelo['a'],modelo['b'],tau)
    ic=objetivo*dt
    if tau:ic+=(c-objetivo)*tau*(-math.expm1(-dt/tau))
    revoluciones=(n-nn-modelo['a']*dt-ic)/(modelo['b']*60)
    return nn,cc,max(0.,revoluciones)


class Sensor:
    def __init__(self,desigualdad=0.):
        self.desigualdad=desigualdad
        self.contador=0
        self.falta=.5+desigualdad
        self.ultimo=0.
        self.rpm=1100.

    def propagar(self,n,c,objetivo,t,dt,modelo,tau):
        restante=dt
        while restante>1e-12:
            nn,cc,vueltas=paso(n,c,objetivo,restante,modelo,tau)
            if vueltas<self.falta:
                self.falta-=vueltas
                return nn,cc
            lo,hi=0.,restante
            for _ in range(36):
                mitad=(lo+hi)/2
                if paso(n,c,objetivo,mitad,modelo,tau)[2]<self.falta:lo=mitad
                else:hi=mitad
            h=(lo+hi)/2
            n,c,_=paso(n,c,objetivo,h,modelo,tau)
            t+=h;restante-=h
            self.rpm=30./(t-self.ultimo)
            self.ultimo=t;self.contador+=1
            self.falta=.5+(-self.desigualdad if self.contador%2 else self.desigualdad)
        return n,c


def corrida(lib,modelo,kp,tau=.12,desigualdad=0.,factor=1.,ki=0.):
    assert lib.configurar(kp,ki,0.)
    sensor=Sensor(desigualdad)
    n,c=1100.,0.
    final=600/(1300/6)
    filas=[];estado='TRAMO_COMPLETO'
    for k in range(math.ceil(final/base.DT)+1):
        t=min(k*base.DT,final)
        if not 500<=n<=1100:
            estado='VELOCIDAD_FUERA_BANDA';break
        ref=1100-1300/6*t
        r=lib.calcularMuestra(ref,sensor.rpm,round(t*1e6),round(sensor.ultimo*1e6),True)
        if not r.disponible:raise RuntimeError('PID sin resultado')
        angulo=lib.convertir(r.limitada)
        if not 25<=angulo<=45:raise RuntimeError('Conversion angular incorrecta')
        filas.append(dict(t_tramo_s=t,referencia_rpm=ref,rpm_real_simulada=n,
            rpm_medida_simulada=sensor.rpm,error_real_rpm=n-ref,error_medido_rpm=sensor.rpm-ref,
            servo_grados=angulo,u_limitada=r.limitada,muestras=sensor.contador,
            antiguedad_s=t-sensor.ultimo))
        if t>=final:break
        dt=min(base.DT,final-t)
        n,c=sensor.propagar(n,c,aporte(modelo,angulo,factor),t,dt,modelo,tau)
    evaluar=[f for f in filas if 550<=f['referencia_rpm']<=1050]
    errores=[f['error_real_rpm'] for f in evaluar]
    cubre=bool(evaluar) and evaluar[-1]['referencia_rpm']<=555
    metrica=dict(kp=kp,ki=ki,kd=0.,tau_s=tau,desigualdad_vueltas=desigualdad,
        factor_freno=factor,estado=estado,cubre_1050_a_550=cubre,
        mae_real_rpm=sum(map(abs,errores))/len(errores) if errores else math.nan,
        error_minimo_rpm=min(errores) if errores else math.nan,
        error_maximo_rpm=max(errores) if errores else math.nan,
        angulo_minimo=min(f['servo_grados'] for f in filas),
        cambios_angulo=sum(a['servo_grados']!=b['servo_grados'] for a,b in zip(filas,filas[1:])),
        salto_maximo_grados=max([0]+[abs(a['servo_grados']-b['servo_grados']) for a,b in zip(filas,filas[1:])]))
    return filas,metrica


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida',type=Path,default=base.RESULTADOS/'pid_dos_marcas')
    parser.add_argument('--kp',type=float,nargs='+',default=[.0025,.005,.0075,.01,.015,.02])
    parser.add_argument('--ki',type=float,nargs='+',default=[0.])
    args=parser.parse_args()
    if any(not math.isfinite(x) or x<0 for x in args.kp+args.ki):
        parser.error('Las ganancias deben ser finitas y no negativas')
    args.salida.mkdir(parents=True,exist_ok=True)
    modelo=modelo_actual();resultados=[];nominales={}
    with tempfile.TemporaryDirectory(prefix='pid_rango25_') as temporal:
        raiz=Path(temporal);shutil.copytree(base.FIRMWARE/'include',raiz/'include');(raiz/'src').mkdir()
        for nombre in ('pid.cpp','freno.cpp'):shutil.copy2(base.FIRMWARE/'src'/nombre,raiz/'src'/nombre)
        config=raiz/'include/configuracion.h'
        config.write_text(re.sub(r'anguloMinimoEnsayo = \d+', 'anguloMinimoEnsayo = 25',config.read_text()))
        puente=Simulacion(raiz)
        try:
            lib=puente.lib
            lib.calcularMuestra.argtypes=[ctypes.c_float,ctypes.c_float,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_bool]
            lib.calcularMuestra.restype=Salida
            assert lib.convertir(0.)==45 and lib.convertir(1.)==25
            for kp in args.kp:
                for ki in args.ki:
                    for tau in (.12,.25):
                        for desigualdad in (-.006,0.,.006):
                            for factor in (.8,1.,1.2):
                                filas,m=corrida(lib,modelo,kp,tau,desigualdad,factor,ki=ki)
                                resultados.append(m)
                                if tau==.12 and desigualdad==.006 and factor==1.:
                                    nominales[(kp,ki)]=filas
                                    nombre=f'P_{kp:g}' if ki==0 else f'PI_{kp:g}_{ki:g}'
                                    base.guardar(args.salida/(nombre+'.csv'),filas)
        finally:puente.cerrar()
    base.guardar(args.salida/'sensibilidad.csv',resultados)
    resumen=[]
    for kp,ki in nominales:
        R=[r for r in resultados if r['kp']==kp and r['ki']==ki]
        resumen.append(dict(kp=kp,ki=ki,casos=len(R),casos_cubiertos=sum(r['cubre_1050_a_550'] for r in R),
            peor_mae_real_rpm=max(r['mae_real_rpm'] for r in R),
            peor_error_positivo_rpm=max(r['error_maximo_rpm'] for r in R),
            peor_error_negativo_rpm=min(r['error_minimo_rpm'] for r in R),
            angulo_minimo=min(r['angulo_minimo'] for r in R),
            salto_maximo_grados=max(r['salto_maximo_grados'] for r in R)))
    base.guardar(args.salida/'resumen.csv',resumen)
    informe=dict(modelo=modelo,rango_angular=[25,45],marcas=2,kp=args.kp,ki=args.ki,kd=0.,
        limites=['Estudio local entre 500 y 1100 RPM, sin prediccion de parada',
                 'Sensor por pasos de media vuelta, sin ancho de marca ni ruido electrico',
                 'Sectores de 0,5 mas o menos 0,006 vueltas son supuestos, no geometria medida',
                 'Lectura inicial de 1100 RPM asumida al iniciar el tramo',
                 'Interpolacion entre angulos y tau del contacto no validados',
                 'No reproduce fallos ni estados del firmware completo',
                 'No extrapolar estos resultados a exactitud o estabilidad fisica garantizadas'])
    (args.salida/'modelo_y_limites.json').write_text(json.dumps(informe,indent=2,ensure_ascii=False))
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axs=plt.subplots(2,1,figsize=(10,7),constrained_layout=True)
        for (kp,ki),F in nominales.items():
            t=[f['t_tramo_s'] for f in F]
            etiqueta=f'Kp {kp:g}, Ki {ki:g}'
            axs[0].plot(t,[f['rpm_real_simulada'] for f in F],label=etiqueta)
            axs[1].step(t,[f['servo_grados'] for f in F],where='post',label=etiqueta)
        axs[0].plot([0,600/(1300/6)],[1100,500],'k--',label='Referencia local de la recta de 6 s')
        axs[0].set(ylabel='RPM verdaderas del modelo')
        axs[1].set(ylabel='Orden al servo [grados]',xlabel='Tiempo desde entrada al tramo de 1100 RPM [s]')
        for ax in axs:ax.grid(alpha=.2);ax.legend(fontsize=8)
        fig.suptitle('Simulacion con dos marcas, sectores ligeramente desiguales y rango de 45 a 25 grados\n'
                     'Dinamica de contacto e interpolacion supuestas, no es una prueba fisica',fontsize=10)
        fig.savefig(args.salida/'comparacion.png',dpi=160);plt.close(fig)
    except ImportError:pass
    for r in resumen:print(r)
    print('No se abrieron puertos ni se cargo firmware. Resultados en',args.salida)


if __name__=='__main__':main()
