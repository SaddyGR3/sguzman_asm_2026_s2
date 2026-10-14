# Resultados comparativos verificados de 2.5

Tablas generadas desde `resultados_2_5.json` y contrastadas con `metricas.csv`
y las muestras NPZ. El redondeo se aplica solo a la presentación.

## Calidad reconstruida

8174 muestras comunes; FIR compensado 18 muestras; entrada y espectral sin
desplazamiento. La SNR de entrada se recalcula sobre ese mismo intervalo.

| Caso | Método | SNR entrada (dB) | SNR salida (dB) | ΔSNR (dB) | MSE |
|---|---|---|---|---|---|
| 1 | Sin filtrar | 0.010 | 0.010 | 0.000 | 5.622400e-02 |
| 1 | FIR temporal | 0.010 | 51.911 | 51.901 | 3.628906e-07 |
| 1 | Espectral | 0.010 | 32.166 | 32.156 | 3.422115e-05 |
| 2 | Sin filtrar | 5.009 | 5.009 | 0.000 | 1.099230e-02 |
| 2 | FIR temporal | 5.009 | 9.524 | 4.514 | 3.887311e-03 |
| 2 | Espectral | 5.009 | 20.813 | 15.804 | 2.888661e-04 |
| 3 | Sin filtrar | 3.010 | 3.010 | 0.000 | 1.838450e-02 |
| 3 | FIR temporal | 3.010 | 3.071 | 0.061 | 1.812801e-02 |
| 3 | Espectral | 3.010 | 14.677 | 11.667 | 1.252343e-03 |

## Conservación útil y atenuación del ruido

La componente útil y el ruido residual se obtienen fijando las ganancias
aprendidas de la mezcla. La energía total incluye ruido; no se interpreta
como energía útil. Banda del caso 1: 2130–2170 Hz; caso 3: 900–1300 Hz.
El caso 2 no tiene una interferencia dominante única.

| Caso | Método | Útil conservada (%) | Energía total (%) | Ruido total: atenuación (dB) | Interferencia en banda: atenuación (dB) |
|---|---|---|---|---|---|
| 1 | Sin filtrar | 100.000 | 199.779 | 0.000 | 0.000 |
| 1 | FIR temporal | 99.643 | 99.643 | 55.556 | 64.971 |
| 1 | Espectral | 100.000 | 100.061 | 32.156 | 59.259 |
| 2 | Sin filtrar | 100.000 | 132.155 | 0.000 | No aplica |
| 2 | FIR temporal | 99.643 | 111.400 | 4.514 | No aplica |
| 2 | Espectral | 99.016 | 100.170 | 17.222 | No aplica |
| 3 | Sin filtrar | 100.000 | 151.730 | 0.000 | 0.000 |
| 3 | FIR temporal | 99.643 | 150.677 | 0.061 | 0.053 |
| 3 | Espectral | 99.764 | 104.936 | 11.766 | 11.282 |

## Ganancias de tonos útiles

Ajuste conjunto de senos, cosenos y DC sobre la componente útil separada.
Estos valores no son los de amplitud observada en la mezcla con ruido.

| Caso | Método | Ganancia 300 Hz (dB) | Ganancia 700 Hz (dB) | Ganancia 1100 Hz (dB) |
|---|---|---|---|---|
| 1 | Sin filtrar | 0.0000 | 0.0000 | 0.0000 |
| 1 | FIR temporal | -0.0170 | -0.0174 | 0.0070 |
| 1 | Espectral | 0.0000 | 0.0000 | 0.0000 |
| 2 | Sin filtrar | 0.0000 | 0.0000 | 0.0000 |
| 2 | FIR temporal | -0.0170 | -0.0174 | 0.0070 |
| 2 | Espectral | -0.0268 | -0.0407 | -0.0795 |
| 3 | Sin filtrar | 0.0000 | 0.0000 | 0.0000 |
| 3 | FIR temporal | -0.0170 | -0.0174 | 0.0070 |
| 3 | Espectral | -0.0023 | -0.0022 | -0.0827 |

## Tiempo y memoria en PC

Equipo: 12th Gen Intel(R) Core(TM) i5-12450H. Tres calentamientos y 30 repeticiones.
La mediana por 1024 muestras es el tiempo de captura dividido entre ocho;
el P95 corresponde a la captura completa. El método espectral usa 17 tramas
con relleno. El pico es adicional, excluye entrada y coeficientes previos y
puede omitir buffers nativos; no sumar las columnas de memoria. Entrada
float64: 65536 bytes. Persistencia espectral cero entre llamadas, con sus
matrices incluidas en el pico. Son implementaciones de PC: FIR con bucles
Python y espectral vectorizado en NumPy. No extrapolar estos tiempos a ESP32.

| Caso | Método | Mediana por 1024 (ms) | P95 captura (ms) | Persistencia lógica (bytes) | Pico adicional trazado (bytes) |
|---|---|---|---|---|---|
| 1 | Sin filtrar | 0.000 | 0.000 | 0 | 0 |
| 1 | FIR temporal | 6.163 | 72.844 | 592 | 133329 |
| 1 | Espectral | 0.123 | 2.262 | 0 | 989751 |
| 2 | Sin filtrar | 0.000 | 0.000 | 0 | 0 |
| 2 | FIR temporal | 5.272 | 45.915 | 592 | 133329 |
| 2 | Espectral | 0.250 | 2.259 | 0 | 1067580 |
| 3 | Sin filtrar | 0.000 | 0.000 | 0 | 0 |
| 3 | FIR temporal | 5.821 | 47.989 | 592 | 133329 |
| 3 | Espectral | 0.161 | 1.563 | 0 | 1067487 |

## Figuras

- [Caso 1](figuras/caso_1_comparacion.png).
- [Caso 2](figuras/caso_2_comparacion.png).
- [Caso 3](figuras/caso_3_comparacion.png).
- [Resumen de calidad](figuras/resumen_calidad.png).
- [Energía útil y tonos](figuras/energia_y_tonos.png).
- [Recursos de PC](figuras/recursos_pc.png).

Cada figura tiene una versión PNG de 300 dpi y una versión SVG. En los
espectros se usa un periodograma Hann unilateral sobre el tramo común,
sin quitar DC; el piso de visualización es −160 dB y no altera las métricas.
El intervalo temporal ilustrado es 100–120 ms; no representa toda la captura.
El PSD del error incluye ruido y distorsión.

La decisión por caso y las condiciones de fallo se desarrollan en el paso 6.
El algoritmo espectral permanece fuera de línea. La comparación directa
sobre 8192 muestras se conserva en CSV/JSON, separada de estas tablas.
