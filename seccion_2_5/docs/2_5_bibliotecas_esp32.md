# Paso 8: bibliotecas para FFT y filtrado en ESP32

**Decisión:** proponer **ESP-DSP 1.8.2** como componente de ESP-IDF para
FFT e implementación FIR en float32 sobre el ESP32 clásico. KISS FFT
queda como alternativa portable. La consulta de fuentes se realizó el
12 de octubre de 2026; no se instaló ni compiló firmware.

## Opciones verificadas

| Biblioteca y versión consultada | Licencia | Precisión y funciones pertinentes | Limitaciones para esta propuesta |
|---|---|---|---|
| ESP-DSP 1.8.2 | Apache-2.0 | FFT compleja float32 y variante int16; FIR float32 y filtrado entero; también biquads IIR | Componente ESP-IDF, tablas y estado propios; las optimizaciones dependen del chip. Requiere comprobar orden, escala y errores de cada API. |
| KISS FFT 131.1.0 | BSD-3-Clause | FFT directa/inversa; float por defecto, double, Q15 o Q31 según compilación; FFT real para longitud par | C portable; integración en ESP-IDF a cargo del grupo. No se ha medido en la placa. No sustituye la ruta FIR de 37 coeficientes ya diseñada. |

ESP-DSP ofrece rutinas optimizadas y referencias ANSI C, y el registro
oficial identifica la versión 1.8.2 y licencia Apache-2.0
([registro del componente](https://components.espressif.com/components/espressif/esp-dsp/versions/1.8.2/readme),
[licencia](https://github.com/espressif/esp-dsp/blob/v1.8.2/LICENSE)).
Los filtros IIR disponibles no motivan sustituir el FIR seleccionado:
la comparación experimental se realizó con ese FIR.

KISS FFT documenta float por defecto, opciones de punto fijo y double,
y transformadas sin normalización en coma flotante. Su ejecución básica
usa buffers distintos; si se utiliza el mismo buffer crea uno temporal.
Esto cambiaría el presupuesto in-place del paso 7. La opción real requiere
longitud par, condición que cumple N = 1024. Se descarta como primera
opción por la integración y validación adicional que requeriría, sin
afirmar que sea más lenta en esta placa
([README 131.1.0](https://github.com/mborgerding/kissfft/blob/131.1.0/README.md),
[licencia de esa versión](https://github.com/mborgerding/kissfft/blob/131.1.0/COPYING)).

## Versión y configuración seleccionadas

La revisión usa el tag v1.8.2 de ESP-DSP, asociado al commit
`a53a0756833c045311ea1d79a2badf495cdfde4c`. Su manifiesto declara ESP-IDF
`>=4.2`; es un requisito de dependencia, no una comprobación de todas
las combinaciones de compilador e IDF
([manifiesto](https://github.com/espressif/esp-dsp/blob/v1.8.2/idf_component.yml)).
La versión exacta de ESP-IDF y la placa se registrarán al implementar.

Se propone fijar la dependencia a `espressif/esp-dsp: "1.8.2"` en
el manifiesto del futuro firmware y conservar `dependencies.lock`,
siguiendo el contrato de versión específica del
[Component Manager](https://docs.espressif.com/projects/idf-component-manager/en/latest/reference/manifest_file.html).
Configurar target `esp32`, optimizaciones DSP activadas y tamaño máximo
FFT de 1024. La selección Kconfig es `CONFIG_DSP_MAX_FFT_SIZE_1024=y`,
que produce `CONFIG_DSP_MAX_FFT_SIZE=1024`; además se selecciona
`CONFIG_DSP_OPTIMIZED=y`. Evitar depender del máximo predeterminado
de 4096 si solo se utiliza N = 1024
([Kconfig de la versión](https://github.com/espressif/esp-dsp/blob/v1.8.2/Kconfig)).

No se añade todavía un manifiesto activo porque el repositorio contiene
la referencia de la tarea y la propuesta, sin un proyecto ESP-IDF
configurado. Al integrar el componente se conservarán su licencia y
avisos correspondientes; las funciones propias y las fuentes usadas
se identificarán en el informe.

## Uso de FFT e IFFT

La ruta seleccionada utiliza una FFT compleja de 1024 puntos aunque la
entrada sea real, para mantener un contrato sencillo y el buffer previsto.
Se carga `Re[n] = v[n]w[n]`, `Im[n] = 0` en 2048 floats intercalados.
La API opera sobre ese buffer in-place; la variante `_ae32` corresponde
al ESP32 y la ANSI sirve como referencia portable
([cabecera FFT](https://github.com/espressif/esp-dsp/blob/v1.8.2/modules/fft/include/dsps_fft2r.h)).

Inicializar una vez con `dsps_fft2r_init_fc32(tabla, 1024)`. Por trama,
llamar `dsps_fft2r_fc32(buffer, 1024)` y después
`dsps_bit_rev2r_fc32(buffer, 1024)` para ordenar los bins antes de
calcular magnitudes y aplicar ganancias. Comprobar cada código de retorno.
La FFT directa no aplica 1/N en las mariposas; su inicialización maneja
tablas globales. Se inicializa antes de lanzar tareas y no se reinicializa
ni libera mientras otra tarea las usa
([implementación FFT](https://github.com/espressif/esp-dsp/blob/v1.8.2/modules/fft/float/dsps_fft2r_fc32_ansi.c)).

Para sintetizar se propone construir la inversa mediante
`IFFT(Y) = conj(FFT(conj(Y)))/N`: conjugación, FFT directa,
reordenamiento y conjugación final con escala 1/1024. Esta es una
adaptación matemática propia; no se atribuye una función IFFT con nombre
inventado a ESP-DSP. Se verificará identidad y signo de la fase en placa.
Al aplicar G se refleja `G[N−k] = G[k]` para k = 1…511; DC y Nyquist
se tratan una sola vez. No se usa el conversor de dos señales reales
como si fuera un equivalente directo de `numpy.fft.rfft`.

ESP-DSP aporta primitivas DSP. El estimador de ruido, protección de
tonos, política de calentamiento, historial DC y overlap-add del paso 7
siguen siendo responsabilidad de la implementación del grupo.

## FIR de 37 coeficientes

Se propone `dsps_fir_init_f32` con los coeficientes, un delay preasignado
y longitud 37; después `dsps_fir_f32` sobre cada lote de 512 muestras,
con la misma estructura de estado. No se reinicializa entre lotes.
La API exige delay de longitud `coeffs_len + 4`, es decir **41 floats**
([cabecera FIR](https://github.com/espressif/esp-dsp/blob/v1.8.2/modules/fir/include/dsps_fir.h)).

La inicialización revisada solo impone longitud múltiplo de cuatro y
alineación de 16 bytes bajo target ESP32-S3; el diseño de 37 coeficientes
se mantiene para **ESP32 clásico**. No se debe trasladar esa configuración
al S3 sin adaptar y validar el contrato. Se propone alinear los buffers
a 16 bytes por uniformidad y preasignar delay, evitando asignación interna
([inicialización FIR](https://github.com/espressif/esp-dsp/blob/v1.8.2/modules/fir/float/dsps_fir_init_f32.c)).

La referencia ANSI recorre el delay desde la muestra más antigua hacia
la reciente mientras avanza los coeficientes; para la convención
`sum b[k]x[n−k]` se cargan los b en orden invertido. El FIR actual es
simétrico, de modo que invertirlos no altera la secuencia; esa simetría
podría ocultar un error de orden en un filtro futuro. Una prueba de
impulso con coeficientes no simétricos verificará el adaptador
([FIR ANSI](https://github.com/espressif/esp-dsp/blob/v1.8.2/modules/fir/float/dsps_fir_f32_ansi.c),
[FIR ESP32](https://github.com/espressif/esp-dsp/blob/v1.8.2/modules/fir/float/dsps_fir_f32_ae32.S)).

La ecuación manual de 2.3 continúa como referencia independiente.
Cambiar a una rutina optimizada puede cambiar redondeos por acumulación;
se verificará contra float64 con las tolerancias propuestas, sin suponer
igualdad bit a bit.

## Memoria refinada para ESP-DSP

La inicialización de FFT reserva 1024 floats de twiddles: **4096 bytes**.
También copia a RAM 496 pares de índices uint16 para bit reversal:
`2 × 496 × 2 = 1984 bytes`. El payload de tablas activas es **6080 bytes**;
se mantiene aparte el buffer de datos de **8192 bytes**. La cantidad
de pares se contrastó con los 992 índices de la tabla de esa versión
([tabla oficial](https://github.com/espressif/esp-dsp/blob/v1.8.2/modules/fft/float/dsps_fft2r_bitrev_tables_fc32.c)).

Esta cuenta incluye la copia interna incluso si la tabla de twiddles la
aporta el usuario. No cuenta dos veces la tabla estática en flash como
RAM activa. Metadatos y costes del allocator siguen cubiertos de forma
provisional por las reservas; el mapa de enlace determinará su ubicación.

| Cuenta | Paso 7: reserva genérica | Paso 8: ESP-DSP 1.8.2 |
|---|---:|---:|
| Tablas/workspace FFT, fuera del buffer de datos | 8192 B | 6080 B de payload |
| Subtotal espectral de aplicación | 67245 B | 65133 B |
| Con provisión auxiliar de 16384 B | 83629 B | **81517 B ≈ 79.61 KiB** |
| Margen dentro del objetivo de 96 KiB | 14675 B | **16787 B** |
| Núcleo FIR | 292 B, implementación mínima | **352 B estimados con la biblioteca** |

El núcleo FIR pasa a 148 bytes de coeficientes, 164 de delay y
aproximadamente 40 de `fir_f32_t` bajo ABI de 32 bits. La estructura
deberá confirmarse con `sizeof` en el compilador destino. Con buffers
de aplicación y control, la ruta FIR se estima en **9568 bytes**.
Estas cifras refinan la propuesta; no equivalen a RAM total medida ni
validan que los plazos de 64 ms se cumplan.

Los resultados del paso 7 se conservan como presupuesto inicial. El
[registro del paso 8](../../revision/paso_8/README.md) contiene las
derivaciones, fuentes fijadas por versión y hashes de los archivos leídos.
La [arquitectura del paso 9](2_5_arquitectura_comunicacion.md) añade
comunicación y evaluación controlada: el nodo N3 completo se presupuesta
en 134.16 KiB, con objetivo de reserva de 160 KiB. Esa cuenta incluye
recursos que no forman parte del DSP aislado aquí descrito.

## Comprobaciones al implementar

Validar FFT/IFFT e identidad con G = 1, escala y orden de bins mediante
impulso, DC, Nyquist y tonos entre bins. Contrastar FIR con la ecuación
manual, verificando orden de coeficientes y continuidad entre lotes.
Comparar ANSI y optimizada con tolerancia, y medir la cadena completa
con ventanas, medianas y E/S. Los benchmarks del proveedor de una FFT
aislada no sustituyen esa medición ni se suman a los tiempos de Python.

La investigación y los cálculos del paso 8 quedan completos. Las
pruebas de firmware, la compatibilidad efectiva con la versión de IDF
seleccionada y las mediciones de RAM/plazos permanecen como validación
de la implementación del proyecto. Se empleó asistencia de IA para
la revisión y redacción, contrastando las decisiones con fuentes primarias.
