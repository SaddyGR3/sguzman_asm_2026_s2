## Sección 2.2 - Generación de señales con ruido

Se generan las señales que vamos a utilizar para probar los algoritmos de filtrado de las demás secciones.

Utilicé el generador de señales del profe y lo adapté para crear 3 casos diferentes:

- Caso 1: Interferencia sinusoidal de 2150 Hz, SNR de 0 dB.
- Caso 2: Ruido blanco gaussiano, SNR de 5 dB.
- Caso 3: Ruido de banda entre 900 y 1300 Hz, SNR de 3 dB.

En los tres casos se utiliza una señal limpia con frecuencias de 300, 700 y 1100 Hz.

### Parámetros
- Frecuencia de muestreo: 8000 Hz.
- Cantidad de muestras: 8192.
- Tamaño de bloque: 1024 muestras.

### Archivos

Dentro de la carpeta `pruebas` están los tres casos separados.

Cada caso tiene:
- `01_referencia_limpia.wav`: señal original.
- `02_ruido.wav`: ruido generado.
- `03_entrada_contaminada.wav`: señal con ruido.
- `muestras_exactas.npz`: las tres señales en arreglos de NumPy.
- `metadatos_prueba.json`: información de la generación.

Para trabajar con los filtros, les recomiendo usar `muestras_exactas.npz`, ya que contiene las señales sin la cuantización de los archivos WAV.

Pueden cargar las señales así:

import numpy as np

datos = np.load("2_2_generacionsenales/pruebas/caso_1/muestras_exactas.npz")

limpia = datos["limpia"]
ruido = datos["ruido"]
contaminada = datos["contaminada"]

La variable `contaminada` es la que deben pasar por los filtros y `limpia` les sirve para comparar los resultados.

### Resultados

También agregué gráficas para cada caso:
- Señales en el tiempo.
- Magnitud espectral.
- Fase espectral.
- Energía por bandas.

Están guardadas en `resultados/figuras`, separadas por caso.

Además, hice un análisis del ruido generado y obtuve:

- Caso 1: frecuencia detectada de 2150.39 Hz.
- Caso 2: distribución de energía bastante uniforme (CV = 3.64 %).
- Caso 3: banda detectada entre 870.12 y 1327.15 Hz.

Estos resultados están guardados en archivos JSON dentro de `resultados/identificacion_ruido`.


