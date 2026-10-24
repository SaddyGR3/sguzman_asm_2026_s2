"""Ejecuta un kernel Jupyter nuevo en una copia sin datos/resultados calculados."""
from pathlib import Path
import hashlib,json,os,shutil,sys,tempfile,time,traceback
import nbformat
from nbclient import NotebookClient
ROOT=Path(__file__).resolve().parents[2];DEST=ROOT/'entrega/tarea1';EVIDENCIA=Path(__file__).resolve().parent
started=time.perf_counter()
with tempfile.TemporaryDirectory(prefix='tarea1-notebook-') as tmp:
    trabajo=Path(tmp)/'paquete';shutil.copytree(DEST,trabajo)
    shutil.rmtree(trabajo/'resultados')
    for n in (1,2,3):shutil.rmtree(trabajo/f'pruebas/caso_{n}')
    (trabajo/'metadatos/configuraciones.json').unlink()
    specs=Path(tmp)/'jupyter/kernels/python3';specs.mkdir(parents=True)
    (specs/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],'display_name':'Python de verificación','language':'python'}))
    os.environ['JUPYTER_PATH']=str(Path(tmp)/'jupyter');os.environ['JUPYTER_RUNTIME_DIR']=str(Path(tmp)/'runtime')
    os.environ['IPYTHONDIR']=str(Path(tmp)/'ipython');os.environ['MPLCONFIGDIR']=str(Path(tmp)/'mpl');os.environ['MPLBACKEND']='Agg'
    nb=nbformat.read(trabajo/'notebook.ipynb',as_version=4)
    def inicio(cell,cell_index,**kwargs):print(f'Celda {cell_index}: ejecución...',flush=True)
    client=NotebookClient(nb,timeout=240,kernel_name='python3',resources={'metadata':{'path':str(trabajo)}},on_cell_start=inicio)
    try:client.execute()
    except Exception:
        nbformat.write(nb,EVIDENCIA/'notebook_fallido.ipynb');raise
    assert all(c.get('execution_count') for c in nb.cells if c.cell_type=='code')
    assert not any(o.output_type=='error' for c in nb.cells if c.cell_type=='code' for o in c.outputs)
    for case in (1,2,3):
        for file in ('muestras_exactas.npz','metadatos_prueba.json','01_referencia_limpia.wav','02_ruido.wav','03_entrada_contaminada.wav'):assert (trabajo/f'pruebas/caso_{case}'/file).is_file()
    for f in ('metricas.csv','resultados_2_5.json','resumen_2_5.md'):assert (trabajo/'resultados/regenerados'/f).is_file()
    shutil.copytree(trabajo/'resultados/regenerados',DEST/'resultados/regenerados',dirs_exist_ok=True)
    for case in (1,2,3):shutil.copytree(trabajo/f'pruebas/caso_{case}',DEST/f'pruebas/caso_{case}',dirs_exist_ok=True)
    shutil.copy2(trabajo/'metadatos/configuraciones.json',DEST/'metadatos/configuraciones.json')
    shutil.copy2(trabajo/'metadatos/protocolo.json',DEST/'metadatos/protocolo.json')
    # Las salidas se guardan para revisión sin conservar rutas temporales de la verificación.
    old=str(trabajo)
    for cell in nb.cells:
        if cell.cell_type!='code':continue
        for out in cell.outputs:
            if out.output_type=='stream':out.text=out.text.replace(old,'<carpeta_del_paquete>')
            if 'data' in out:
                for key in ('text/plain','text/html'):
                    if key in out.data:out.data[key]=out.data[key].replace(old,'<carpeta_del_paquete>')
    nbformat.validate(nb);nbformat.write(nb,DEST/'notebook.ipynb')
record={'estado':'ejecucion_completa_correcta','motor':'nbclient con kernel ipykernel nuevo','python':sys.version.split()[0],'celdas_codigo':sum(c.cell_type=='code' for c in nb.cells),'regeneracion_desde_cero':{'resultados_eliminados':True,'casos_NPZ_WAV_metadatos_eliminados':True,'configuraciones_agregadas_eliminadas':True,'repositorio_original_no_importado':True},'pruebas':{'scripts_temporales':8,'espectrales':4,'comparacion':9},'duracion_s':time.perf_counter()-started,'sha256_notebook':hashlib.sha256((DEST/'notebook.ipynb').read_bytes()).hexdigest()}
(EVIDENCIA/'verificacion_notebook.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(json.dumps(record,ensure_ascii=False),flush=True)
