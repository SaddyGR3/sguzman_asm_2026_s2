# Procesamiento propuesto para ESP32

La propuesta usa ESP32 clásico con procesamiento en float32. Aún no se ha implementado ni medido en placa. Las [bibliotecas](2_5_bibliotecas_esp32.md) y la [arquitectura](2_5_arquitectura_comunicacion.md) completan el diseño: reproducción a 256 ms y reserva de 160 KiB para el nodo comparador.

## Decisión y fundamento

Se propone mantener **fs = 8000 Hz**, **FFT de N = 1024 muestras**,
**avance H = 512 muestras**, **solapamiento de 50 %** y **float32 para
procesamiento**. La ruta temporal conserva el FIR Kaiser de orden 36,
con 37 coeficientes y estado continuo. La ruta espectral conserva
sqrt-Hann en análisis y síntesis y modifica ganancias reales por bin.

Estos valores preservan el muestreo, diseño FIR y rejilla espectral de
los experimentos. El FIR obtuvo la mejor calidad en el caso tonal
separado; la resta espectral con protección la obtuvo en los casos blanco
y superpuesto, según el [análisis comparativo](2_5_comparacion_propuesta.md).
Se mantienen ambas rutas para compararlas. La elección del método no
requiere conocer la referencia limpia; el modo puede configurarse para
cada ensayo, y una selección automática requeriría validación adicional.

