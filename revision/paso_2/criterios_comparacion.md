# Paso 2: criterios comunes para la comparación de 2.5

Estado: definido para implementar el evaluador en el paso 4.
Fecha: 12 de octubre de 2026.

Estos criterios resuelven los pendientes numéricos de la revisión del paso 1.
Todavía no son los resultados finales de 2.5. La configuración ejecutable
prevista se registra en `protocolo.json`; no se modifican los algoritmos de
los compañeros. La referencia normativa son las fórmulas del apartado 2.5
del enunciado local de la Tarea 1.

## 1. Datos y métodos que se compararán

Se usarán únicamente los tres NPZ oficiales de 2.2, con sus metadatos y
hashes verificados en el paso 1. No se regenerarán ni normalizarán por separado
las señales para mejorar las métricas. Los WAV se conservan para reproducción;
las mediciones usan los arreglos exactos, sin su cuantización.

| Parámetro | Valor común |
|---|---|
| Frecuencia de muestreo | 8000 Hz |
| Longitud de captura | 8192 muestras, 1.024 s |
| Bloque nominal | 1024 muestras, 128 ms |
| Tonos útiles | 300, 700 y 1100 Hz |
| Semillas, casos 1–3 | 202601, 202602 y 202603 |
| Precisión de evaluación | `float64`; FFT compleja `complex128` |

La tabla principal tendrá nueve filas: entrada sin filtrar, FIR temporal y
salida espectral seleccionada para cada uno de los tres casos.

- **Temporal:** FIR Kaiser de orden 36, 37 coeficientes; paso 1200 Hz,
  rechazo 1800 Hz y atenuación de diseño 40 dB. Usar la implementación
  manual por bloques, conservando estados e iniciándolos en cero por captura.
- **Espectral:** `N=1024`, salto `H=512`, solape 50 %, ventana raíz de Hann
  periódica en análisis y síntesis. Caso 1: `picos`; casos 2 y 3: `resta`.
  Mantener los parámetros del evaluador de 2.4, registrados en el JSON.
- **Entrada:** identidad; su salida es la señal contaminada.

El IIR candidato y `top_k` pueden aparecer como material adicional; no
sustituyen los métodos elegidos. La selección espectral depende del tipo de
ruido registrado: no se presentará como clasificación automática.

## 2. Retardo y tramo común

La evaluación principal mide calidad después de compensar el retardo conocido
del FIR. No se buscará por correlación el desplazamiento que dé mejor SNR.

| Método | Retardo de índices a compensar |
|---|---:|
| Entrada | 0 muestras |
| FIR | 18 muestras = 2.25 ms |
| Espectral reconstruido | 0 muestras |

Sea `L=8192`, `d_max=18`, `K=L-d_max=8174`. Para todos los métodos:

```text
referencia = limpia[0:8174]
entrada_referencia = contaminada[0:8174]
salida_entrada = contaminada[0:8174]
salida_temporal = temporal[18:8192]
salida_espectral = espectral[0:8174]
```

Las métricas principales usan esos mismos 8174 instantes de referencia,
equivalentes a 1.02175 s. La SNR de entrada se recalcula sobre ese tramo:
puede diferir ligeramente de los 0, 5 y 3 dB de la captura completa.
No se añadirán muestras finales inventadas ni se descartarán transitorios
adicionales en la tabla principal. Se conservan los fades de las señales.

Se calculará además MSE, SNR y ΔSNR **sin compensación sobre las 8192
muestras**, para cada método, con un sufijo `directo`. Esa tabla secundaria
documenta el efecto del retardo; no se mezcla con la principal.

Compensar índices es una operación de evaluación, no una forma de eliminar
la latencia física. Que la reconstrucción espectral conserve índices tampoco
significa que sea instantánea: su estimación actual usa la captura completa.

## 3. MSE, SNR y mejora

Para la referencia `s` y salida evaluada `y`, ambas de longitud `K`:

\[
e[n]=s[n]-y[n],\quad
E_s=\sum_{n=0}^{K-1}s[n]^2,\quad
E_e=\sum_{n=0}^{K-1}e[n]^2,
\]

\[
\operatorname{MSE}=E_e/K,\qquad
\operatorname{SNR}=10\log_{10}(E_s/E_e),\qquad
\Delta\operatorname{SNR}=\operatorname{SNR}_{salida}-\operatorname{SNR}_{entrada}.
\]

No se restará DC ni se cambiará la ganancia antes de medir estas métricas.
La SNR incluye distorsión y ruido residual en el error; no se calculará
usando energía total de salida como numerador. Para la fila de entrada,
ΔSNR es cero. Un error exactamente cero da SNR `+inf`; referencia con energía
cero es inválida para estos experimentos. No se añadirán epsilons que alteren
el resultado. Se guardan valores completos y se redondea solo al presentar.
Para conservar JSON válido, representar infinitos como cadenas `"+inf"` o
`"-inf"`; usar `null` para valores no definidos. En CSV usar `+inf`, `-inf`
y celda vacía, respectivamente.

