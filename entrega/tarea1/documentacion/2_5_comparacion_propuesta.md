# 2.5 Comparación y propuesta para el sistema embebido

**Estado:** evaluación común, tablas, figuras y análisis comparativo completados
en los pasos 4–6. El diseño de procesamiento para ESP32 está propuesto en
el paso 7, las bibliotecas se seleccionaron en el paso 8 y la arquitectura
y comunicación se definieron en el paso 9. Este archivo servirá como
base para integrar la sección en el informe LaTeX del grupo.

## Objetivo

Comparar la entrada sin filtrar, el FIR temporal y la salida espectral en
los tres casos oficiales. Justificar las decisiones para el sistema embebido
mediante resultados medidos y un presupuesto de procesamiento, memoria y
comunicación.

## Metodología común

Aplicar el protocolo del paso 2, que define datos, parámetros, alineamiento,
descomposición de fuentes, métricas y medición de recursos:

- Criterios de comparación (ruta en el repositorio: `revision/paso_2/criterios_comparacion.md`).
- Configuración del evaluador (ruta en el repositorio: `revision/paso_2/protocolo.json`).

La comparación principal compensa las 18 muestras del FIR y utiliza
8174 muestras comunes. También se informan las métricas directas.
La energía útil se separa del ruido residual mediante una evaluación
condicional con ganancias espectrales fijadas desde la mezcla.

El evaluador, las instrucciones y los controles están descritos en el
README de la sección (ruta en el repositorio: `seccion_2_5/README.md`). Los resultados numéricos se encuentran
en el CSV (ruta en el repositorio: `seccion_2_5/resultados/metricas.csv`) y
el JSON de resultados (ruta en el repositorio: `seccion_2_5/resultados/resultados_2_5.json`).

## Resultados comparativos

Las cuatro tablas, sus unidades y las notas de interpretación están en
el resumen generado (ruta en el repositorio: `seccion_2_5/resultados/resumen_2_5.md`). Las seis figuras revisadas
presentan señales temporales, PSD de señales y errores, calidad reconstruida,
conservación útil, ganancias por tono y recursos en PC.

| Caso | SNR entrada (dB) | SNR FIR (dB) | SNR espectral (dB) |
|---|---:|---:|---:|
| 1: tonal separada | 0.010 | 51.911 | 32.166 |
| 2: blanco | 5.009 | 9.524 | 20.813 |
| 3: superposición parcial | 3.010 | 3.071 | 14.677 |

La revisión numérica contrastó CSV y JSON y recalculó métricas desde las
muestras NPZ. El registro de revisión (ruta en el repositorio: `revision/paso_5/README.md`)
describe las comprobaciones y la inspección visual.

La figura del caso 1 muestra que ambos filtros atenúan la componente de
2150 Hz; el FIR alcanza menor error global. En el caso 2, el FIR conserva
parte del ruido dentro de su banda de paso, mientras la reducción espectral
reduce el error más ampliamente. En el caso 3, el FIR deja casi intacto el
ruido entre 900 y 1300 Hz, que se superpone con el tono útil de 1100 Hz.

La conservación de energía útil es alta en todos los casos: el FIR alcanza
99.643 %, y el espectral 100.000 %, 99.016 % y 99.764 %, respectivamente.
Estos porcentajes corresponden a las fuentes separadas con ganancias fijas,
no a la energía total de la salida. No demuestran ausencia de distorsión.

Los gráficos de recursos describen implementaciones diferentes en PC: FIR
manual con bucles Python y espectral vectorizado con NumPy. La comparación
de esos tiempos no determina cuál será más rápido en ESP32. El presupuesto
de firmware y la adaptación causal permanecen pendientes.

Calidad reconstruida de los tres casos (ruta en el repositorio: `seccion_2_5/resultados/figuras/resumen_calidad.png`)

## Elección del método por caso

La elección siguiente prioriza menor MSE y mayor SNR respecto de la señal
limpia, sobre el intervalo común con retardo compensado. En ese intervalo,
ambas métricas producen la misma clasificación porque la referencia y su
energía son iguales para todos los métodos. No se elige por energía total
de salida, que puede aumentar por el ruido residual.

