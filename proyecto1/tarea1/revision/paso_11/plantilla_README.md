# Tarea 1 — caracterización espectral y reducción de ruido

Código, señales y resultados de la comparación entre un FIR temporal y un método FFT/IFFT, con una propuesta de implementación en tres ESP32.

## Autores

- Saddy Guzman Rojas — 2023088184
- David García Cruz — 2024115575
- Válerin Calderón Bran — 2020033313
- Luis Castro Montenegro — 2013083843

Repositorio: [sguzman_asm_2026_s2](https://github.com/SaddyGR3/sguzman_asm_2026_s2), rama `integracion-tarea1`. La etiqueta local registrada `tarea1_prototipo` identifica el cierre inicial del repositorio.

## Archivos principales

| Archivo o carpeta | Contenido |
|---|---|
| [informe.pdf](informe.pdf) | Fundamentos, diseño, resultados, conclusiones y referencias. |
| [notebook.ipynb](notebook.ipynb) | Ejecución completa de los apartados 2.1–2.5. |
| [src/](src/) | Generación, análisis, filtros y métricas. |
| [pruebas/](pruebas/) | Tres casos con NPZ, WAV y metadatos; pruebas automáticas. |
| [resultados/metricas.csv](resultados/metricas.csv) | Mediciones citadas en el informe. |
| [resultados/figuras/](resultados/figuras/) | Gráficas citadas en el informe. |
| [resultados/regenerados/](resultados/regenerados/) | Resultados de una ejecución nueva del notebook. |
| [metadatos/configuraciones.json](metadatos/configuraciones.json) | Parámetros y semillas de los tres casos. |
| [metadatos/protocolo.json](metadatos/protocolo.json) | Alineamiento y criterios de comparación. |

## Ejecutar el notebook

El entorno comprobado usa Python 3.12.14. Desde esta carpeta, crear un entorno e instalar las dependencias:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

En Windows:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Abrir `notebook.ipynb` en VS Code, seleccionar ese entorno como kernel y ejecutar todas las celdas en orden con un kernel nuevo. `requirements-lock.txt` conserva también las versiones transitivas comprobadas.

La ejecución regenera señales, WAV, metadatos, demostraciones FFT, respuesta del FIR, filtros espectrales, pruebas, métricas y figuras. Incluye un barrido de sustracción sin protección tonal. No descarga datos ni necesita archivos externos al paquete; las dependencias deben instalarse previamente.

Las mediciones del informe se conservan en `resultados/`. El notebook escribe en `resultados/regenerados/`, para no sustituirlas con tiempos obtenidos en otro equipo. Su calidad se compara con las cifras de referencia; los tiempos y picos de memoria pueden variar.

## Criterios de comparación

Las capturas tienen 8192 muestras a 8 kHz, con tonos útiles de 300, 700 y 1100 Hz. La comparación principal usa 8174 muestras, compensando 18 muestras de retardo del FIR. Los experimentos de 2.4 sobre captura completa se informan aparte.

La energía útil se mide reutilizando las ganancias espectrales calculadas desde la mezcla sobre la referencia limpia. No equivale a energía total de salida. El filtro actual estima DC y piso de ruido sobre toda la captura: es una referencia fuera de línea. Los recursos y plazos de ESP32 son estimaciones aún sin pruebas en placa.

`metadatos/huellas_muestras.json` identifica las muestras congeladas. El notebook comprueba esas huellas antes de actualizar los hashes de los NPZ regenerados. Una diferencia numérica o una alteración de datos detiene esa comprobación.

El JSON de `resultados/` conserva el entorno y las huellas de los archivos originales usados para las mediciones del informe. Sus rutas documentan esa procedencia. El JSON de `resultados/regenerados/` identifica los archivos de la ejecución del paquete; es el que utiliza el verificador de resultados.

## Pruebas y comprobación de archivos

El notebook ejecuta ocho scripts temporales, cuatro pruebas espectrales y nueve de comparación. Las pruebas comprueban equivalencia con SciPy, continuidad, reconstrucción, adaptación a interferencia desplazada, métricas conocidas y rechazo de datos alterados. Los registros se guardan en `resultados/regenerados/`.

En Linux, la integridad del paquete se verifica con:

```bash
sha256sum -c MANIFEST.sha256
```

El manifiesto describe los archivos distribuidos; volver a ejecutar el notebook modifica algunos de ellos y sus hashes.

El [informe PDF](informe.pdf) contiene la comparación detallada, las referencias y la propuesta para ESP32.

Se usó IA como apoyo para explicar filtros, comparar métodos, elaborar scripts y gráficos, verificar cálculos e integrar los aportes y borradores. La ejecución y las pruebas contrastan los resultados con las señales y referencias incluidas. La validación física del sistema queda fuera del prototipo en PC.
