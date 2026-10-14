"""Construye una entrega portable sin modificar aportes ni mediciones originales."""
from pathlib import Path
import hashlib, json, shutil, textwrap, re
ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/'entrega/tarea1'
DEST.mkdir(parents=True,exist_ok=True)
for name in ('src','pruebas','metadatos','resultados','documentacion'):(DEST/name).mkdir(exist_ok=True)
changes=[]
def copiar(src,dst,replacements=()):
    original=(ROOT/src).read_text();new=original
    if "filtros_temporales/" in dst:
        new=re.sub(r'RAIZ.parent\s*/ "seccion_2_2"\s*/ "2_2_generacionsenales"\s*/ "pruebas"', 'RAIZ / "pruebas"', new)
    for old,replacement in replacements:
        if old not in new:raise ValueError(f'Adaptación ausente: {src}: {old}')
        new=new.replace(old,replacement)
    (DEST/dst).parent.mkdir(parents=True,exist_ok=True);(DEST/dst).write_text(new)
    changes.append({'origen':src,'destino':dst,'adaptaciones':len(replacements),'sha256_original':hashlib.sha256(original.encode()).hexdigest(),'sha256_entrega':hashlib.sha256(new.encode()).hexdigest()})
for section,module in [('seccion_2_3','filtros_temporales.py'),('seccion_2_4','filtrado_espectral.py')]:copiar(f'{section}/src/{module}',f'src/{module}')
copiar('seccion_2_5/src/metricas.py','src/metricas.py')
map_eval=[('parents[2]','parents[1]'),('revision/paso_2/protocolo.json','metadatos/protocolo.json'),('seccion_2_5/resultados','resultados/regenerados'),('seccion_2_3/src','src'),('seccion_2_4/src','src'),('seccion_2_2/metadatos/configuraciones.json','metadatos/configuraciones.json'),('seccion_2_3/src/filtros_temporales.py','src/filtros_temporales.py')]
# Las sustituciones de carpetas src ya cubren también las rutas usadas en hashes.
map_eval=map_eval[:-1]
copiar('seccion_2_5/src/evaluar_comparacion.py','src/evaluar_comparacion.py',map_eval)
copiar('seccion_2_5/src/graficar_comparacion.py','src/graficar_comparacion.py', [('parents[2]','parents[1]'),('parents[1] / "resultados"','parents[1] / "resultados/regenerados"'),('revision/paso_2/protocolo.json','metadatos/protocolo.json')])
copiar('seccion_2_1/src/analizar_2_1.py','src/analizar_2_1.py',[('SECCION / "resultados"','SECCION / "resultados/regenerados/fundamentos"')])
# Reutilizar las celdas oficiales de generación/caracterización sin su demostración Kaggle adicional.
nb=json.loads((ROOT/'seccion_2_2/ce1110-generador-de-se-ales.ipynb').read_text())
imports='''from pathlib import Path
import json
import numpy as np
import matplotlib.pyplot as plt
from scipy.io import wavfile
from scipy.signal import butter, sosfiltfilt, chirp, get_window
RAIZ = Path(__file__).resolve().parents[1]
'''
helpers=''.join(nb['cells'][5]['source'])
body='\n'.join(''.join(nb['cells'][i]['source']) for i in (16,18,20))
for old,new in [('2_2_generacionsenales/pruebas','pruebas'),('2_2_generacionsenales/resultados/figuras','resultados/regenerados/generacion/figuras'),('2_2_generacionsenales/resultados/identificacion_ruido','resultados/regenerados/generacion/identificacion_ruido')]:body=body.replace(old,new)
# Todas las rutas Path relativas de estas celdas se resuelven dentro del paquete.
body=body.replace("Path('pruebas')","(RAIZ / 'pruebas')").replace('Path("pruebas")','(RAIZ / "pruebas")').replace('Path("resultados/regenerados/generacion/figuras")','(RAIZ / "resultados/regenerados/generacion/figuras")').replace('Path(\n    "resultados/regenerados/generacion/identificacion_ruido"\n)','(RAIZ / "resultados/regenerados/generacion/identificacion_ruido")')
body=body.replace('plt.show()','plt.close()')
# La celda de fase original carece de curvas con etiqueta; omitir su leyenda vacía.
phase_start=body.index('# GRÁFICA 3:');phase_end=body.index('# GRÁFICA 4:',phase_start)
body=body[:phase_start]+body[phase_start:phase_end].replace('plt.legend()', '# Fase sin leyenda: las curvas originales no tienen etiquetas.')+body[phase_end:]
config_base=json.loads((ROOT/'seccion_2_2/metadatos/configuraciones.json').read_text())
body += '\nconfiguraciones = '+repr(config_base)+'\n'
body += '''for nombre, conf in configuraciones.items():
    meta=json.loads((RAIZ / 'pruebas' / nombre / 'metadatos_prueba.json').read_text())
    conf['snr_obtenida_dB']=meta['snr_obtenida_dB']
(RAIZ / 'metadatos').mkdir(exist_ok=True)
(RAIZ / 'metadatos/configuraciones.json').write_text(json.dumps(configuraciones,indent=2,ensure_ascii=False)+'\\n')
'''
(DEST/'src/generar_senales.py').write_text(imports+'\n'+helpers+'\n\ndef regenerar():\n'+textwrap.indent(body,'    ')+'\n')
shutil.copy2(ROOT/'seccion_2_2/metadatos/configuraciones.json',DEST/'metadatos/configuraciones.json')
p=json.loads((ROOT/'revision/paso_2/protocolo.json').read_text());p['estado']='protocolo_comun_integrado';p['fuente_requisitos']='Enunciado de Tarea 1, versión 7, apartado 2.5'
import numpy as np
canon={}
for case in p['casos']:
    case['archivo']=f"pruebas/caso_{case['caso']}/muestras_exactas.npz"
    source=ROOT/f"seccion_2_2/2_2_generacionsenales/pruebas/caso_{case['caso']}"
    shutil.copytree(source,DEST/f"pruebas/caso_{case['caso']}",dirs_exist_ok=True)
    with np.load(source/'muestras_exactas.npz',allow_pickle=False) as arr:
        canon[str(case['caso'])]={k:{'shape':list(arr[k].shape),'dtype':str(arr[k].dtype),'sha256':hashlib.sha256(arr[k].tobytes()).hexdigest()} for k in arr.files}
