# Informe del avance de la semana 12

`informe.tex` integra el borrador de `docs-informe`, los resultados del paso 6
y los diagramas del receptor. `informe.pdf` es el PDF compilado para revisión.
Contiene 13 figuras: arquitectura, cuatro figuras de diseño, P1–P5 y tres
diagramas de validación/montaje. P2–P4 están en el apéndice.

## Regenerar imágenes y tablas

Con el entorno de Python de la simulación activo, desde esta carpeta:

```bash
python preparar_figuras.py
latexmk -pdf -interaction=nonstopmode -halt-on-error informe.tex
```

Se requiere Graphviz (`dot`) para exportar los diagramas vectoriales y una
distribución LaTeX con los paquetes del preámbulo para compilar el PDF. El
documento usa imágenes y tablas externas: compilar únicamente el texto del
archivo `.tex`, sin esos recursos, no es suficiente.

El script reutiliza `python -m sim.informe`, copia sus nueve PNG a `figuras/`,
incorpora el montaje del receptor y exporta tres diagramas vectoriales desde
`diagramas/*.dot`. También genera `tabla_dft.tex` y `tabla_costo.tex` a partir
del JSON/CSV de simulación, conservando sus unidades y decimales. Los tiempos
DFT/FFT cambian con la carga de la PC; cada regeneración actualiza la tabla.

Los diagramas resumidos de recepción y contenido se adaptaron para que sean
legibles en el PDF. Los originales detallados, las fuentes Mermaid y las
capturas reprocesadas permanecen en `../diagramas/`. Las figuras de diseño
se regeneran desde las configuraciones; no se modificaron los algoritmos.

## Archivos para entregar o compartir

- Para leer el informe: `informe.pdf`.
- Para compilar sin ejecutar Python: `informe.tex`, `tabla_dft.tex`,
  `tabla_costo.tex` y la carpeta `figuras/` completa.
- Para regenerar: incluir además `preparar_figuras.py`, `diagramas/` y el
  resto del proyecto (`simulacion/` y los diagramas originales).

Las copias de las imágenes de esta carpeta se versionan con el informe,
aunque sus originales regenerables estén ignorados en `simulacion/resultados/`.

## Revisión del 30 de octubre de 2026

PDF compilado con referencias resueltas y sin desbordamientos horizontales.
Las figuras se comprobaron por páginas. Se actualizaron el número de pruebas
(213), la interpretación de los residuos de P1, las unidades de memoria y las
limitaciones del modelo de costo. La actualización solo afecta presentación,
documentación y preparación de recursos.

La revisión editorial y los cotejos numéricos del 30 de octubre se registran
en `revision_editorial.md`, fuera del PDF. La declaración de IA describe el
uso de Codex observado en estas tareas. Antes de entregar, el equipo debe
confirmar sus datos, completar otros usos de IA si los hubo y aprobar la
versión final.