| Caso | Método preferido para calidad | MSE FIR | MSE espectral | Ventaja del ganador en SNR | MSE del perdedor / ganador |
|---|---|---:|---:|---:|---:|
| 1: interferencia tonal de 2150 Hz | FIR pasa bajos | 3.629 × 10⁻⁷ | 3.422 × 10⁻⁵ | 19.745 dB | 94.30 |
| 2: ruido blanco | Espectral, resta con protección tonal | 3.887 × 10⁻³ | 2.889 × 10⁻⁴ | 11.290 dB | 13.46 |
| 3: ruido entre 900 y 1300 Hz | Espectral, resta con protección tonal | 1.813 × 10⁻² | 1.252 × 10⁻³ | 11.606 dB | 14.48 |

Estas conclusiones describen las tres capturas y configuraciones evaluadas.
No constituyen una garantía para cualquier señal o nivel de ruido.

### Caso 1: separación entre banda útil e interferencia

Los tonos útiles de 300, 700 y 1100 Hz quedan dentro de la banda de paso
del FIR, mientras la interferencia de 2150 Hz queda por encima de su borde
de rechazo de 1800 Hz. Esa separación permite reducir el ruido sin eliminar
los tonos útiles. El FIR mejora la SNR en 51.901 dB, conserva 99.643 % de
la energía útil y atenúa 64.971 dB la interferencia en la banda de
2130–2170 Hz. Las ganancias de los tres tonos están entre −0.018 y
+0.007 dB, por lo que la distorsión de amplitud observada es pequeña.

El espectral con detección de picos también funciona: mejora la SNR en
32.156 dB y conserva prácticamente toda la energía útil. Sin embargo,
su menor distorsión útil no compensa el mayor ruido residual global.
La atenuación de 59.259 dB en la banda de interferencia no equivale a la
atenuación total de ruido de 32.156 dB: son mediciones diferentes, y la
primera incorpora la ponderación de una ventana Hann en el análisis.

Un diagnóstico exploratorio de las salidas guardadas sitúa el 98.983 %
de la energía de error espectral en las primeras y últimas 512 muestras
del intervalo común, que representan 12.528 % de dicho intervalo.
Esto evidencia una concentración del error en los extremos. La cadena de
ventanas, relleno y reconstrucción es una explicación posible; atribuir
el error a una operación específica requeriría un experimento adicional.
No se eliminan esos extremos ni se modifica la clasificación principal.
Las derivaciones y su procedencia están en
el registro del paso 6 (ruta en el repositorio: `revision/paso_6/README.md`).

### Caso 2: ruido distribuido dentro y fuera de la banda útil

El FIR reduce el ruido blanco fuera de su banda de paso, pero deja pasar
gran parte del que comparte banda con la señal. Por eso mejora la SNR
solamente 4.514 dB, aunque conserva los tonos útiles. Su energía total de
salida equivale al 111.400 % de la energía limpia; el excedente no es
una mejora de la señal, sino que incluye ruido residual y términos cruzados.

La resta espectral estima el piso de ruido y atenúa bins según su relación
con ese piso, con protección de tonos estables. Alcanza una mejora de SNR
de 15.804 dB y una atenuación total de ruido de 17.222 dB. La diferencia
entre estas dos cifras muestra que eliminar ruido también puede introducir
distorsión útil. Conserva 99.016 % de energía útil; sus ganancias a
300, 700 y 1100 Hz son −0.027, −0.041 y −0.079 dB, respectivamente.
El compromiso observado favorece al espectral por su menor error total.

### Caso 3: superposición con el tono útil de 1100 Hz

El ruido de 900–1300 Hz coincide con la banda de paso y con uno de los
tonos útiles. El FIR mejora la SNR apenas 0.061 dB y atenúa 0.053 dB
el ruido de esa banda: conserva la señal, pero también la interferencia.
Reducir el corte o introducir un rechazo alrededor de 1100 Hz afectaría
al tono que debe conservarse.

La resta espectral aprovecha la estructura de tonos estables para proteger
sus bins mientras reduce el piso de ruido en otros bins. Mejora la SNR
11.667 dB y atenúa 11.282 dB el ruido de 900–1300 Hz. La conservación
útil de 99.764 % y la ganancia de −0.083 dB del tono de 1100 Hz indican
un compromiso favorable en esta captura, aunque persiste ruido residual.
La protección no separa de forma perfecta las dos fuentes en los bins
que comparten: ambas reciben la misma ganancia una vez fijada la máscara.