## 4. Energía útil y ruido residual: descomposición de referencia

Para no contar ruido como energía útil, se usará una descomposición que
aprovecha las fuentes conocidas de las señales sintéticas.

En el temporal, aplicar el mismo FIR, con estados iniciales cero, a `limpia`
y a `ruido` por separado. En el espectral, primero obtener las ganancias
`G` procesando **solo la entrada contaminada**. Después fijar esas ganancias
y aplicar exactamente la misma cadena de DC, relleno, ventanas, FFT/IFFT,
solapamiento y recorte a limpia y ruido, por separado. No volver a estimar
ganancias usando la señal limpia o el ruido aislado.

Con `T_G` como operador lineal de reconstrucción para ganancias fijas:

\[
y=T_G(s+r)=y_s+y_r,\quad y_s=T_G(s),\quad y_r=T_G(r).
\]

Restar y restaurar la media de cada componente forma parte de este operador
lineal. Para el FIR, `T_G` se sustituye por su convolución causal. Para la
entrada, `y_s=s` y `y_r=r`. Alinear y recortar `y_s` y `y_r` como en el inciso 2.

La conservación de energía útil se define como:

\[
C_u=100\frac{\sum y_s[n]^2}{\sum s[n]^2}\quad[\%].
\]

No se limita artificialmente a 100 %: un valor mayor indica amplificación.
Tampoco basta para demostrar baja distorsión, porque no penaliza por sí sola
todos los cambios de fase; se interpreta junto con MSE, SNR y ganancias por
tono. La energía total `100·sum(y²)/sum(s²)` se puede guardar como diagnóstico,
con el nombre explícito de energía total, nunca como conservación útil.

Esta separación es **condicional a las ganancias aprendidas de la mezcla**.
Es una evaluación con fuentes conocidas, no una recuperación perfecta
disponible en ESP32 ni el resultado de ejecutar el algoritmo adaptativo sobre
limpia sola. El ruido que coincide con frecuencias útiles puede sobrevivir.

Se verificará `max(abs(y-y_s-y_r)) < 1e-12` sobre la captura completa.
Una comprobación exploratoria de viabilidad con los tres casos dio errores
máximos entre `2.05e-16` y `3.49e-16`. No se usó para ajustar parámetros.

Como diagnóstico de distorsión, ajustar conjuntamente seno y coseno en
300, 700 y 1100 Hz y un término DC, tanto sobre `s` como sobre `y_s` alineada.
Informar por tono `20·log10(A_salida/A_referencia)`. Es un ajuste sobre el tramo
con fades incluido; usar la misma base y tramo en ambas señales.

## 5. Atenuación

Habrá una medida comparable para todos los casos, usando el ruido residual
de la descomposición anterior:

\[
A_r=10\log_{10}\left(\frac{\sum r[n]^2}{\sum y_r[n]^2}\right)\quad[\mathrm{dB}].
\]

La referencia `r` y `y_r` usan el tramo y alineamiento principal. Atenuación
positiva significa reducción; negativa, amplificación. Esta métrica no
incluye distorsión de la señal útil, que se informa por separado.

Además se medirá la atenuación de la interferencia en su banda:

| Caso | Banda de evaluación |
|---|---|
| 1 | 2130–2170 Hz, ±20 Hz alrededor de 2150 Hz |
| 2 | No aplica: ruido blanco sin una interferencia dominante única |
| 3 | 900–1300 Hz; banda interferente, no un tono aislado |

Aplicar la misma Hann periódica de longitud `K` a `r` y `y_r`, calcular rFFT
y sumar `peso·abs(R[k])²/K` en la banda, extremos incluidos. El peso es 2 para
bins interiores y 1 para DC y Nyquist si existe. El cociente de esas sumas
define la atenuación en dB. No se iguala esta energía ventaneada a la energía
temporal sin ventana. La banda de ±20 Hz incluye el lóbulo principal de la
interferencia con la resolución de evaluación cercana a 0.979 Hz.

No se usará la energía de la salida contaminada en la banda como si fuera
ruido puro, especialmente en el caso 3. Para el caso 2 guardar `null` en JSON
y una celda vacía en CSV para la banda dominante; no inventar una frecuencia.
Potencia residual cero da atenuación `+inf`; potencia inicial cero da una
métrica no definida.

## 6. Tiempo y latencia

