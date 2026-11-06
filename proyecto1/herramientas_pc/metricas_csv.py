"""Contrato de métricas seriales. No abre puertos ni depende de PlatformIO."""
import csv
import math
import re
from collections import defaultdict
from dataclasses import dataclass

CAMPOS_V2 = ('marca version reproduccion estado ruta modo banda_lo_hz banda_hi_hz pico_hz '
          'snr_x_db snr_y_db delta_snr_db energia_banda_pct atenuacion_db mse_x retardo_ms '
          'proc_prom_ms proc_max_ms carga_pct ram_libre_b ram_bloque_b muestras bloques_proc '
          'proc_total_prom_ms proc_total_max_ms carga_total_pct metricas_prom_ms metricas_max_ms '
          'notch_hz notch_q alfa ganancia_minima metodo_atenuacion').split()
CAMPOS = CAMPOS_V2 + ['n_fft', 'h_fft']
MODOS = ('SIN_FILTRO', 'FIR', 'NOTCH', 'RESTA')
ESTADOS = {'OK', 'CONFIG_CAMBIADA', 'DATOS_NO_FINITOS', 'SIN_MUESTRAS'}
INDEFINIDOS = set(CAMPOS[9:15])
ENTEROS = {'version', 'reproduccion', 'ram_libre_b', 'ram_bloque_b', 'muestras', 'bloques_proc', 'n_fft', 'h_fft'}
TEXTOS = {'marca', 'estado', 'ruta', 'modo', 'metodo_atenuacion'}
COMUNES = set(CAMPOS) - {'ruta', 'modo', 'snr_y_db', 'delta_snr_db', 'energia_banda_pct',
                        'atenuacion_db', 'mse_x', 'retardo_ms', 'proc_prom_ms', 'proc_max_ms', 'carga_pct'}
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')


def interpretar(linea):
    """Devuelve campos string validados; None para mensajes ajenos a métricas."""
    linea = ANSI.sub('', linea).strip()
    if not linea.startswith('METRICAS,'):
        return None
    fila = next(csv.reader([linea], strict=True))
    if len(fila) < 2 or fila[1] not in {'1', '2', '3'}:
        raise ValueError('versión no soportada')
    campos = CAMPOS if fila[1] == '3' else CAMPOS_V2
    if len(fila) != len(campos):
        raise ValueError(f'se esperaban {len(campos)} campos, llegaron {len(fila)}')
    d = dict(zip(campos, fila))
    if d['version'] != '3':
        d.update(n_fft='1024', h_fft='512')  # contrato de firmware v1/v2 fijo
    for campo in ENTEROS:
        if not re.fullmatch(r'\d+', d[campo]):
            raise ValueError(f'{campo}: entero inválido')
    if d['version'] not in {'1', '2', '3'}:
        raise ValueError(f"versión no soportada: {d['version']}")
    if int(d['n_fft']) not in (256,512,1024) or int(d['h_fft']) != int(d['n_fft'])//2:
        raise ValueError('N/H incompatibles')
    if d['estado'] not in ESTADOS or d['modo'] not in MODOS:
        raise ValueError('estado o modo desconocido')
    if d['ruta'] != ('espectral' if d['modo'] == 'RESTA' else 'temporal'):
        raise ValueError('ruta incompatible con modo')
    if d['metodo_atenuacion'] not in {'pico', 'fuera_banda'}:
        raise ValueError('método de atenuación desconocido')
    for campo in set(CAMPOS) - TEXTOS - ENTEROS:
        if campo in INDEFINIDOS and d[campo] == 'NA':
            continue
        try:
            valor = float(d[campo])
        except ValueError as exc:
            raise ValueError(f'{campo}: número inválido') from exc
        if not math.isfinite(valor):
            raise ValueError(f'{campo}: usar NA para indefinidos')
        if campo not in {'pico_hz', 'snr_x_db', 'snr_y_db', 'delta_snr_db', 'atenuacion_db'} and valor < 0:
            raise ValueError(f'{campo}: valor negativo')
    if not 100 <= float(d['banda_lo_hz']) < float(d['banda_hi_hz']) <= 3000:
        raise ValueError('banda inválida')
    if d['version'] == '3' and d['modo'] == 'RESTA':
        if abs(float(d['retardo_ms']) - int(d['h_fft']) / 8) > .00051:
            raise ValueError('retardo espectral incompatible con H')
    return d


@dataclass
class Informe:
    archivo: str
    version: int
    reproduccion: int
    filas: dict
    completo: bool
    valido: bool
    problema: str


def agrupar(archivos):
    """Deduplica metricas repetido por archivo/sesión, versión, ID y modo.

    Dos filas diferentes con la misma clave son conflicto, nunca se reemplazan.
    No une capturas de sesiones diferentes aunque coincidan sus IDs.
    """
    grupos = defaultdict(dict)
    conflictos = set()
    avisos = []
    duplicados = 0
    for archivo in dict.fromkeys(p.resolve() for p in archivos):
        with archivo.open(encoding='utf-8', errors='replace') as stream:
            for numero, linea in enumerate(stream, 1):
                try:
                    d = interpretar(linea)
                except (ValueError, csv.Error) as exc:
                    avisos.append(f'{archivo.name}:{numero}: {exc}')
                    continue
                if d is None:
                    continue
                clave = (str(archivo), int(d['version']), int(d['reproduccion']))
                prev = grupos[clave].get(d['modo'])
                if prev == d:
                    duplicados += 1
                elif prev is not None:
                    conflictos.add(clave)
                else:
                    grupos[clave][d['modo']] = d
    informes = []
    for clave, filas in sorted(grupos.items()):
        version = clave[1]
        completo = (set(filas) == set(MODOS) if version >= 2 else
                    len(filas) == 2 and 'RESTA' in filas)
        comunes = {tuple(d[c] for c in sorted(COMUNES)) for d in filas.values()}
        motivos = []
        if not completo:
            motivos.append('incompleto: faltan modos')
        if clave in conflictos:
            motivos.append('filas contradictorias para el mismo modo')
        if len(comunes) != 1:
            motivos.append('configuración o campos comunes inconsistentes')
        if any(d['estado'] != 'OK' for d in filas.values()):
            motivos.append('informe invalidado por la placa')
        informes.append(Informe(*clave, filas, completo, not motivos, '; '.join(motivos)))
    return informes, avisos, duplicados
