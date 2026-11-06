#!/usr/bin/env python3
"""Tablas y gráficos de METRICAS v1/v2 ya capturadas; nunca abre el serial."""
import argparse
import csv
from datetime import datetime
from pathlib import Path
import sys

from metricas_csv import CAMPOS, MODOS, agrupar


def graficar(informe, etiqueta, destino):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    campos = [
        ('snr_y_db', 'SNR estimada de salida (dB)'),
        ('delta_snr_db', 'ΔSNR estimada (dB)'),
        ('energia_banda_pct', 'Energía en banda conservada (%)'),
        ('atenuacion_db', 'Atenuación de interferencia (dB)'),
        ('mse_x', 'MSE respecto de x contaminada'),
        ('retardo_ms', 'Retardo algorítmico fijo (ms)'),
        ('proc_prom_ms', 'Procesamiento medio (ms)'),
        ('carga_pct', 'Carga media atribuida (%)'),
        ('proc_max_ms', 'Procesamiento máximo (ms)'),
    ]
    modos = [m for m in MODOS if m in informe.filas]
    fig, ejes = plt.subplots(3, 3, figsize=(15, 11))
    colores = dict(zip(MODOS, ('#64748b', '#2563eb', '#d97706', '#059669')))
    for eje, (campo, titulo) in zip(ejes.flat, campos):
        for i, modo in enumerate(modos):
            texto = informe.filas[modo][campo]
            if texto == 'NA':
                eje.text(i, .03, 'NA', ha='center', transform=eje.get_xaxis_transform())
            else:
                valor = float(texto)
                eje.bar(i, valor, color=colores[modo])
                eje.annotate(f'{valor:.3g}', (i, valor), xytext=(0, 4 if valor >= 0 else -12),
                             textcoords='offset points', ha='center', fontsize=8)
        eje.set_xticks(range(len(modos)), modos, rotation=20)
        eje.set_xlim(-.6, len(modos)-.4)
        if campo == 'snr_y_db':
            entrada = next(iter(informe.filas.values()))['snr_x_db']
            if entrada != 'NA':
                eje.axhline(float(entrada), color='#9333ea', linestyle='--', label='Entrada x')
                eje.legend(fontsize=8)
        eje.set_title(titulo, fontsize=10)
        eje.axhline(0, color='black', linewidth=.5)
        eje.grid(axis='y', alpha=.2)
    primera = next(iter(informe.filas.values()))
    fig.suptitle(f'{etiqueta} · reproducción {informe.reproduccion} · CSV v{informe.version}\n'
                 f"Banda {primera['banda_lo_hz']}–{primera['banda_hi_hz']} Hz · estimadas sin referencia limpia")
    fig.text(.5, .012, 'MSE mide modificación de x. FIR/NOTCH comparten tiempo de filtros: no sumar sus barras. '
             'SIN FILTRO reutiliza x; costo común incluido en total.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, .93))
    fig.savefig(destino.with_suffix('.png'), dpi=160)
    fig.savefig(destino.with_suffix('.svg'))
    plt.close(fig)


def ejecutar(args):
    informes, avisos, duplicados = agrupar(args.archivos)
    if args.reproduccion:
        informes = [i for i in informes if i.reproduccion in args.reproduccion]
    if not informes:
        raise ValueError('No hay informes reconocidos para esa selección. Esperar a que termine la reproducción.')
    if not args.sin_graficos:
        try:
            import matplotlib  # noqa: F401
        except ImportError as exc:
            raise ValueError('Falta matplotlib: instalar requirements_metricas.txt o usar --sin-graficos') from exc
    destino = args.salida or Path(__file__).resolve().parent / 'resultados' / datetime.now().strftime('informe_%Y%m%d_%H%M%S_%f')
    if destino.exists() and (not destino.is_dir() or any(destino.iterdir())):
        raise ValueError('La carpeta de salida ya tiene contenido; elegir otra para no mezclar resultados.')
    destino.mkdir(parents=True, exist_ok=True)
    with (destino/'metricas.csv').open('w', encoding='utf-8', newline='') as stream:
        escritor = csv.DictWriter(stream, fieldnames=['archivo', 'etiqueta', 'completo', 'valido']+CAMPOS)
        escritor.writeheader()
        for informe in informes:
            for modo in MODOS:
                if modo not in informe.filas:
                    continue
                escritor.writerow(dict(archivo=informe.archivo, etiqueta=args.etiqueta,
                                        completo=informe.completo, valido=informe.valido, **informe.filas[modo]))
    salida = ['# Comparación de filtros', '', 'Métricas estimadas sin referencia limpia. No contiene muestras, ondas ni espectros.',
              'MSE respecto de x mide modificación, no error frente a una señal limpia.', '',
              f'Registros repetidos omitidos: {duplicados}. Líneas rechazadas: {len(avisos)}.', '']
    for n, informe in enumerate(informes, 1):
        etiqueta = args.etiqueta or Path(informe.archivo).stem
        salida += [f'## {etiqueta} — reproducción {informe.reproduccion}, v{informe.version}', '',
                   f'Archivo: `{informe.archivo}`', '',
                   f"Estado del conjunto: {informe.problema or 'completo y coherente; estado de placa OK'}.", '']
        if informe.version == 1:
            salida += ['CSV v1 contiene solo el modo temporal seleccionado y RESTA; no permite comparar los cuatro modos.', '']
        salida += ['| Modo | Estado | SNR x dB | SNR y dB | ΔSNR dB | E banda % | Aten dB | MSE(x) | Ret ms | Proc prom/max ms |',
                   '|---|---|---:|---:|---:|---:|---:|---:|---:|---|']
        for modo in MODOS:
            if modo not in informe.filas:
                continue
            d = informe.filas[modo]
            valores = [modo, d['estado']] + [d[c] for c in ('snr_x_db','snr_y_db','delta_snr_db','energia_banda_pct','atenuacion_db','mse_x','retardo_ms')]
            valores += [d['proc_prom_ms']+'/'+d['proc_max_ms']]
            salida.append('| '+' | '.join(valores)+' |')
        d = next(iter(informe.filas.values()))
        salida += ['', f"Total: {d['proc_total_prom_ms']} ms medio / {d['proc_total_max_ms']} ms máximo; "
                   f"carga media {d['carga_total_pct']} %. RAM libre {d['ram_libre_b']} B, mayor bloque {d['ram_bloque_b']} B.", '']
        if float(d['proc_total_max_ms']) >= 64:
            salida += ['**El máximo total alcanza o supera el plazo de 64 ms.**', '']
        if informe.valido and not args.sin_graficos:
            nombre = f'{n:03d}_v{informe.version}_r{informe.reproduccion}'
            graficar(informe, etiqueta, destino/nombre)
            salida += [f'![Comparación]({nombre}.png)', f'[Figura SVG]({nombre}.svg)', '']
    salida += ['## Interpretación', '', 'NA se conserva como no disponible, nunca se convierte en cero.',
               'FIR y NOTCH incluyen el tiempo compartido de ambos filtros; no sumar filas para obtener carga real.',
               'SIN FILTRO v2 reutiliza la energía de x y no tiene FFT adicional; cero ms no equivale a costo global nulo.',
               'El costo total incluye trabajo común y es el que se compara con 64 ms.', '', '## Líneas rechazadas', '']
    salida += ['- '+a for a in avisos] or ['Ninguna.']
    (destino/'informe.md').write_text('\n'.join(salida)+'\n', encoding='utf-8')
    for aviso in avisos:
        print('Aviso: '+aviso, file=sys.stderr)
    print(f'Informes: {len(informes)}; completos y válidos: {sum(i.valido for i in informes)}; repetidos omitidos: {duplicados}')
    print(f'Resultados: {destino.resolve()}')
    # Producir diagnóstico útil incluso si faltó una fila, sin dar captura por buena.
    return 0 if all(i.valido for i in informes) and not avisos else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archivos', type=Path, nargs='+', help='CSV de captura; también admite logs con otras líneas')
    parser.add_argument('--etiqueta', default='', help='Nombre indicado por el usuario, por ejemplo P1')
    parser.add_argument('--reproduccion', type=int, action='append', help='Seleccionar ID; se puede repetir')
    parser.add_argument('--salida', type=Path, help='Carpeta vacía o nueva para CSV normalizado, informe y figuras')
    parser.add_argument('--sin-graficos', action='store_true', help='Solo CSV y tabla Markdown, sin matplotlib')
    try:
        return ejecutar(parser.parse_args())
    except (ValueError, OSError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