Medir con `perf_counter_ns`, tres ejecuciones de calentamiento y 30
repeticiones por caso y método. Reiniciar los estados por captura en cada
repetición. Excluir carga de archivos, diseño de coeficientes, métricas,
descomposición de fuentes, gráficas y escritura de resultados. Incluir
asignaciones, validaciones y diagnósticos que los filtros actuales realizan
internamente. Registrar máquina y versiones de las dependencias.
Alternar el orden de los dos filtros entre repeticiones para reducir el
efecto de cambios de carga o temperatura durante la medición.

La medición común es el procesamiento completo de las 8192 muestras. Guardar
mediana, percentil 95 y máximo. Informar también:

- **Tiempo equivalente por 1024 muestras:** tiempo de captura dividido entre
  8 bloques nominales. Sirve para comparar carga por la misma cantidad de
  entrada; no es el tiempo medido individual de cada trama espectral.
- **Razón tiempo/audio:** tiempo de captura dividido entre 1.024 s.
- **Tramas espectrales reales:** 17, incluyendo relleno; el coste medio
  amortizado por trama es tiempo de captura dividido entre 17. No representa
  el peor tiempo por trama ni un límite de tiempo real.

El solape implica un salto de 64 ms, mientras que la ventana cubre 128 ms.
Los 2.25 ms del FIR corresponden a retardo de grupo. Reportarlos en columnas
separadas del tiempo de CPU. No deducir una latencia causal del algoritmo
espectral fuera de línea ni afirmar cumplimiento de plazos en ESP32 con
estas mediciones de PC. La propuesta causal se desarrolla en el paso 7.

La identidad se informa con coste de filtrado cero como referencia: no
medir una copia arbitraria de la entrada como un algoritmo de reducción.

## 7. Memoria aproximada

Separar tres conceptos para no mezclar números incompatibles:

1. **Datos persistentes del algoritmo:** coeficientes, estados y tablas.
   Contar bytes de arrays con `nbytes`, sin contar dos veces vistas de la
   misma asignación. Los arrays preexistentes del banco de pruebas se
   identifican por separado.
2. **Pico adicional trazado en PC:** en una ejecución aparte, sin medir
   tiempo simultáneamente, iniciar `tracemalloc` después de cargar entrada
   y coeficientes y registrar el máximo durante el procesamiento completo.
   Es una aproximación de asignaciones trazadas; no captura necesariamente
   todos los buffers nativos, la memoria del intérprete ni el RSS total.
   Registrar entrada y coeficientes preasignados por separado. Incluir en el
   pico las salidas y ganancias que la función retiene.
3. **Presupuesto futuro en ESP32:** calcular explícitamente buffers de
   entrada/salida, estados, ventanas, FFT, ganancias y comunicación según
   precisión y biblioteca elegidas. No convertir el pico de Python en una
   estimación directa de RAM de firmware.

El FIR especializado requiere 37 coeficientes y 36 estados: 584 bytes en
float64 o 292 bytes en float32, sin buffers, overhead ni copias transitorias.
La rutina genérica también mantiene `a=[1]`; se debe distinguir su
almacenamiento real del presupuesto especializado de 73 valores.
El espectral actual conserva matrices de 17 tramas; no presupuestarlo como
si solo mantuviera una trama. La captura de entrada ocupa 65536 bytes en
float64; contabilizarla por separado con el mismo criterio para ambos métodos.

## 8. Interpretación, controles y salida prevista

No elegir el método solo por atenuación o conservación de energía. Examinar
SNR/MSE, ganancia de cada tono, reducción del ruido, latencia y coste juntos.
La elección se justificará por caso; una conclusión general deberá explicar
qué casos y restricciones prioriza. Los resultados previos son exploratorios:
este documento no pretende ser un registro previo a cualquier medición.

Controles mínimos del evaluador:

- Confirmar hashes, longitudes, semillas, `fs` y sumatoria limpia + ruido.
- Verificar que la entrada sin filtrar tenga conservación útil 100 %,
  atenuación 0 dB y ΔSNR 0 dB.
- Usar retardo FIR fijo de 18 muestras y comprobar simetría de coeficientes.
- Confirmar descomposición con ganancias fijas y reconstrucción identidad.
- No pasar limpia, ruido aislado ni la frecuencia exacta de interferencia al
  filtro espectral. Solo el evaluador conoce esas fuentes para medir.
- Verificar que `MSE = E_error/K` y que las tres filas de cada caso comparten
  exactamente la misma SNR de entrada y referencia.

El evaluador generará `metricas.csv`, JSON con configuración, resultados sin
redondear y notas metodológicas, y figuras de tiempo y espectro. Las columnas
previstas están enumeradas en `protocolo.json`. Los resultados de calidad
alineados y directos se distinguirán por sus nombres y longitud de evaluación.

Se utilizó asistencia de IA para formular estos criterios, revisar el código
existente y comprobar la viabilidad numérica de la descomposición espectral.
La evaluación final se verificará con el código del paso 4 y sus controles.
