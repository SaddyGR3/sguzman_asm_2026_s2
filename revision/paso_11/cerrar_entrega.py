"""Verifica calidad/archivos, crea manifiesto y comprime el paquete revisable."""
from pathlib import Path
import csv,hashlib,json,math,shutil,zipfile
ROOT=Path(__file__).resolve().parents[2];DEST=ROOT/'entrega/tarea1';EVIDENCIA=Path(__file__).resolve().parent
shutil.copy2(ROOT/'informe/informe.pdf',DEST/'informe.pdf')
with (DEST/'resultados/metricas.csv').open() as f:original=list(csv.DictReader(f))
with (DEST/'resultados/regenerados/metricas.csv').open() as f:regenerado=list(csv.DictReader(f))
assert len(original)==len(regenerado)==9
quality=[key for key in original[0] if not key.startswith(('tiempo_','memoria_')) and key not in ('razon_tiempo_audio','tramas_procesadas')]
maximo=0.0
for old,new in zip(original,regenerado):
    for key in quality:
        if old[key]==new[key]:continue
        x,y=float(old[key]),float(new[key]);error=abs(x-y);maximo=max(maximo,error)
        assert math.isclose(x,y,rel_tol=1e-10,abs_tol=1e-10),(key,x,y)
for required in ('informe.pdf','notebook.ipynb','src/filtros_temporales.py','src/filtrado_espectral.py','resultados/metricas.csv','metadatos/configuraciones.json','README.md'):
    assert (DEST/required).is_file(),required
for n in (1,2,3):
    assert len(list((DEST/f'pruebas/caso_{n}').glob('*.wav')))==3
ver=json.loads((EVIDENCIA/'verificacion_notebook.json').read_text());assert ver['sha256_notebook']==hashlib.sha256((DEST/'notebook.ipynb').read_bytes()).hexdigest()
# No distribuir cachés ni entornos. El manifiesto no se incluye a sí mismo.
files=sorted(p for p in DEST.rglob('*') if p.is_file() and p.name!='MANIFEST.sha256' and '__pycache__' not in p.parts and '.venv' not in p.parts)
(DEST/'MANIFEST.sha256').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(DEST).as_posix()+'\n' for p in files))
archive=ROOT/'entrega/tarea1.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in [*files,DEST/'MANIFEST.sha256']:z.write(p,p.relative_to(DEST.parent))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for p in [*files,DEST/'MANIFEST.sha256']:
        name=p.relative_to(DEST.parent).as_posix()
        assert hashlib.sha256(z.read(name)).digest()==hashlib.sha256(p.read_bytes()).digest(),name
record={'estado':'paquete_final_verificado','archivos':len(files)+1,'zip':str(archive.relative_to(ROOT)),'bytes_zip':archive.stat().st_size,'sha256_zip':hashlib.sha256(archive.read_bytes()).hexdigest(),'sha256_pdf':hashlib.sha256((DEST/'informe.pdf').read_bytes()).hexdigest(),'sha256_notebook':ver['sha256_notebook'],'error_max_calidad_vs_informe':maximo,'regeneracion_desde_cero':ver['regeneracion_desde_cero'],'zip_crc_e_integridad':'correctos','pendientes':[]}
(EVIDENCIA/'verificacion_entrega.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(json.dumps(record,ensure_ascii=False,indent=2))