## Compromiso entre reducción y distorsión

La conservación de energía útil debe leerse junto con MSE y ganancias por
tono. Un valor cercano a 100 % puede coexistir con errores de fase,
transitorios o una redistribución de amplitudes. Tampoco debe confundirse
con la energía total de salida.

La evaluación condicional permite escribir, para cada salida,
`y = y_util + y_ruido`. El error es
`e = (s − y_util) − y_ruido`; por tanto, el MSE incluye distorsión útil,
ruido residual y un término cruzado. No es correcto sumar únicamente
las dos energías y asumir que siempre son independientes. En el método
espectral, esta descomposición usa ganancias aprendidas desde la mezcla
y después congeladas; no entrega al filtro las referencias limpias ni
representa una separación de fuentes disponible en el firmware.

El experimento adicional de 2.4 con ruido blanco y protección tonal
desactivada muestra el riesgo de aumentar la reducción indiscriminadamente:

| Factor de resta α | SNR de salida (dB) | Atenuación fuera de los tonos (dB) | Ganancia del tono de 1100 Hz (dB) |
|---|---:|---:|---:|
| 2 | 16.938 | 20.616 | −2.707 |
| 3 | 14.737 | 25.852 | −4.277 |
| 8 | 7.643 | 25.984 | −15.582 |

Entre α = 2 y α = 8, la atenuación adicional se obtiene a costa de una
pérdida importante del tono útil y una SNR menor. Este experimento se
evalúa sobre **8192 muestras y sin protección tonal**; no se mezcla con
la comparación principal de 8174 muestras. La configuración elegida para
los casos 2 y 3 mantiene α = 3 y protección tonal activada. Los datos
del experimento están en
los resultados originales de 2.4 (ruta en el repositorio: `seccion_2_4/resultados/resultados_2_4.json`).

## Condiciones de fallo y alcance

| Método | Condición | Efecto y evidencia |
|---|---|---|
| FIR pasa bajos | Ruido dentro de la banda de paso | Reducción limitada en el caso 2 y prácticamente nula en el caso 3. |
| FIR pasa bajos | Contenido útil fuera de la banda prevista | Se atenuaría junto con el ruido; es una consecuencia del diseño, no una prueba realizada con otra señal. |
| Detección espectral de picos | Interferencia dentro de 0–1200 Hz o ruido distribuido | La banda protegida impide rechazar esos picos y un detector de máximos no elimina un piso ancho. En 2.4, usar picos en los casos 2 y 3 deja la SNR aproximadamente en 5 y 3 dB, respectivamente, en la evaluación directa original. |
| Resta espectral | Factor de resta excesivo o protección insuficiente | Puede eliminar señal útil; el experimento anterior lo mide al desactivar la protección. |
| Resta espectral con protección | Ruido que coincide con tonos protegidos | Parte del ruido se conserva junto con esos tonos; el caso 3 mantiene ruido residual pese a mejorar la SNR. |
| Estimación espectral actual | Señales útiles variables, ruido no estacionario o interferencias estables dentro de la banda útil | La detección de estabilidad y la mediana de captura pueden confundir fuentes o estimar mal el ruido. Es un riesgo del algoritmo que requiere capturas adicionales; no se ha medido aquí. |

El fundamento del límite del FIR es la superposición de los sistemas LTI:
si `x = s + r`, entonces `Y(f) = H(f)S(f) + H(f)R(f)`. Una misma
respuesta en frecuencia actúa sobre ambas fuentes; no distingue su origen
cuando coinciden en frecuencia. Oppenheim y colaboradores desarrollan
superposición y filtrado en las secciones 1.6.6 y 3.8–3.9; Proakis y
Manolakis describen las bandas de paso y rechazo en la sección 5.4.1
[R1–R2]. La estrategia espectral añade supuestos sobre estabilidad y piso
de ruido; su adaptación completa no es un sistema LTI, aunque el operador
condicionado a una máscara fija sea lineal.

La compensación de 18 muestras permite comparar fidelidad del FIR, pero
su retardo físico de 2.25 ms a 8000 Hz sigue existiendo. Las métricas
directas documentan el desfase; no deben sustituir la comparación alineada
para juzgar solamente el filtrado. Por su parte, la cadena espectral
utiliza información de toda la captura para estimar ruido y estabilidad,
por lo que sus resultados actuales no validan un procesamiento causal.

