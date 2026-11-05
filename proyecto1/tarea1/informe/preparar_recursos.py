"""Actualiza figuras y tablas del informe desde los resultados ya medidos.
No ejecuta benchmarks ni cambia los datos de las secciones originales.
"""
from pathlib import Path
import csv, shutil, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import signal
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'informe'
sys.path.insert(0, str(ROOT / 'seccion_2_3/src'))
from filtros_temporales import disenar_fir_kaiser, obtener_polos_ceros
for p in (ROOT/'seccion_2_1/resultados/figuras').glob('*.png'):
    shutil.copy2(p, OUT/'figuras'/p.name)
for case in range(1,4):
    for p in (ROOT/f'seccion_2_2/2_2_generacionsenales/resultados/figuras/caso_{case}').glob('*.png'):
        shutil.copy2(p, OUT/'figuras'/f'generacion_{case}_{p.name}')
for p in (ROOT/'seccion_2_5/resultados/figuras').glob('*.png'):
    shutil.copy2(p, OUT/'figuras'/p.name)
shutil.copy2(ROOT/'seccion_2_5/docs/figuras/arquitectura_nodos.png', OUT/'figuras/arquitectura_nodos.png')
b,a,order = disenar_fir_kaiser(8000,1200,1800)
f,h = signal.freqz(b,a,worN=16384,fs=8000)
mag = 20*np.log10(np.maximum(np.abs(h),1e-12))
f_g,g = signal.group_delay((b,a),w=4096,fs=8000)
fig, ax = plt.subplots(3,1,figsize=(9,8),layout='constrained')
ax[0].plot(f,mag);ax[0].set(ylabel='Magnitud (dB)',ylim=(-110,2))
ax[0].axvline(1200,color='C1',ls='--');ax[0].axvline(1800,color='C2',ls='--')
# La fase y el retardo se interpretan en la banda de paso.
mask=f<=1200
ax[1].plot(f[mask],np.unwrap(np.angle(h))[mask]);ax[1].set(ylabel='Fase (rad)',xlim=(0,1200))
ax[2].plot(f_g[f_g<=1200],g[f_g<=1200]);ax[2].set(ylabel='Retardo (muestras)',xlabel='Frecuencia (Hz)',xlim=(0,1200),ylim=(17,19))
for item in ax:item.grid(alpha=.3)
fig.savefig(OUT/'figuras/fir_respuesta.png',dpi=220);plt.close(fig)
z,p=obtener_polos_ceros(b,a)
fig,ax=plt.subplots(figsize=(6,5),layout='constrained');t=np.linspace(0,2*np.pi,600)
ax.plot(np.cos(t),np.sin(t),'--',color='gray',label='Círculo unitario')
ax.scatter(z.real,z.imag,facecolors='none',edgecolors='C0',label='36 ceros')
ax.scatter(p.real,p.imag,marker='x',color='C3',label='36 polos en el origen')
ax.set(xlabel='Parte real',ylabel='Parte imaginaria',xlim=(-1.7,1.7),ylim=(-1.7,1.7),aspect='equal')
ax.grid(alpha=.3);ax.legend(fontsize=8);fig.savefig(OUT/'figuras/fir_polos_ceros.png',dpi=220);plt.close(fig)
# Coeficientes simétricos: enumerar mitad más centro sin perder ningún valor.
rows=[r'\begin{tabular}{rrr}\toprule $k$ & $36-k$ & $b[k]=b[36-k]$\\\midrule']
for k in range(19):rows.append(f'{k} & {36-k} & '+f'${b[k]:.16e}$'.replace('e',r'\mathrm{e}')+r'\\')
rows.append(r'\bottomrule\end{tabular}')
(OUT/'coeficientes.tex').write_text('\n'.join(rows)+'\n')
with (ROOT/'seccion_2_5/resultados/metricas.csv').open() as fh:data=list(csv.DictReader(fh))
names={'entrada':'Entrada','temporal_fir':'FIR','espectral':'FFT/IFFT'}
def table(headers, keys, formats):
    lines=[r'\begin{tabular}{ll'+'r'*len(keys)+r'}\toprule', 'Caso & Método & '+' & '.join(headers)+r'\\\midrule']
    for row in data:
        vals=[]
        for key,fmt in zip(keys,formats):
            val=row[key]
            vals.append('--' if val=='' else format(float(val),fmt))
        lines.append(row['caso']+' & '+names[row['metodo']]+' & '+' & '.join(vals)+r'\\')
    lines.append(r'\bottomrule\end{tabular}')
    return '\n'.join(lines)+'\n'
(OUT/'tabla_calidad.tex').write_text(table(['MSE','SNR (dB)',r'$\Delta$SNR (dB)'],['mse','snr_salida_db','delta_snr_db'],['.6e','.3f','.3f']))
(OUT/'tabla_energia.tex').write_text(table([r'$C_u$ (\%)',r'$E_y/E_s$ (\%)',r'$A_r$ (dB)',r'$A_B$ (dB)'],['energia_util_conservada_pct','energia_total_salida_pct','atenuacion_ruido_total_db','atenuacion_interferencia_banda_db'],['.3f']*4))
(OUT/'tabla_tonos.tex').write_text(table(['300 Hz (dB)','700 Hz (dB)','1100 Hz (dB)'],['ganancia_util_300_Hz_db','ganancia_util_700_Hz_db','ganancia_util_1100_Hz_db'],['.4f']*3))
(OUT/'tabla_recursos.tex').write_text(table(['Eq. 1024 (ms)','P95 captura (ms)','Persist. (B)','Pico trazado (B)'],['tiempo_equivalente_1024_mediana_ms','tiempo_captura_p95_ms','memoria_persistente_bytes','memoria_pico_trazada_adicional_bytes'],['.4f','.3f','.0f','.0f']))
print('Recursos actualizados: 25 figuras, cuatro tablas y coeficientes.')
