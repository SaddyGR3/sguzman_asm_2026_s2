#!/usr/bin/env python3
"""Evalua una captura PID sin modificar ganancias ni completar mediciones ausentes."""
from __future__ import annotations
import argparse
import csv
import json
import math
import statistics
from pathlib import Path


def leer(ruta):
    with ruta.open(newline='') as archivo:return list(csv.DictReader(archivo))


def guardar(ruta,filas):
    with ruta.open('w',newline='') as archivo:
        w=csv.DictWriter(archivo,fieldnames=list(filas[0]));w.writeheader();w.writerows(filas)


def evaluar(carpeta,salida):
    E=leer(carpeta/'eventos_1.csv');D=leer(carpeta/'diagnostico_1.csv')
    inicios=[i for i,e in enumerate(E) if e['tipo']=='ENSAYO_PID_INICIO']
    if len(inicios)!=1:raise ValueError('Esta herramienta requiere una sola corrida PID por captura')
    i=inicios[0];inicio=E[i]
    j=next((j for j in range(i+1,len(E)) if E[j]['tipo'].startswith(('FALLO_','ENSAYO_PID_FIN_')) or
              E[j]['tipo'] in ('PID_FIN_NO_CONFIRMADO','ENSAYO_CANCELADO')),None)
    if j is None:raise ValueError('La captura no contiene un final de PID')
    fin=E[j]
    R=[r for r in D if r['modo']=='PID']
    V=[r for r in R if r['estado_medicion']=='RECIENTE' and math.isfinite(float(r['rpm_validada']))]
    if not V:raise ValueError('No hay lecturas validas en modo PID')
    duraciones=[float(e['valor'])/1000 for e in E[i+1:] if e['tipo']=='ENSAYO_DURACION_MS']
    if len(duraciones)!=1:raise ValueError('Duracion no unica')
    duracion=duraciones[0]
    config={}
    for clave in ('PID_KP_X1000000','PID_KI_X1000000','PID_KD_X1000000',
                  'MARCAS_POR_VUELTA','PID_ANGULO_MINIMO','PID_ANGULO_LIBERADO'):
        valores=[int(e['valor']) for e in E[:i+1] if e['tipo']==clave]
        if len(valores)!=1:raise ValueError('Falta configuracion unica de '+clave)
        config[clave]=valores[0]
    # Metadatos nuevos opcionales. Las capturas antiguas conservan su lectura.
    for clave, defecto in (('PID_PRECARGA_X1000000',0), ('MEDICION_INTERVALOS',1),
                           ('MEDICION_VUELTA_COMPLETA',0), ('REFERENCIA_FORMA_X1000',0)):
        valores=[int(e['valor']) for e in E[:i+1] if e['tipo']==clave]
        if len(valores)>1:raise ValueError('Configuracion no unica de '+clave)
        config[clave]=valores[0] if valores else defecto
    tipos=[int(e['valor']) for e in E[:i+1] if e['tipo']=='REFERENCIA_TIPO']
    config['REFERENCIA_TIPO']=tipos[-1] if tipos else 0
    resumen=[]
    grupos={'Lecturas validas durante la referencia':[r for r in V if float(r['tiempo_ensayo_ms'])<=duracion*1000],
            'Banda de referencia de 1050 a 550 RPM':[r for r in V if 550<=float(r['referencia_rpm'])<=1050]}
    for nombre,X in grupos.items():
        if not X:continue
        errores=[float(r['rpm_validada'])-float(r['referencia_rpm']) for r in X]
        resumen.append(dict(ventana=nombre,lecturas=len(X),
            inicio_s=float(X[0]['tiempo_ensayo_ms'])/1000,fin_s=float(X[-1]['tiempo_ensayo_ms'])/1000,
            mae_medido_rpm=statistics.mean(map(abs,errores)),
            rmse_medido_rpm=math.sqrt(statistics.mean(e*e for e in errores)),
            error_minimo_rpm=min(errores),error_maximo_rpm=max(errores)))
    filas=[]
    for r in R:
        n=float(r['rpm_validada']);ref=float(r['referencia_rpm']);valida=r in V
        error=n-ref if valida else math.nan
        filas.append(dict(t_ensayo_s=float(r['tiempo_ensayo_ms'])/1000,tiempo_original_ms=r['tiempo_ms'],
            referencia_rpm=ref,rpm_validada=n,error_medido_rpm=error,
            estado_medicion=r['estado_medicion'],pid_estado=r['pid_estado'],
            u_aplicada=float(r['u_aplicada']),u_solicitada=float(r['u_solicitada']),
            pid_p=float(r['pid_p']),pid_i=float(r['pid_i']),pid_d=float(r['pid_d']),
            pulsos_aceptados=int(r['pulsos_aceptados']),antiguedad_us=int(r['antiguedad_us']),
            pid_dt_us=int(r['pid_dt_us']),pid_omitidos=int(r['pid_omitidos'])))
        if valida:
            assert abs(error-float(r['error_rpm']))<.03
    # La base se estima solo para situar eventos en la figura. Se conservan ambos tiempos.
    origen=statistics.median(float(r['tiempo_ms'])-float(r['tiempo_ensayo_ms']) for r in R)
    ordenes=[dict(t_aproximado_s=(float(e['tiempo_ms'])-origen)/1000,tiempo_original_ms=e['tiempo_ms'],
                  angulo_ordenado=int(e['valor'])) for e in E[i+1:j+1] if e['tipo']=='SERVO_CMD']
    dt=[int(r['pid_dt_us']) for r in R if int(r['pid_dt_us'])>0]
    ultimo=V[-1]
    datos=dict(captura=str(carpeta),configuracion=config,duracion_referencia_s=duracion,
        final=fin['tipo'],tiempo_final_aproximado_s=(float(fin['tiempo_ms'])-origen)/1000,
        ultima_fila_valida_s=float(ultimo['tiempo_ensayo_ms'])/1000,
        ultima_rpm_valida=float(ultimo['rpm_validada']),
        antiguedad_ultima_medida_us=int(ultimo['antiguedad_us']),
        pid_dt_min_us=min(dt),pid_dt_max_us=max(dt),
        periodos_omitidos_max=max(int(r['pid_omitidos']) for r in R),
        tiempo_calculo_max_us=max(int(r['pid_tiempo_calculo_us']) for r in R),
        motor_ordenado_apagado=all(r['motor_encendido']=='0' for r in R),
        incrementos_diagnostico={k:int(R[-1][k])-int(R[0][k]) for k in
            ('pulsos_rechazados','saltos_rechazados','perdidos_cola')},
        ordenes_servo=len(ordenes),
        limites=['Errores de RPM medidas, no de velocidad verdadera independiente',
                 'Lecturas cada 100 ms pueden repetir la misma estimacion de velocidad',
                 'No se reemplaza ausencia de señal por velocidad cero',
                 'Eventos y campos de diagnostico no comparten exactamente el mismo instante',
                 'Una captura no comprueba repetibilidad ni sintonia final'])
    salida.mkdir(parents=True,exist_ok=True)
    guardar(salida/'metricas.csv',resumen);guardar(salida/'seguimiento.csv',filas)
    if ordenes:guardar(salida/'ordenes_servo.csv',ordenes)
    (salida/'diagnostico.json').write_text(json.dumps(datos,indent=2,ensure_ascii=False))
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axs=plt.subplots(3,1,figsize=(11,9),sharex=True,constrained_layout=True)
        t=[r['t_ensayo_s'] for r in filas]
        axs[0].plot(t,[r['referencia_rpm'] for r in filas],'--',label='Referencia')
        axs[0].plot(t,[r['rpm_validada'] for r in filas],label='Velocidad valida, sin completar huecos')
        axs[0].set(ylabel='RPM');axs[0].legend(fontsize=8)
        axs[1].plot(t,[r['error_medido_rpm'] for r in filas]);axs[1].axhline(0,color='gray',lw=.8)
        axs[1].set(ylabel='Medida menos referencia [RPM]')
        axs[2].step([r['t_aproximado_s'] for r in ordenes],[r['angulo_ordenado'] for r in ordenes],where='post')
        axs[2].set(ylabel='Orden al servo [grados]',xlabel='Tiempo de ensayo [s]',ylim=(24,46))
        for ax in axs:
            ax.grid(alpha=.2);ax.axvline(duracion,color='gray',ls=':',label='Fin de referencia')
        ganancias=[config[k]/1e6 for k in ('PID_KP_X1000000','PID_KI_X1000000','PID_KD_X1000000')]
        fig.suptitle('Control fisico con Kp %g, Ki %g y Kd %g\n' % tuple(ganancias) +
                     'Final registrado '+fin['tipo']+'; la ausencia de pulsos no se dibuja como cero medido',fontsize=11)
        fig.savefig(salida/'seguimiento.png',dpi=160);plt.close(fig)
    except ImportError:pass
    return resumen,datos


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('captura',type=Path)
    parser.add_argument('--salida',type=Path);args=parser.parse_args()
    raiz=Path(__file__).resolve().parents[1]/'matlab/resultados_reales'
    salida=args.salida or raiz/('evaluacion_pid_'+args.captura.resolve().name)
    resumen,datos=evaluar(args.captura,salida)
    for r in resumen:print(r)
    print('Final registrado',datos['final']);print('Resultados en',salida)


if __name__=='__main__':main()
