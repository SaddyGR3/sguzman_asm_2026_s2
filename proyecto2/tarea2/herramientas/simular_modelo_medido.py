#!/usr/bin/env python3
"""Estudio local del PID real con una planta estimada a partir de las capturas.

No abre puertos ni cambia firmware. La medida es ideal cada 20 ms. La planta
solo se propaga en la banda medida. Los angulos intermedios y la dinamica del
servo son hipotesis de simulacion, sin validacion experimental.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import tempfile
from pathlib import Path
from panel.simulacion import Simulacion

HERRAMIENTAS = Path(__file__).resolve().parent
PROYECTO = HERRAMIENTAS.parents[1]
RESULTADOS = PROYECTO / 'tarea2/matlab/resultados_reales'
FIRMWARE = PROYECTO / 'firmware/freno abs'
DT = .02


def tabla(ruta):
    with ruta.open(newline='') as archivo:
        return list(csv.DictReader(archivo))


def guardar(ruta, filas):
    if not filas:
        return
    with ruta.open('w', newline='') as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)


def cargar_modelo():
    libre = RESULTADOS / 'modelo_libre_20261127_210612_886523/parametros.csv'
    fuertes = RESULTADOS / 'caracterizacion_angulos_actual/resumen_angulos.csv'
    suaves = RESULTADOS / 'frenado_suave_20s/resumen_angulos.csv'
    f = tabla(libre)[0]
    datos = tabla(fuertes) + tabla(suaves)
    nodos = {int(r['servo_grados']): float(r['c_comun_rpm_s']) for r in datos
             if int(r['servo_grados']) in (28, 30, 33, 34, 35)}
    assert set(nodos) == {28, 30, 33, 34, 35}, 'Faltan angulos medidos'
    assert all(math.isfinite(c) and c > 0 for c in nodos.values())
    # Desde 36 se supone ausencia de contacto en el escenario nominal.
    # Las corridas aisladas de 36 y 37 no permiten validar esa frontera.
    nodos.update({36: 0., 45: 0.})
    return dict(a=float(f['a_rpm_s']), b=float(f['b_inverso_s']), nodos=nodos,
                fuentes=[str(p) for p in (libre, fuertes, suaves)])


def aporte(modelo, angulo, factor=1.):
    if not 28 <= angulo <= 45:
        raise ValueError('Angulo fuera de la zona caracterizada')
    puntos = sorted(modelo['nodos'])
    for izq, der in zip(puntos, puntos[1:]):
        if izq <= angulo <= der:
            c0, c1 = modelo['nodos'][izq], modelo['nodos'][der]
            return factor * (c0 + (c1-c0)*(angulo-izq)/(der-izq))
    raise ValueError('No hay intervalo para el angulo')


def avanzar(n, contacto, objetivo, dt, a, b, tau):
    """Solucion exacta en un paso con orden constante y contacto de primer orden."""
    eb = math.exp(-b*dt)
    if tau == 0:
        return (n+(a+objetivo)/b)*eb-(a+objetivo)/b, objetivo
    et = math.exp(-dt/tau)
    siguiente = n*eb-(a+objetivo)*(1-eb)/b-(contacto-objetivo)*(et-eb)/(b-1/tau)
    return siguiente, objetivo+(contacto-objetivo)*et


def corrida(lib, modelo, nombre, duracion, kp=0., ki=0., fijo=None, tau=.12, factor=1.):
    assert lib.configurar(kp, ki, 0.)
    n, contacto, t = 1100., 0., 0.
    pendiente = 1300./duracion
    final = 600./pendiente
    filas = []
    estado = 'TRAMO_COMPLETO'
    for k in range(math.ceil(final/DT)+1):
        t = min(k*DT, final)
        referencia = max(500., 1100.-pendiente*t)
        error = n-referencia
        if fijo is None:
            r = lib.calcular(referencia, n, round(t*1e6), True)
            if not r.disponible:
                raise RuntimeError('El PID no produjo un resultado')
            angulo = lib.convertir(r.limitada)
            solicitada, limitada, p, i = r.solicitada, r.limitada, r.p, r.i
        else:
            angulo = fijo
            solicitada = limitada = p = i = math.nan
        if not 28 <= angulo <= 45:
            estado = 'ANGULO_FUERA_MODELO'
            break
        filas.append(dict(t_tramo_s=t, t_referencia_s=t+200./pendiente,
                          referencia_rpm=referencia, rpm_simulada=n, error_rpm=error,
                          servo_grados=angulo, aporte_dinamico_rpm_s=contacto,
                          u_solicitada=solicitada, u_limitada=limitada, p=p, i=i))
        if t >= final:
            break
        siguiente = min((k+1)*DT, final)
        n, contacto = avanzar(n, contacto, aporte(modelo, angulo, factor),
                               siguiente-t, modelo['a'], modelo['b'], tau)
        if not 500 <= n <= 1100:
            estado = 'VELOCIDAD_FUERA_BANDA'
            # No se sigue propagando una planta fuera de la banda medida.
            break
    evaluar = [r for r in filas if 550 <= r['referencia_rpm'] <= 1050]
    cobertura = bool(evaluar) and evaluar[-1]['referencia_rpm'] <= 555
    errores = [r['error_rpm'] for r in evaluar]
    metrica = dict(caso=nombre, duracion_referencia_s=duracion, kp=kp, ki=ki, kd=0.,
                   tau_servo_s=tau, factor_freno=factor, estado=estado,
                   cubre_1050_a_550=cobertura, registros_evaluados=len(evaluar),
                   mae_rpm=sum(abs(e) for e in errores)/len(errores) if errores else math.nan,
                   max_error_absoluto_rpm=max(map(abs, errores)) if errores else math.nan,
                   error_minimo_rpm=min(errores) if errores else math.nan,
                   error_maximo_rpm=max(errores) if errores else math.nan,
                   angulo_minimo=min(r['servo_grados'] for r in filas) if filas else math.nan,
                   angulo_maximo=max(r['servo_grados'] for r in filas) if filas else math.nan,
                   cambios_angulo=sum(x['servo_grados'] != y['servo_grados']
                                      for x, y in zip(filas, filas[1:])))
    return filas, metrica


def estudio(modelo, lib, salida):
    barrido = []
    for kp in (.002, .005, .01, .02, .04):
        for ki in (0., .001, .003, .01):
            _, m = corrida(lib, modelo, 'Candidato', 6., kp=kp, ki=ki)
            barrido.append(m)
    elegidos = {}
    for nombre, integral in [('P', False), ('PI', True)]:
        candidatos = [m for m in barrido if bool(m['ki']) == integral and m['cubre_1050_a_550']
                      and m['estado'] != 'ANGULO_FUERA_MODELO']
        assert candidatos, 'No hay candidatos dentro del modelo'
        elegidos[nombre] = min(candidatos, key=lambda m: m['mae_rpm'])
    metricas, series = [], {}
    for duracion in (6., 20.):
        casos = [('Libre', dict(fijo=45)), ('Fijo35', dict(fijo=35)), ('Fijo34', dict(fijo=34))]
        casos += [(nombre, dict(kp=m['kp'], ki=m['ki'])) for nombre, m in elegidos.items()]
        for nombre, parametros in casos:
            filas, m = corrida(lib, modelo, nombre, duracion, **parametros)
            metricas.append(m)
            series[(duracion, nombre)] = filas
            guardar(salida/f'{nombre}_{int(duracion)}s.csv', filas)
    sensibilidad = []
    pi = elegidos['PI']
    for tau in (0., .12, .25):
        for factor in (.8, 1., 1.2):
            _, m = corrida(lib, modelo, 'PI_sensibilidad', 6., kp=pi['kp'], ki=pi['ki'],
                          tau=tau, factor=factor)
            sensibilidad.append(m)
    guardar(salida/'barrido.csv', barrido)
    guardar(salida/'metricas.csv', metricas)
    guardar(salida/'sensibilidad.csv', sensibilidad)
    return elegidos, metricas, series


def graficar(salida, series):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print('Se guardaron los CSV. Para generar el PNG hace falta matplotlib.')
        return
    figura, ejes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    colores = dict(Libre='#64748b', Fijo35='#b45309', Fijo34='#7c3aed', P='#0284c7', PI='#059669')
    for col, duracion in enumerate((6., 20.)):
        maximo = 600./(1300./duracion)
        ejes[0,col].plot([0,maximo], [1100,500], '--', color='black', label='Referencia')
        for nombre, color in colores.items():
            f = series[(duracion,nombre)]
            ejes[0,col].plot([r['t_tramo_s'] for r in f], [r['rpm_simulada'] for r in f],
                             color=color, label=nombre)
            if nombre in ('P','PI'):
                ejes[1,col].step([r['t_tramo_s'] for r in f], [r['servo_grados'] for r in f],
                                 where='post', color=color, label=nombre)
        ejes[0,col].set(title=f'Recta de 1300 a 0 RPM en {int(duracion)} s, solo tramo local',
                       ylabel='Velocidad [RPM]', ylim=(480,1120))
        ejes[1,col].set(ylabel='Orden al servo [grados]', ylim=(27,46),
                       xlabel='Tiempo desde el inicio del tramo a 1100 RPM [s]')
        for ax in ejes[:,col]:
            ax.grid(alpha=.2)
            ax.legend(fontsize=8)
    figura.suptitle('Simulacion con modelo medido y sensor ideal, no es una prueba fisica\n'
                    'Interpolacion y ausencia de contacto desde 36 grados supuestas, dinamica de contacto supuesta con tau de 0,12 s', fontsize=11)
    figura.savefig(salida/'comparacion.png', dpi=160)
    plt.close(figura)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path, default=RESULTADOS/'simulacion_modelo_medido')
    args = parser.parse_args()
    args.salida.mkdir(parents=True, exist_ok=True)
    modelo = cargar_modelo()
    # El primer estudio conserva su rango historico para reproducir las cifras previas.
    # La simulacion con pulsos usa el rango nuevo y esta en simular_pid_dos_marcas.py.
    with tempfile.TemporaryDirectory(prefix='pid_estudio_inicial_') as temporal:
        raiz=Path(temporal)
        shutil.copytree(FIRMWARE/'include',raiz/'include');(raiz/'src').mkdir()
        for nombre in ('pid.cpp','freno.cpp'):shutil.copy2(FIRMWARE/'src'/nombre,raiz/'src'/nombre)
        config=raiz/'include/configuracion.h'
        config.write_text(re.sub(r'anguloMinimoEnsayo = \d+', 'anguloMinimoEnsayo = 15',config.read_text()))
        puente = Simulacion(raiz)
        try:
            assert (puente.lib.convertir(0.) == 45 and puente.lib.convertir(1.) == 15), (
                'El rango angular cambio. Revisar la simulacion antes de ejecutarla')
            # Solo se usa la biblioteca nativa. No se ejecuta la planta ficticia ni el reloj del panel.
            elegidos, metricas, series = estudio(modelo, puente.lib, args.salida)
        finally:
            puente.cerrar()
    alcanzabilidad=[]
    for duracion in (6.,20.):
        for rpm in (1100.,800.,500.):
            natural=modelo['a']+modelo['b']*rpm
            requerido=1300./duracion-natural
            alcanzabilidad.append(dict(duracion_referencia_s=duracion,rpm=rpm,
                desaceleracion_natural_rpm_s=natural,aporte_requerido_rpm_s=requerido,
                dentro_rango_local=0<=requerido<=modelo['nodos'][28]))
    guardar(args.salida/'alcanzabilidad_recta.csv',alcanzabilidad)
    huellas={f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in modelo['fuentes']}
    informe = dict(modelo=modelo, fuentes_sha256=huellas, dt_s=DT, seleccionados_solo_simulacion=elegidos,
                   banda_rpm=[500,1100], banda_metricas_referencia_rpm=[550,1050],
                   hipotesis=['Medicion ideal nueva cada 20 ms, sin sensor por pulsos',
                              'Sin contacto desde 36 grados y liberado a 45',
                              'Interpolacion lineal entre nodos del freno',
                              'Dinamica de contacto supuesta con tau de 0,12 s',
                              'Reinicio del PID y contacto liberado al entrar al tramo',
                              'Sensibilidad de 0,8 a 1,2 no es intervalo de confianza'],
                   limites=['Sin extrapolar la planta fuera de 500 a 1100 RPM',
                            'Angulos menores que 28 interrumpen la corrida',
                            'Una ganancia seleccionada en simulacion no esta validada en maqueta',
                            'Los estados y fallos del firmware completo no se simulan',
                            'Los nodos provienen de ajustes con distinta incertidumbre'])
    (args.salida/'modelo_y_limites.json').write_text(json.dumps(informe, indent=2, ensure_ascii=False))
    graficar(args.salida, series)
    print('Ganancias elegidas solo para esta simulacion')
    for nombre, m in elegidos.items():
        print(nombre, 'Kp', m['kp'], 'Ki', m['ki'], 'Kd', 0, 'MAE nominal', round(m['mae_rpm'],3))
    print('La prueba fisica y las ganancias de la ESP32 no se modificaron.')
    print('Resultados guardados en', args.salida)


if __name__ == '__main__':
    main()
