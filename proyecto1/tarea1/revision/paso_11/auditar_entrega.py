"""Revisa textos distribuibles, enlaces locales y sintaxis del paquete."""
from pathlib import Path
from urllib.parse import unquote
import ast,json,re,sys
import nbformat
ROOT=Path(__file__).resolve().parents[2]
DEST=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'entrega/tarea1'
errors=[];counts={'markdown':0,'python':0,'enlaces_locales':0,'celdas_notebook':0}
internal=re.compile(r'\bpasos?\s+\d+\b|ruta en el repositorio|revision/paso_|criterios_definidos_evaluador_pendiente|base para integrar|se completarán durante|/ruta/al/repositorio',re.I)
for path in DEST.rglob('*'):
 if not path.is_file():continue
 if path.suffix in ('.md','.py'):
  text=path.read_text()
  for i,line in enumerate(text.splitlines(),1):
   if internal.search(line):errors.append(f'{path.relative_to(DEST)}:{i}: referencia interna: {line.strip()}')
  if path.suffix=='.py':ast.parse(text);counts['python']+=1
  else:
   counts['markdown']+=1
   for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',text):
    if target.startswith(('http:','https:','#')):continue
    counts['enlaces_locales']+=1
    if not (path.parent/unquote(target.split('#')[0])).resolve().exists():errors.append(f'{path.relative_to(DEST)}: enlace inexistente: {target}')
 if path.suffix=='.json':
  obj=json.loads(path.read_text())
  if internal.search(json.dumps(obj,ensure_ascii=False)):errors.append(f'{path.relative_to(DEST)}: metadatos con estado o referencia interna')
nb=nbformat.read(DEST/'notebook.ipynb',as_version=4);nbformat.validate(nb)
for i,c in enumerate(nb.cells):
 counts['celdas_notebook']+=1
 if internal.search(c.source):errors.append(f'notebook celda {i}: referencia interna')
 for out in c.get('outputs',[]):
  if out.output_type=='error':errors.append(f'notebook celda {i}: error de ejecución guardado')
  if out.output_type=='stream' and internal.search(out.text):errors.append(f'notebook celda {i}: salida con referencia interna')
assert not errors,'\n'.join(errors)
print(json.dumps({'estado':'correcto',**counts},ensure_ascii=False))
