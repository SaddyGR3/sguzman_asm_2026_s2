# Informe LaTeX — paso 10

Principal: `informe.tex`. Contiene 2.1–2.5, conclusiones, referencias, declaración de IA y coeficientes del FIR. Figuras y tablas están en esta carpeta; no depende de rutas externas al compilar.

## Compilar en VS Code

Abrir `informe.tex` con LaTeX Workshop y ejecutar la receta latexmk/PDFLaTeX. Desde esta carpeta:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error informe.tex
```

Produce `informe.pdf`. No necesita BibTeX ni shell-escape. La portada contiene los cuatro nombres y carnés, sin campo de grupo. El repositorio corresponde al remoto actual y la entrega se identifica con la etiqueta `tarea1_prototipo`.

## Actualizar recursos

Desde la raíz:

```bash
MPLBACKEND=Agg MPLCONFIGDIR=/tmp/mpl-tarea1 .venv/bin/python informe/preparar_recursos.py
```

Lee el CSV existente, copia figuras y genera respuesta/polos FIR. No repite benchmarks ni modifica las secciones originales. Si cambian algoritmos o datos, primero regenerar y revisar resultados de 2.5. Los `tabla_*.tex` y `coeficientes.tex` son generados; la narración se edita en `informe.tex`.

El notebook y el paquete final están en `entrega/tarea1/`; el ZIP está en `entrega/tarea1.zip`.