(DEST/'metadatos/protocolo.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n')
(DEST/'metadatos/huellas_muestras.json').write_text(json.dumps(canon,indent=2)+'\n')
# Mantener calidad/tiempos del PDF como referencia; el notebook escribe en regenerados/.
for name in ('metricas.csv','resultados_2_5.json','resumen_2_5.md'):
    shutil.copy2(ROOT/'seccion_2_5/resultados'/name,DEST/'resultados'/name)
shutil.copytree(ROOT/'seccion_2_5/resultados/figuras',DEST/'resultados/figuras',dirs_exist_ok=True)
shutil.copy2(ROOT/'informe/informe.pdf',DEST/'informe.pdf')
for f in (ROOT/'seccion_2_5/docs').glob('*.md'):shutil.copy2(f,DEST/'documentacion'/f.name)
for sub in ('filtros_temporales','filtrado_espectral'):(DEST/'pruebas'/sub).mkdir(exist_ok=True)
for f in (ROOT/'seccion_2_3/pruebas/filtros_temporales').glob('test_*.py'):copiar(str(f.relative_to(ROOT)),f'pruebas/filtros_temporales/{f.name}')
# El auxiliar temporal localiza los casos con rutas antiguas: adaptar solamente ese acceso.
f=ROOT/'seccion_2_3/pruebas/filtros_temporales/evaluar_candidatos_casos.py'
s=f.read_text();s=s.replace('RAIZ.parent / "seccion_2_2" / "2_2_generacionsenales" / "pruebas"','RAIZ / "pruebas"')
s=re.sub(r'RAIZ.parent\s*/ "seccion_2_2"\s*/ "2_2_generacionsenales"\s*/ "pruebas"', 'RAIZ / "pruebas"', s)
(DEST/'pruebas/filtros_temporales/evaluar_candidatos_casos.py').write_text(s)
copiar('seccion_2_4/pruebas/filtrado_espectral/evaluar_casos.py','pruebas/filtrado_espectral/evaluar_casos.py',[('REPOSITORIO = SECCION.parent','REPOSITORIO = SECCION'),('REPOSITORIO / "seccion_2_2" / "2_2_generacionsenales" / "pruebas"','REPOSITORIO / "pruebas"'),('SECCION / "resultados"','SECCION / "resultados/regenerados/espectral"')])
copiar('seccion_2_4/pruebas/filtrado_espectral/test_filtrado_espectral.py','pruebas/filtrado_espectral/test_filtrado_espectral.py')
(DEST/'pruebas/comparacion').mkdir(exist_ok=True)
copiar('seccion_2_5/pruebas/test_comparacion.py','pruebas/comparacion/test_comparacion.py',[('seccion_2_5/src','src'),('seccion_2_2/metadatos/configuraciones.json','metadatos/configuraciones.json')])
(DEST/'metadatos/trazabilidad_codigo.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n')
print(DEST)

# Guía y dependencias también se incluyen al reconstruir una carpeta vacía.
for name in ('README.md','requirements.txt','requirements-lock.txt'):
    shutil.copy2(Path(__file__).parent/('plantilla_'+name),DEST/name)
# Los enlaces locales de los textos originales indican sus rutas de repositorio.
for f in (DEST/'documentacion').glob('*.md'):
    original=ROOT/'seccion_2_5/docs'/f.name
    def corregir(m):
        label,target=m.group(1),m.group(2)
        if target.startswith(('http:','https:','#')):return m.group(0)
        try:ruta=str((original.parent/target).resolve().relative_to(ROOT))
        except ValueError:return label
        return label+' (ruta en el repositorio: `'+ruta+'`)'
    f.write_text(re.sub(r'!?\[([^\]]+)\]\(([^)]+)\)',corregir,f.read_text()))
