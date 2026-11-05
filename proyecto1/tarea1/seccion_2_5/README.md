# 2.5 Comparación y propuesta para el sistema embebido

Responsabilidad del integrante 4: comparar la entrada sin filtrar, el FIR
temporal de 2.3 y el método espectral de 2.4 en los tres casos oficiales;
justificar la propuesta embebida e integrar los resultados.

## Estado

- Paso 1: aportes existentes verificados.
- Paso 2: criterios comunes definidos.
- Paso 3: estructura de esta sección preparada.
- Paso 4: evaluador implementado, probado y ejecutado sobre los tres casos.
- Paso 5: métricas contrastadas y seis figuras generadas y revisadas.
- Paso 6: métodos elegidos por caso y condiciones de fallo documentados.
- Paso 7: diseño de procesamiento para ESP32 y presupuesto calculados.
- Paso 8: bibliotecas seleccionadas, restricciones y memoria refinadas.
- Paso 9: arquitectura, protocolo, enlaces y presupuestos definidos.

Esta carpeta contiene las métricas, figuras y tablas comunes de los tres casos.
El [análisis comparativo](docs/2_5_comparacion_propuesta.md) explica las
decisiones y sus límites. El [diseño para ESP32](docs/2_5_diseno_esp32.md)
define muestreo, bloques, formato, adaptación causal y memoria provisional.
La [selección de bibliotecas](docs/2_5_bibliotecas_esp32.md) propone ESP-DSP
y compara KISS FFT. La [arquitectura y comunicación](docs/2_5_arquitectura_comunicacion.md)
define tres nodos, tramas, tasas y evaluación controlada. La integración
en LaTeX corresponde al paso 10.

## Organización

```text
seccion_2_5/
├── src/
│   ├── metricas.py
│   ├── evaluar_comparacion.py
│   ├── graficar_comparacion.py
│   └── README.md
├── pruebas/
│   ├── test_comparacion.py
│   └── README.md
├── resultados/
│   ├── metricas.csv
│   ├── resultados_2_5.json
│   ├── resumen_2_5.md
│   ├── revision_figuras.json
│   ├── caso_1/senales_comparacion.npz
│   ├── caso_2/senales_comparacion.npz
│   ├── caso_3/senales_comparacion.npz
│   ├── README.md
│   └── figuras/
├── docs/
│   ├── 2_5_comparacion_propuesta.md
│   ├── 2_5_diseno_esp32.md
│   ├── 2_5_bibliotecas_esp32.md
│   ├── 2_5_arquitectura_comunicacion.md
│   └── figuras/arquitectura_nodos.{dot,svg,png}
└── README.md
```

## Criterios y dependencias

El evaluador deberá leer directamente
[`../revision/paso_2/protocolo.json`](../revision/paso_2/protocolo.json).
La explicación metodológica está en
[`../revision/paso_2/criterios_comparacion.md`](../revision/paso_2/criterios_comparacion.md).
Se mantiene una única configuración para evitar copias que diverjan.
La evidencia de revisión está en
[`../revision/paso_1/README.md`](../revision/paso_1/README.md).

Entradas existentes, relativas a la raíz del repositorio:

- `seccion_2_2/2_2_generacionsenales/pruebas/caso_*/muestras_exactas.npz`
  y sus metadatos individuales.
- `seccion_2_3/src/filtros_temporales.py`: diseño y ecuación de diferencias FIR.
- `seccion_2_4/src/filtrado_espectral.py`: cadena espectral adaptativa.

No se copian ni se modifican los archivos de señales o filtros. El código de
esta sección resolverá las rutas desde su ubicación, para funcionar sin
depender del directorio actual de ejecución. Las referencias limpia y ruido
aislado se usarán solamente en evaluación.

## Entorno y ejecución

Las dependencias verificadas se registran en
[`../revision/paso_1/requirements.txt`](../revision/paso_1/requirements.txt).
Ya existe un entorno local `.venv/`, excluido de Git.

Para repetir la revisión del paso 1 desde la raíz:

```bash
.venv/bin/python revision/paso_1/verificar_aportes.py
```

Para evaluar los casos, medir recursos y regenerar resultados desde la raíz:

```bash
.venv/bin/python seccion_2_5/src/evaluar_comparacion.py
```

Para ejecutar las nueve pruebas:

```bash
.venv/bin/python -m unittest discover -s seccion_2_5/pruebas -p 'test_*.py' -v
```

El script acepta `--salida RUTA` para exportar a otra carpeta y
`--protocolo RUTA` para leer una configuración compatible. Con
`--sin-benchmark` calcula calidad sin medir tiempos ni pico de memoria; esas
columnas quedan vacías, excepto la identidad de coste cero. Usar una salida
alternativa en esa modalidad si se desea conservar el benchmark existente.

Para ejecutar desde otro directorio, indicar las rutas absolutas del
intérprete de `.venv/` y del script. Las rutas predeterminadas de datos,
configuración y resultados se resuelven desde el archivo del evaluador.

## Resultados y pendientes

El evaluador produce CSV, JSON y NPZ con las salidas y la descomposición útil/
ruido. Los tiempos corresponden a PC y el espectral continúa siendo fuera
de línea. La energía útil es condicional a las ganancias fijadas desde la
mezcla; no se trata de una separación disponible en el dispositivo.

Para verificar las métricas guardadas y regenerar las figuras y tablas:

```bash
.venv/bin/python seccion_2_5/src/graficar_comparacion.py
```

Este comando lee los resultados existentes con benchmark; no vuelve a ejecutar
los filtros ni a medir tiempos. Puede usar `--resultados RUTA` para una carpeta
alternativa con los mismos archivos exportados. Antes de graficar comprueba
la correspondencia entre CSV, JSON, fuentes NPZ, protocolo y código evaluado.

Las seis figuras se guardan en `resultados/figuras/` en PNG de 300 dpi y SVG.
Las cuatro tablas están en [el resumen de resultados](resultados/resumen_2_5.md).
La revisión numérica y visual está documentada en
[el registro del paso 5](../revision/paso_5/README.md). Regenerar las figuras
marca su revisión visual como pendiente hasta volver a inspeccionarlas.

La documentación incluye las condiciones de fallo y el diseño de procesamiento
embebido propuesto. Sus cálculos están en
[el registro del paso 7](../revision/paso_7/README.md).
Las bibliotecas y el presupuesto refinado están en
[el registro del paso 8](../revision/paso_8/README.md).
La arquitectura y comunicación están en
[el registro del paso 9](../revision/paso_9/README.md). El contenido está integrado en el
[informe LaTeX grupal](../informe/informe.tex), preparado en el paso 10.
El [notebook final](../entrega/tarea1/notebook.ipynb) integra
la ejecución desde cero y el [paquete portable](../entrega/tarea1/README.md)
está verificado para la entrega final con la etiqueta `tarea1_prototipo`.

Se usó asistencia de IA para implementar el evaluador y las pruebas. Se
verificaron métricas con casos de resultado conocido, equivalencia temporal
con SciPy, identidad espectral y descomposición en los tres casos oficiales.