Las mediciones de PC muestran el espectral más rápido y con mayor pico
de memoria trazada que el FIR manual. El FIR usa bucles Python y el
espectral operaciones vectorizadas de NumPy; esos tiempos no establecen
la velocidad relativa en ESP32. El valor de cero bytes persistentes del
espectral describe su función por captura, no un requisito de RAM nulo.
La adaptación y el presupuesto propuestos en el paso 7 deben validarse
con ESP-DSP, seleccionada en el paso 8, y mediciones en la placa.

Solo se evalúa una captura con una semilla por caso, tres tonos conocidos,
un muestreo y un conjunto de parámetros. No se ha comprobado robustez con
voz, música, variaciones de nivel, frecuencias cercanas a los bordes,
otros ruidos o cambios de precisión. Estas son pruebas futuras; el paso 6
no cambia señales, parámetros ni resultados para mejorar las cifras.

## Conclusión comparativa

Para las condiciones medidas, conviene el FIR cuando la interferencia está
claramente separada de la banda útil, y la resta espectral con protección
cuando el ruido está distribuido o se superpone parcialmente con tonos
estables. El caso 3 demuestra el límite de un pasa bajos fijo; el
experimento sin protección demuestra el límite de una reducción espectral
agresiva. La selección debe considerar conjuntamente fidelidad, retardo,
memoria y disponibilidad de una estimación causal del ruido.

## Propuesta para ESP32 — paso 7 completado

El diseño de procesamiento para ESP32 (ruta en el repositorio: `seccion_2_5/docs/2_5_diseno_esp32.md`) desarrolla
la selección, sus cálculos y los criterios de validación pendientes:

| Parámetro | Propuesta |
|---|---|
| Muestreo | 8000 Hz; 125 µs por muestra; Nyquist 4000 Hz |
| Análisis espectral | FFT de 1024 muestras; separación entre bins 7.8125 Hz |
| Avance | 512 muestras nuevas cada 64 ms; solapamiento de 50 % |
| Ventanas | sqrt-Hann en análisis y síntesis, con overlap-add |
| Ruta temporal | FIR de orden 36, 37 coeficientes, estado continuo |
| Procesamiento | float32; formato de ADC, DAC y transmisión por especificar |
| Estimación causal | Mediana sobre las últimas 8 tramas completas y suavizado de 31 bins |
| Objetivo de cálculo | DSP ≤ 48 ms; plazo total por avance < 64 ms |
| Retardo programado espectral | 192 ms en el DSP aislado; refinado a 256 ms con enlaces en el paso 9 |
| Memoria espectral provisional | 81517 bytes ≈ 79.61 KiB, refinada en el paso 8; objetivo de 96 KiB |
| Núcleo FIR especializado | 292 bytes para coeficientes y estado float32 |

La adaptación sustituye el DC de captura completa por un promedio causal
con restauración alineada, conserva un historial de magnitudes acotado y
calcula las máscaras desde el pasado y la trama actual. Durante el
calentamiento se usa G = 1. El historial completo representa 576 ms de
señal y no añade ese valor como retardo por trama. Se conservan inicialmente
los parámetros de picos y resta, pero la calidad del estimador causal no
se considera medida por las pruebas fuera de línea.

El diseño incluye control de escala y saturación, un presupuesto por
arreglo, reservas provisionales para la biblioteca y las tareas, y una
distinción entre bloque DSP y descriptor DMA. Mantener 8000 Hz requiere
además limitar el espectro analógico antes del ADC y comprobar el reloj
real. El ancho numérico del procesamiento no fija la resolución de los
convertidores.

Los cálculos reproducibles están en
el registro del paso 7 (ruta en el repositorio: `revision/paso_7/README.md`). La propuesta
está fundamentada en los resultados y en documentación técnica primaria;
todavía no es firmware ni una medición de desempeño del ESP32.

## Bibliotecas de FFT y filtrado — paso 8 completado

La selección de bibliotecas (ruta en el repositorio: `seccion_2_5/docs/2_5_bibliotecas_esp32.md`) propone
**ESP-DSP 1.8.2, Apache-2.0**, como componente ESP-IDF para FFT y FIR
float32 sobre ESP32 clásico. **KISS FFT 131.1.0, BSD-3-Clause**, queda
como alternativa portable. Se verificaron licencia, precisión, APIs y
restricciones con documentación y código oficiales fijados por versión.