La evaluación de cuantización de coeficientes respalda float32. Para esta
propuesta se toma como base el **ESP32 clásico con LX6**; el modelo exacto
de placa debe registrarse al implementar. Espressif declara 520 KB de
SRAM en el chip, compartidos por datos e instrucciones; esa cifra no es
RAM libre de aplicación ([ficha del ESP32](https://documentation.espressif.com/esp32_datasheet_en.html)).
No se presupone PSRAM.

## Muestreo y tamaños de bloque

A 8000 Hz, el período de muestra es 125 µs y Nyquist es 4000 Hz.
Los tonos útiles hasta 1100 Hz y la interferencia de 2150 Hz quedan por
debajo de ese límite. Esto justifica conservar fs para las señales
estudiadas, pero no demuestra ausencia de aliasing en una adquisición
analógica. Se debe limitar el espectro antes del ADC: conservar el rango
útil y la interferencia de prueba, y atenuar suficientemente por encima
de 4000 Hz según el máximo nivel de entrada. El filtro analógico y el
reloj real se verificarán al construir el banco. Un FIR posterior al ADC
no corrige aliasing ya producido.

| N de FFT | Separación entre bins fs/N | Duración N/fs | Avance con 50 % de solapamiento |
|---:|---:|---:|---:|
| 256 | 31.250 Hz | 32 ms | 16 ms |
| 512 | 15.625 Hz | 64 ms | 32 ms |
| **1024** | **7.8125 Hz** | **128 ms** | **64 ms** |

N = 1024 mantiene la rejilla ya evaluada y permite describir picos y
bandas con mayor detalle que las alternativas de la tabla. La separación
entre bins no equivale a resolver automáticamente dos tonos cercanos:
también interviene la ventana. No se atribuyen mejoras medidas a N = 256
o 512; la tabla compara únicamente sus magnitudes calculadas.

**N es la longitud de análisis; H es la cantidad de muestras nuevas.**
Se acumulan 512 muestras nuevas cada 64 ms y se reutilizan las 512
anteriores. El FIR puede procesar esos mismos lotes de 512 conservando
sus 36 muestras de estado. Esto cambia la unidad de ejecución respecto
de los bloques temporales de 1024 de la comparación en PC; no cambia su
ecuación matemática. Las métricas y el benchmark guardados permanecen
referidos a su configuración original.

## Formato numérico y escala

Se propone `float32` para muestras internas, coeficientes, magnitudes,
ganancias y acumulación, y pares de float32 para valores complejos.
La referencia de PC permanece en float64. En 2.3, convertir los
coeficientes a float32 produjo un error máximo de 1.088 × 10⁻⁸ y mantuvo
la atenuación mínima de rechazo cerca de 46.107 dB. Esa prueba verifica
coeficientes y respuesta, no la totalidad de una ejecución DSP en float32.
La FFT y el estimador causal deben verificarse por separado.

ESP-IDF documenta que `double` carece de aceleración de hardware en estos
targets con FPU y se ejecuta por software. Se propone ejecutar el DSP
en una tarea con afinidad definida y limitar las interrupciones a notificar
la disponibilidad de datos; por defecto, FreeRTOS de ESP-IDF no admite
uso de FPU en interrupciones ([documentación de FreeRTOS](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/system/freertos_idf.html#floating-point-usage)).

El ancho del ADC o DAC y el formato de transmisión se especificarán
separadamente: procesar en float32 no implica adquirir 32 bits de precisión.
La propuesta de comunicación transmite float32, sin atribuir al ADC esa precisión. La conversión se realiza con escala y
offset documentados. Los buffers complejos no se limitan artificialmente
a ±1: una FFT sin normalizar puede superar el rango de las muestras.
La normalización de la IFFT debe comprobarse con la biblioteca elegida.

La cota del FIR es `|y| ≤ sum(|b|) max(|x|)`, con `sum(|b|) ≈ 1.702778`.
Para una salida normalizada en ±1 se puede reservar un factor conservador
de 0.587276 o fijar una ganancia de reproducción común para ambas rutas.
Esa ganancia se documenta aparte de las métricas del algoritmo. El
espectral no hereda la cota del FIR; se controla su pico por separado.
Antes de convertir a DAC/PWM se limita el rango y se cuentan saturaciones.

Q15 queda como alternativa: requiere cuantización, escala FFT por etapas,
normalización y acumuladores suficientemente anchos. Los 146 bytes de
coeficientes/estado FIR y el acumulador int32 comprobado para esos
coeficientes no validan una FFT ni un estimador completo en Q15.

## Adaptación causal de la ruta espectral

El algoritmo actual resta el DC medio de toda la captura, estima el piso
mediante mediana temporal y determina estabilidad con todos los bloques.
Para streaming se propone la siguiente sustitución, usando solo datos
actuales y anteriores:

1. Centrar cada muestra mediante un promedio causal lento:
   `d[n] = d[n−1] + β (x[n]−d[n−1])`,
   `v[n] = x[n]−d[n]`, con τ = 1 s y
   `β = 1−exp(−1/(fs τ)) ≈ 0.000124992`. Inicializar d con la primera
   muestra. Guardar d con su índice para restaurarlo en la salida
   correspondiente, después del retardo; no añadir el DC del instante de
   reproducción a muestras antiguas.
2. Formar una ventana de 1024 muestras de v cada 512 nuevas. Aplicar
   sqrt-Hann, FFT y obtener 513 magnitudes no negativas. Si se utiliza FFT
   compleja completa, mantener la simetría conjugada al modificar bins.
3. Guardar las últimas **W = 8 tramas completas**, incluida la actual.
   Por bin, calcular la mediana de esas ocho magnitudes; suavizar el
   perfil con la mediana de 31 bins y reflexión en DC/Nyquist. Es una
   mediana de pasado reciente, no de la captura completa.
4. Detectar tonos dentro de 0–1200 Hz con el perfil, máximos locales,
   umbral 2.5 veces el piso y variabilidad `std/mean < 0.55` sobre ese
   historial; proteger el centro y un bin por lado. Para el modo picos,
   usar umbral 6, rechazo de ±6 bins y ganancia mínima 0.001 fuera de la
   banda protegida. Son parámetros iniciales heredados, pendientes de
   validar con la nueva estimación.
5. En modo resta, usar
   `G = clip(1−3 piso/max(|X|, ε), 0.05, 1)` y G = 1 en bins
   protegidos. Adoptar ε = 10⁻¹² con muestras normalizadas y FFT sin
   normalizar. El modo picos construye su máscara desde la trama actual
   y el piso reciente. No se codifica la frecuencia de interferencia.
6. Aplicar ganancias, IFFT, normalización, ventana de síntesis y
   overlap-add. Emitir únicamente las 512 muestras cuyas contribuciones
   de ventanas ya estén completas; conservar la mitad pendiente.
   Restaurar su historial de DC y convertir para reproducción.

El historial cubre `(N + (W−1)H)/fs = 576 ms` de señal cuando está lleno.
Ese valor describe memoria temporal del estimador, no un retardo añadido
de 576 ms: no se espera información futura para cada trama. La mediana
se actualiza cada 64 ms y puede tardar en adaptarse a un cambio de ruido.
W = 8 es una elección inicial para limitar RAM; su calidad no está medida.

Al iniciar, anteponer H ceros a v para completar el solapamiento inicial,
usar G = 1 hasta reunir ocho tramas completas sin relleno y marcar ese
intervalo como calentamiento. El historial estará disponible aproximadamente
a los 576 ms más el tiempo de procesamiento. La reproducción ya puede
funcionar antes en paso directo. Al detener, procesar el relleno necesario
para completar la última contribución, sin incorporar ceros al estimador.
Tras una pérdida de datos se marca la discontinuidad y se reinician los
estados afectados; no se presenta el tramo como una captura continua válida.

La identidad con G = 1 se comprobará usando
`w[n]² + w[n+H]² = 1` en régimen y el tratamiento de extremos indicado.
El promedio DC y su restauración alineada también deben conservar esa
identidad. El nuevo estimador puede cambiar SNR, MSE y detección de tonos;
las cifras del filtro fuera de línea no se presentan como resultados del firmware causal.

## Plazo de ejecución y latencia

Se procesa a 15.625 tramas por segundo. Cada trama espectral debe terminar
antes de la siguiente llegada: **T total por avance < 64 ms**, incluyendo
procesamiento y las tareas que compitan por el recurso. Se fija como
objetivo inicial **T DSP ≤ 48 ms**, reservando 16 ms para E/S y planificación.
Es un objetivo a medir, no un tiempo alcanzado.

Con FFT e IFFT complejas radix-2 se cuentan 5120 mariposas por transformada,
10240 por avance, más ventanas, magnitudes, medianas y ganancias.
El FIR directo requiere 37 × 512 = 18944 MAC por avance, o 296000 MAC/s.
Estos conteos no permiten deducir tiempos comparables entre métodos.

La ventana dura 128 ms y avanza cada 64 ms. Al incluir adquisición, procesamiento y enlaces se propone reproducir con **256 ms de retardo**. El modelo sitúa la disponibilidad espectral en 223.90 ms y la FIR alineada en 226.07 ms, bajo el objetivo de 48 ms de DSP, envío simultáneo desde N1 y encolado de hasta 1 ms por enlace. Son estimaciones; véase el [presupuesto de comunicación](2_5_arquitectura_comunicacion.md).

El FIR mantiene su retardo de grupo de 18 muestras, **2.25 ms**, además
del tiempo de acumular lotes, procesamiento, enlace y cola de reproducción.
Para comparar salidas se usan índices de muestra y compensación de
retardos conocidos. Mantener el FIR retrasado para una comparación común
es una decisión de sincronización, no una propiedad adicional del filtro.

## Presupuesto de memoria

Se reservan arreglos una vez y se procesa por lotes, sin cargar capturas completas en RAM. La FFT compleja reutiliza su buffer y guarda magnitudes/ganancias de los 513 bins no negativos.

| Componente de la ruta espectral | Bytes |
|---|---:|
| Historial centrado, N float32 | 4096 |
| Historial DC alineado, N float32 | 4096 |
| Buffer FFT/IFFT, N pares float32 | 8192 |
| Ventana raíz de Hann | 4096 |
| Acumulación por solapamiento | 4096 |
| Magnitudes actuales, 513 float32 | 2052 |
| Historial, 8 × 513 float32 | 16416 |
| Perfil, piso y ganancias, 3 × 513 float32 | 6156 |
| Máscara de protección, 513 uint8 | 513 |
| Trabajo de mediana, 31 float32 | 124 |
| Tablas ESP-DSP | 6080 |
| Dos buffers de entrada y dos de salida | 8192 |
| Control y alineación | 1024 |
| **Subtotal DSP** | **65133** |
| Reserva auxiliar de la ruta aislada | 16384 |
| **Ruta aislada con auxiliares** | **81517 ≈ 79.61 KiB** |

El FIR mínimo necesita 37 coeficientes y 36 estados: 292 B en float32 o 146 B en Q15. Con ESP-DSP se estiman 352 B por su estado y estructura de control. Con buffers de aplicación y control, la ruta FIR ocupa 9568 B, antes de los auxiliares completos del nodo.

La memoria completa de N1, N2 y N3 se estima en **72868, 46652 y 137377 B**, con reservas objetivo de 96, 64 y 160 KiB, respectivamente. Esas cuentas incluyen comunicación y evaluación y se detallan en la [arquitectura](2_5_arquitectura_comunicacion.md). No se suman a la ruta aislada como categorías adicionales.

El lote lógico H no obliga a que un descriptor DMA contenga H muestras.
Por ejemplo, I2S con dos slots de 32 bits requeriría 4096 bytes para
512 frames, por encima del máximo de 4092 documentado. Se propone,
si se usa ese modo, agrupar **dos descriptores de 256 frames** para
completar un avance; cada uno ocupa 2048 bytes. El número de descriptores
y buffers de lectura se fijará según el intervalo real de servicio
([notas de I2S](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/i2s.html#how-to-prevent-data-lost)).
Esto es un ejemplo de provisión de periférico; no presupone que el
ADC/DAC concreto use esa interfaz ni define la comunicación entre nodos.

## Validación necesaria al implementar

Antes de afirmar funcionamiento en tiempo real se debe comprobar:

- FFT/IFFT en float32 contra la referencia, escala, DC, Nyquist y
  reconstrucción con G = 1; error de identidad objetivo ≤ 10⁻⁵ en
  muestras normalizadas, sujeto a la biblioteca elegida.
- FIR float32 y estado continuo entre lotes contra float64, incluyendo
  transitorios y ausencia de saturación; error máximo objetivo ≤ 10⁻⁵.
- Causalidad: cambiar muestras futuras no debe modificar salidas ya
  emitidas ni las máscaras calculadas anteriormente.
- Calidad en los tres casos con referencias e índices alineados,
  mostrando captura completa y régimen posterior al calentamiento por
  separado. Como meta inicial, la SNR causal no debería perder más de
  1 dB frente a la referencia fuera de línea en un intervalo idéntico;
  si la pierde, se ajusta el estimador y se reporta la diferencia.
- Mediana, P95 y máximo de tiempo por avance en la placa con E/S activa,
  verificación del plazo de 64 ms, contadores de pérdidas y saturación,
  RAM real y latencia extremo a extremo.

Las tolerancias anteriores son criterios propuestos, no verificaciones
ya superadas. Las métricas con referencia limpia requieren un ensayo
controlado; no son observables directamente a partir de una entrada
contaminada arbitraria.

Las tablas anteriores son estimaciones de diseño. Las ecuaciones y asignaciones permiten contrastarlas con el mapa de memoria y las reservas efectivas del firmware.

Las fuentes técnicas se consultaron el 12 de octubre de 2026. La propuesta
se redactó con asistencia de IA; sus cálculos se verificaron separadamente
de las mediciones existentes.
