# Código de comparación

Módulos implementados en el paso 4:

- `metricas.py`: alineamiento, MSE, SNR, energía útil, atenuación y ganancias
  por tono con los criterios del paso 2.
- `evaluar_comparacion.py`: carga y validación de configuración y casos,
  ejecución de los filtros existentes, descomposición de fuentes con
  ganancias fijas, medición de tiempo y memoria, y exportación CSV, JSON y NPZ.
- `graficar_comparacion.py`: verifica las métricas exportadas, genera seis
  figuras PNG/SVG y cuatro tablas Markdown, sin repetir filtros o benchmark.

La configuración se lee de `revision/paso_2/protocolo.json` desde la raíz
del repositorio. Los parámetros numéricos de los filtros se leen de esa
configuración. Los algoritmos de 2.3 y 2.4 se reutilizan mediante adaptadores;
no se reemplazan por funciones de biblioteca en la comparación principal.

La evaluación de fuentes separadas y la medición de memoria se hacen fuera
del tramo cronometrado. Las gráficas se producen con el módulo separado del
paso 5. Los espectros usan PSD Hann unilateral y un piso únicamente visual.

`espectral_congelado` reutiliza el relleno y la ventana de 2.4 para aplicar
las ganancias de la mezcla a cada fuente. Es instrumentación de evaluación,
no un nuevo estimador adaptativo. Se comprueba que sus contribuciones sumen
la salida del filtro original con error menor que `1e-12`.

Las validaciones de datos y configuración usan excepciones, de modo que no
se desactivan al ejecutar Python con `-O`. El JSON exportado registra hashes
del protocolo, las entradas y el código involucrado.