La propuesta FFT incluye datos complejos intercalados, reordenamiento
de bins y una inversa por conjugación con escala 1/1024. El FIR usa
37 coeficientes y delay de 41 floats, conservando el estado entre avances.
Las tablas activas FFT ocupan 6080 bytes de payload, y refinan el total
espectral provisional a 81517 bytes. El núcleo FIR con estructura se
estima en 352 bytes; los 292 bytes del paso 7 corresponden a una
implementación mínima propia.

La versión exacta de ESP-IDF, el sizeof de estructuras, la RAM total,
precisión efectiva y tiempos deben confirmarse al implementar. La revisión
de fuentes no se presenta como compilación o validación en placa.
La evidencia está en el registro del paso 8 (ruta en el repositorio: `revision/paso_8/README.md`).

## Arquitectura y comunicación — paso 9 completado

La propuesta de arquitectura (ruta en el repositorio: `seccion_2_5/docs/2_5_arquitectura_comunicacion.md`) define
tres placas ESP32: N1 adquiere y analiza, N2 filtra mediante FIR y
N3 filtra mediante FFT/IFFT y compara las salidas por índices de muestra.
Cada filtro tiene reproducción local con DAC/PWM y reconstrucción.
Tres UART independientes conectan N1–N2, N1–N3 y N2–N3 a 921600 baud,
8N1, con control de estado en sentido inverso.

Arquitectura propuesta (ruta en el repositorio: `seccion_2_5/docs/figuras/arquitectura_nodos.png`)

Cada avance transmite 512 muestras nuevas float32. El paquete incluye
cabecera de 32 bytes, CRC-32, COBS y delimitador. INPUT/FIR_OUT requieren
hasta 2094 bytes en el cable; INPUT_REF con x y s, hasta 4150 bytes.
El enlace más cargado, N1→N3 con referencia y diagnóstico, requiere
664375 baud; con control acotado, 671375 baud, 72.85 % de ocupación
a la tasa propuesta. Las tasas no se suman entre enlaces independientes.

La referencia limpia solo está disponible en ensayos controlados; sin
ella se muestran N/D para MSE, SNR de referencia y energía útil.
El modo de evaluación condicional calcula la contribución útil con
ganancias congeladas y añade memoria y trabajo. La arquitectura completa
refina la reproducción a 256 ms y propone reservas por dispositivo
de 96 KiB para N1, 64 KiB para N2 y 160 KiB para N3, cuyos consumos
modelados son 71.16, 45.56 y 134.16 KiB, respectivamente.

Se especifican sesión, secuencia e índice, tratamiento de errores,
discontinuidades y deriva de reloj. Una trama oficial de ejemplo,
cálculos reproducibles y revisión visual del diagrama están en
el registro del paso 9 (ruta en el repositorio: `revision/paso_9/README.md`).
El diseño aún requiere validar enlaces, precisión, RAM y plazos en placa.

## Referencias del análisis

- **[R1]** Oppenheim, Willsky y Nawab, *Señales y sistemas*, segunda
  edición, secciones 1.6.6, 3.8 y 3.9. Se consultó el
  libro proporcionado (ruta en el repositorio: `Contexto/alan-v-oppenheim-seales-y-sistemas-pdf-free.pdf`),
  páginas 76 y 251–254 del archivo PDF.
- **[R2]** Proakis y Manolakis, *Digital Signal Processing*, cuarta
  edición, sección 5.4.1, página impresa 327, página 347 del
  archivo PDF proporcionado (ruta en el repositorio: `Contexto/Digital%20Signal%20Processing%204th%20edition%20-%20Proakis%20and%20Manolakis-compressed.pdf`).

La evidencia numérica procede del evaluador común de 2.5 y, donde se
indica expresamente, del experimento adicional de 2.4. Se empleó asistencia
de IA para redactar el análisis y derivar los diagnósticos; las cifras se
contrastaron con archivos guardados y las afirmaciones teóricas con las
fuentes locales. Las referencias bibliográficas finales, la declaración
de asistencia y la integración con las demás secciones se completarán
durante el paso 10.
