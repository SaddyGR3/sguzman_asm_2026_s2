# Paso 7: propuesta de procesamiento para ESP32

**Estado:** propuesta de diseño calculada; no se ha implementado ni medido
en la placa. La [selección de bibliotecas del paso 8](2_5_bibliotecas_esp32.md)
propone ESP-DSP 1.8.2 y refina este presupuesto inicial. La
[arquitectura del paso 9](2_5_arquitectura_comunicacion.md) incluye enlaces
y evaluación, y refina la reproducción a 256 ms y la reserva del nodo
comparador completo a 160 KiB.

## Decisión y fundamento

Se propone mantener **fs = 8000 Hz**, **FFT de N = 1024 muestras**,
**avance H = 512 muestras**, **solapamiento de 50 %** y **float32 para
procesamiento**. La ruta temporal conserva el FIR Kaiser de orden 36,
con 37 coeficientes y estado continuo. La ruta espectral conserva
sqrt-Hann en análisis y síntesis y modifica ganancias reales por bin.

Estos valores preservan el muestreo, diseño FIR y rejilla espectral de
los experimentos. El FIR obtuvo la mejor calidad en el caso tonal
separado; la resta espectral con protección la obtuvo en los casos blanco
y superpuesto, según el [análisis del paso 6](2_5_comparacion_propuesta.md).
Se mantienen ambas rutas para compararlas. La elección del método no
requiere conocer la referencia limpia; el modo puede configurarse para
cada ensayo, y una selección automática requeriría validación adicional.

La documentación existente de 2.3 identifica ESP32 como hardware y
justifica float32 mediante cuantización de coeficientes. Para esta
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
separadamente: procesar en float32 no implica adquirir 32 bits de precisión
ni obliga a transmitir floats. La conversión se realiza con escala y
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
no se trasladan las cifras del paso 6 como resultados del firmware causal.

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

En la ruta espectral, las primeras 512 muestras reales solo quedan
completas cuando se dispone del segundo bloque solapado, a los 128 ms
desde el inicio. Para reproducción uniforme se propone un retardo
programado de **N + H = 1536 muestras, 192 ms**, que deja un avance
adicional para completar el cálculo antes de reproducir el bloque.
Cumplir 48 ms de DSP dejaría 16 ms de esa holgura. La transferencia entre
nodos y otras colas pueden aumentar el retardo y se presupuestarán en el
paso 9. Los 128 ms de ventana y 64 ms de avance no son por sí solos
mediciones de latencia extremo a extremo.

El FIR mantiene su retardo de grupo de 18 muestras, **2.25 ms**, además
del tiempo de acumular lotes, procesamiento, enlace y cola de reproducción.
Para comparar salidas se usan índices de muestra y compensación de
retardos conocidos. Mantener el FIR retrasado para una comparación común
es una decisión de sincronización, no una propiedad adicional del filtro.

## Presupuesto de memoria

**Presupuesto inicial del paso 7.** Con ESP-DSP 1.8.2, el paso 8 refina
el total espectral a **81517 bytes (79.61 KiB)** y el núcleo FIR de
biblioteca a **352 bytes estimados**. Las cuentas siguientes se conservan
como referencia de diseño previa a elegir la biblioteca; consultar
[el presupuesto refinado](2_5_bibliotecas_esp32.md#memoria-refinada-para-esp-dsp).

Se reservan arreglos una vez, sin matrices de todas las capturas ni
asignaciones por trama. Se contempla una FFT compleja in-place para
presupuestar sin depender aún de una API rFFT específica. Las magnitudes
y máscaras solo almacenan los 513 bins no negativos.

| Componente de la ruta espectral | Bytes |
|---|---:|
| Historial centrado, N float32 | 4096 |
| Historial DC alineado, N float32 | 4096 |
| Trabajo FFT/IFFT, N pares float32 reutilizados | 8192 |
| Ventana sqrt-Hann, N float32 | 4096 |
| Acumulación overlap-add, N float32 | 4096 |
| Magnitudes actuales, 513 float32 | 2052 |
| Historial de magnitudes, 8 × 513 float32 | 16416 |
| Perfil mediano, piso y ganancias, 3 × 513 float32 | 6156 |
| Máscara protegida, 513 uint8 | 513 |
| Scratch de mediana, 31 float32 | 124 |
| Reserva provisional de tablas/workspace FFT | 8192 |
| Dos buffers de entrada y dos de salida, H float32 cada uno | 8192 |
| Reserva de control, contadores y alineación | 1024 |
| **Subtotal DSP y buffers de aplicación** | **67245** |
| Provisión adicional para DMA, pilas y colas | 16384 |
| **Total provisional** | **83629 ≈ 81.67 KiB** |

Se propone un objetivo de **96 KiB por ruta espectral**, con 14675 bytes
de margen respecto de esta provisión. La reserva FFT es una asignación
de diseño, refinada con las tablas de la biblioteca en el paso 8.
Los 16 KiB auxiliares tampoco son un consumo medido ni abarcan
todo el firmware: pueden cambiar con drivers, pantalla, comunicación y
pilas. La factibilidad final se comprobará con mapa de enlace, heap libre,
máximo de pila y requisitos de los buffers; no solo contra los 520 KB
nominales del chip.

Para el FIR especializado, 37 coeficientes más 36 muestras de estado
ocupan **292 bytes float32** o **146 bytes Q15**. Con los cuatro buffers
de H muestras float32 y una provisión de control de 1024 bytes, su
subtotal de aplicación es **9508 bytes**, antes de drivers y pilas.
No se duplica el coeficiente a[0] = 1 de una implementación FIR
especializada. No debe confundirse esta cuenta con los 592 bytes de
estado genérico float64 medidos en el evaluador de PC.

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

Los cálculos están registrados en
[presupuesto_esp32.json](../../revision/paso_7/presupuesto_esp32.json) y se
regeneran con
[calcular_presupuesto.py](../../revision/paso_7/calcular_presupuesto.py).
Las fuentes técnicas se consultaron el 12 de octubre de 2026. La propuesta
se redactó con asistencia de IA; sus cálculos se verificaron separadamente
de las mediciones existentes.
