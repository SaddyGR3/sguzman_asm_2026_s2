# Nodos 2 y 3: receptor UART, grabación, filtros y salida DAC

Recibe continuamente INPUT y DIAG del micrófono del nodo 1 por UART1 a
921600 baudios, 8N1, con 16 KiB de búfer y lecturas sin espera de hasta 1024 B.
Valida COBS, CRC-32/ISO-HDLC y cabecera; al arrancar descarta hasta el primer
`0x00` e ignora las tramas vacías. Cada INPUT contiene 512 muestras float32
a 8 kHz (64 ms). El monitor USB usa UART0 a 115200 baudios.

## Grabar y reproducir

Se graba por actividad y se escucha únicamente al pedir reproducción, para
**evitar realimentación acústica entre micrófono y parlante**. El filtrado sigue
siendo en tiempo real, bloque a bloque, durante la reproducción.

| Estado | Comportamiento |
| --- | --- |
| ESPERANDO | DAC en silencio (128). Mantiene un pre-disparo circular de 4096 muestras (0.512 s), calcula la RMS por INPUT y aprende el ruido de fondo. |
| GRABANDO | Guarda audio hasta 16 bloques seguidos bajo el umbral (1.024 s), o hasta llenar la memoria. El DAC permanece en silencio. |
| LISTA | Conserva la grabación y espera el botón o comando. Mantiene pre-disparo y detección; una actividad nueva reemplaza la grabación anterior. |
| REPRODUCIENDO | Decodifica bloques de 512, actualiza FIR, notch y la ruta espectral y entrega el modo seleccionado al DAC. Sigue leyendo y validando INPUT y DIAG, sin grabar ni disparar. Al drenar el audio y establecer silencio vuelve a LISTA. |

El disparo requiere dos bloques consecutivos con RMS mayor que
`umbral × max(ruido de fondo, 0.00001)`. El factor inicial es **3.0**
(aproximadamente 9.5 dB). Al empezar a recibir o detectar una sesión nueva,
se ignoran los primeros 16 INPUT y se toma la mediana de la RMS de los 16
siguientes: el promedio de los dos valores centrales ordenados. Durante esos
32 bloques (2.048 s) no hay disparos. Al completar se imprime
`Grabación: fondo calibrado <valor>`.

**La calibración se hace en silencio**, tanto al arrancar como al usar
`calibrar`. Este comando cancela la grabación en curso, descarta el audio
anterior y limpia pre-disparo y confirmaciones antes de repetir la medición.
Durante REPRODUCIENDO imprime `Grabación: calibrar no disponible mientras reproduce`
y no cambia nada. Si llega una sesión nueva mientras se reproduce, la
calibración automática se difiere hasta terminar el audio para no medir el parlante.

Después de calibrar, el fondo se actualiza con un promedio exponencial de
factor 0.01, solo en ESPERANDO y con bloques cuya RMS sea **menor que 1.5 veces
el fondo**. Los demás no lo modifican, aunque aún no alcancen el umbral de
disparo. En LISTA se conserva el fondo aprendido. Los dos bloques de
confirmación quedan incluidos una sola vez en el pre-disparo copiado.

La grabación usa **G.711 μ-law de 8 bits**, 8000 bytes/s. Se recortan las
muestras a [-1, 1] y las no finitas se guardan como cero. La reproducción
decodifica a float antes de filtrar; la salida física ya es un DAC de 8 bits.
El pre-disparo es estático y la grabación se reserva una sola vez al arrancar
con `heap_caps_malloc`, después de iniciar ESP-DSP, los controladores y la tarea DAC.
Se imprimen RAM interna libre, bloque libre más grande y duración obtenida.
La reserva considera ambos límites, deja al menos **48 KiB** libres y se reduce
en bloques completos si el asignador no puede satisfacerla.

El máximo es **188 bloques = 96 256 B = 12.032 s**, incluido el pre-disparo
copiado; este además ocupa 4096 B separados. La capacidad real puede ser menor
según la RAM disponible. Si no caben al menos ocho bloques conservando el
margen, se informa que la grabación está deshabilitada y el DAC queda en silencio.
La grabación se pierde al reiniciar. Para P1–P5 de 10 s se esperan unos
10–11 s más el pre-disparo, dependiendo del silencio inicial y final.

Conectar un botón entre **GPIO33 (P33) y GND**, con pull-up interno. El flanco
de 1 a 0 solo inicia reproducción en LISTA. Se lee en cada vuelta del lazo,
sin temporizador de antirrebote. Se puede cambiar el filtro y volver a escuchar
la misma grabación sin modificarla.

Una tarea dedicada escribe al DAC continuo de GPIO25 a 8 kHz, APLL, con seis
búferes DMA de 512 B físicos (tres bloques de audio) y una cola de dos bloques.
El lazo principal procesa audio solo si hay lugar en la cola; las esperas del
DAC ocurren en su tarea. Las escrituras parciales conservan el desplazamiento
y se reintentan sin perder muestras. Mientras no hay audio se repone silencio
128. Al final se escriben cuatro bloques silenciosos para desplazar el audio
de DMA antes de confirmar LISTA. Puede haber una breve latencia al empezar y
terminar, y clics en las transiciones.

Se requiere `CONFIG_DAC_DMA_AUTO_16BIT_ALIGN=y`, presente en la configuración.
La conversión al DAC es `round(127.5 + 127.5*v)`, limitada a 0–255; una muestra
no finita produce 128. El watchdog RX solo informa errores y no interrumpe
una reproducción si el emisor se desconecta.

## Filtro

Conectar un botón entre **GPIO32 y GND**, con pull-up interno. Arranca en
`SIN FILTRO`; cada pulsación aceptada avanza
`SIN FILTRO → FIR → NOTCH → ESPECTRAL → SIN FILTRO`.
El lazo principal atiende el botón aunque no lleguen INPUT o se desconecte
nodo 1. El antirrebote exige unos 30 ms de nivel estable tanto al pulsar como
al soltar, y bloquea nuevas pulsaciones durante 200 ms después de cada cambio
por botón. Mantenerlo pulsado no repite el cambio; una pulsación detectada
durante el bloqueo se descarta y requiere soltar y volver a pulsar.

Los cambios se aplican entre bloques completos de reproducción: cada bloque
toma una copia del modo al comenzar y la usa hasta encolarse en el DAC. El
audio ya encolado conserva su modo anterior. El botón, los comandos y los
filtros se ejecutan en la misma tarea principal; la tarea DAC solo consume
códigos ya convertidos y no comparte la variable del modo, por lo que no
se requiere `std::atomic` en esta implementación.

| Modo | Salida |
| --- | --- |
| SIN FILTRO | Audio grabado sin filtrar, después de decodificar μ-law. |
| FIR | Kaiser de 37 coeficientes. Inicialmente pasa bajas con corte de 1500 Hz; retardo de 18 muestras (2.25 ms). |
| NOTCH | Inicialmente rechaza 2150 Hz con Q = 8.5. |
| ESPECTRAL | FFT → resta espectral con piso de ruido adaptativo → IFFT con solape y suma; retardo algorítmico adicional H=N/2 (16/32/64 ms). |

Los coeficientes se calculan en double y se guardan en float. Ambos filtros
procesan todas las muestras reproducidas y mantienen estado entre bloques y
cambios de modo. Al empezar cada reproducción se reinician sus estados,
conservando los parámetros. Cambiar banda o notch reinicia solo ese filtro.
El modo vigente elige la salida de cada bloque; con `auto on` se selecciona
al comenzar la reproducción según el diagnóstico guardado (ver más abajo).

## Ruta espectral

Al arrancar, antes de iniciar la recepción, valida una FFT ESP-DSP de N=256 contra una DFT directa en double (DC y dos tonos fuera de bin, sin ventana): imprime error complejo máximo, relativo respecto al máximo de la DFT, PASS si es finito y menor que 1e-4, y duración total; libera los ~3 KiB temporales y un FAIL se informa sin detener el arranque.

Los pasos **6b-1 y 6b-2** implementan el nodo 3 en esta misma placa, en `src/espectral.*`.
Reutiliza de `nodo1/src/espectro.cpp` la raíz de Hann periódica, la tabla y las
llamadas FFT de ESP-DSP. No quita la media antes de la FFT y conserva los valores
complejos. Calcula sus propias magnitudes y piso de ruido; no usa la referencia
limpia ni el diagnóstico del nodo 1 para decidir la ganancia espectral.

Cada bloque decodificado alimenta **las dos rutas independientes**, aunque se
escuche una sola: FIR y notch procesan todas las muestras, y el espectral recibe
esas mismas muestras antes de que se seleccione la salida temporal. La ventana
es **N = 256, 512 o 1024** (inicial 1024), el avance **H=N/2** y fs=8000 Hz.
Cada lote de 512 contiene 512/H saltos de análisis.
El historial contiene el bloque anterior y el actual; después del análisis,
la IFFT y la síntesis se suma la primera mitad con la cola anterior y se guarda
la segunda mitad para el bloque siguiente.

Se usa la misma ventana en análisis y síntesis:

```text
w[n] = sqrt(0.5 * (1 - cos(2*pi*n/N)))          (periódica: denominador N)
w[n]^2 + w[n+H]^2 = Hann[n] + Hann[n+H] = 1   (0 <= n < H, H = N/2)
```

Por tanto, con ganancia 1 la suma con solape tiene **reconstrucción perfecta**
en aritmética exacta; en float32 quedan errores de redondeo. ESP-DSP realiza
una FFT directa sin normalizar. La inversa usa
`IFFT(X) = conj(FFT(conj(X))) / N`, con reordenamiento de bits después de cada
FFT y división por **N una sola vez**. No se aplica otra escala al solape.

`modificar_espectro()` aplica una ganancia real a las partes real e imaginaria
de cada bin positivo y repone `X[N-k] = conj(X[k])`. DC y Nyquist mantienen parte
imaginaria cero. La ganancia conserva la fase de cada bin y la simetría necesaria
para obtener una salida real; su cálculo se describe en "Resta espectral".

El historial y la cola se limpian al iniciar **cada** reproducción. El primer
salto de H muestras corresponde a silencio; el segundo entrega el primer
salto grabado. El retardo algorítmico es **H/fs = 16/32/64 ms**, aparte de
las colas y DMA del DAC. Al agotar la grabación, el lazo de reproducción procesa
un bloque extra de ceros por ambas rutas antes de marcar el último bloque del
DAC. Así se recuperan las últimas H muestras del espectral; el resto del lote es cola. Este vaciado se
hace en todos los modos: en SIN FILTRO añade silencio al final, y en FIR/NOTCH
permite salir a su cola. No modifica el audio guardado ni el receptor.

Se puede cambiar de modo entre bloques sin reiniciar filtros. Como las salidas
tienen retardos distintos, el cambio puede producir un salto o clic; para
comparar, elegir el modo antes de reproducir la misma grabación completa.

**Memoria adicional de los búferes:**

| Búfer | Bytes |
| --- | ---: |
| FFT compleja, 2 × 1024 float | 8192 |
| Tabla FFT, 1024 float | 4096 |
| Ventana, 1024 float | 4096 |
| Historial, 1024 float | 4096 |
| Cola de solape, 512 float | 2048 |
| Salida espectral, 512 float | 2048 |
| Total | **24 576 B (24 KiB)** |

Además se agregan unos pocos contadores y la reserva interna de ESP-DSP para
el reordenamiento de bits. Los búferes de audio son estáticos, sin arreglos
grandes en la pila ni reservas por bloque. La biblioteca se inicia antes de
reservar la grabación para conservar el margen existente de 48 KiB libres;
la duración disponible puede reducirse. Revisar la capacidad impresa al arrancar.
`src/idf_component.yml` declara ESP-DSP como en nodo 1, y `sdkconfig.esp32dev`
habilita su implementación optimizada con longitud máxima 1024.

**Costo y validación pendientes en placa para esta versión:** cada bloque añade dos FFT de 1024
puntos (10 240 mariposas en total), dos reordenamientos y recorridos lineales.
También se calculan magnitudes y, después del calentamiento, 513 medianas de
8 valores y 513 medianas de 31 valores, más la ganancia por bin. No se ha medido
la duración ni se ha compilado o ejecutado la versión con resta. El monitor
separa `proc temporal`, `proc espectral` y `proc total`; el **máximo total** debe
quedar holgadamente por debajo de **64 000 us**, dejando tiempo para RX y consola.
La medición incluye el bloque final de vaciado. La capacidad de grabación, los
tiempos reales y la reducción de ruido deben comprobarse con el hardware.

## Resta espectral

El estimador conserva en un anillo las magnitudes originales de las últimas
**8 tramas**, incluida la actual. Calcula la mediana temporal en cada uno de
los **513 bins** (DC a Nyquist) y suaviza ese perfil con una mediana de **31 bins**.
Los extremos se reflejan sin repetir el valor del borde. Solo se usan muestras
actuales y pasadas, aunque el audio provenga de una grabación.

La primera FFT contiene medio bloque de ceros y no entra al historial de ruido.
Durante las primeras ocho llamadas a `espectral_procesar` la ganancia es 1;
en la novena ya hay ocho tramas reales y empieza la resta. Al iniciar otra
reproducción se limpian el historial de ruido, el audio y el solape, conservando
alfa y ganancia mínima. El calentamiento se repite en todos los modos porque
ambas rutas se calculan siempre.

Para magnitud `M[k]` y piso suavizado `P[k]`, se aplica:

```text
G[k] = max(gmin, min(1 - alfa * P[k] / max(M[k], 1e-12), 1))
Y[k] = G[k] * X[k]
```

Los parámetros iniciales son **alfa = 3** y **gmin = 0.05**. Alfa mayor resta
más ruido; gmin limita cuánto se atenúa cada bin. Un filtrado más agresivo puede
reducir también señal útil y producir ruido musical. El estimador no distingue
perfectamente señal y ruido superpuestos, ni garantiza eliminar un pitido estrecho:
la mediana frecuencial puede excluirlo del piso estimado. P1 se debe comprobar
en placa y registrar si no alcanza la atenuación esperada. Esta versión básica
no incluye protección de tonos ni un método adicional de detección de picos.

El comando configura la intensidad, pero no cambia el modo seleccionado:

```text
espectral 3 0.05
modo espectral
estado
reproducir
```

Se admite **0.5 ≤ alfa ≤ 10** y **0 ≤ gmin ≤ 0.5**, incluidos los extremos.
Se requieren exactamente dos números finitos; argumentos faltantes o adicionales,
`nan`, `inf` y valores fuera de rango imprimen `Error:` sin modificar parámetros.
Los cambios se aplican entre bloques, sin borrar el historial del estimador.
Se guardan solo en RAM: reiniciar la placa restaura 3 y 0.05.

**Memoria adicional del estimador**, aparte de los 24 KiB de la tubería:

| Búfer | Bytes |
| --- | ---: |
| Magnitudes, 513 float | 2052 |
| Historial de ruido, 8 × 513 float | 16 416 |
| Perfil temporal, 513 float | 2052 |
| Piso suavizado, 513 float | 2052 |
| Trabajo compartido de medianas, 31 float | 124 |
| Total de arreglos | **22 696 B (22.16 KiB)** |

Se suman los índices, la bandera de arranque y dos parámetros float. No se
reservan arreglos por bloque ni se colocan estos búferes en la pila. La reserva
disponible para grabar puede bajar; comprobar al arrancar que alcanza para la
prueba antes de interpretar una grabación truncada como un fallo del filtro.

## Comandos desde el monitor

El firmware muestra el eco de las teclas; Enter ejecuta y Backspace corrige.
Los comandos no esperan audio y se aplican entre bloques completos. Mientras
se escribe, se pausa el resumen periódico.

| Comando | Efecto |
| --- | --- |
| `estado` | Muestra modo, banda, notch, coeficientes, alfa, ganancia mínima y N/H espectrales. |
| `modo sin`, `modo fir`, `modo notch`, `modo espectral` | Selecciona la escucha; ESPECTRAL conserva la última selección temporal para comparar ambas rutas. |
| `banda <inf> <sup>` | Recalcula el FIR; admite 100 ≤ inf < sup ≤ 3000 Hz. |
| `notch <f> <q>` | Recalcula el notch; admite 100–3000 Hz y Q de 0.5–20. |
| `espectral <alfa> <gmin>` | Ajusta la resta; alfa 0.5–10, gmin 0–0.5. No selecciona el modo ni reinicia el estimador. |
| `reproducir` | Igual que GPIO33; requiere LISTA. |
| `umbral <factor>` | Ajusta el disparo, de 1.5 a 20; inicialmente 3.0. |
| `calibrar` | Repite la calibración en silencio (16 bloques ignorados + mediana de 16); no disponible durante reproducción. |
| `grabacion` | Muestra estado, duración guardada, capacidad, ruido de fondo y umbral. |
| `vista breve`, `vista todo` | Selecciona el resumen compacto (predeterminado al arrancar) o la línea completa con todos los totales. |
| `metricas` | Reimprime tabla y CSV de la última reproducción terminada; durante otra reproducción conserva el informe anterior. |

La banda inicial es 100–1200 Hz y el notch 2150 Hz, Q 8.5. Con banda inferior
menor que 600 Hz, el FIR es pasa bajas con corte `sup + 300` Hz; desde 600 Hz
es pasa banda con cortes `inf - 300` y `sup + 300` Hz. Un valor inválido imprime
`Error:` sin cambiar parámetros. Toda la configuración se guarda solo en RAM.

## Conexiones

- GPIO19 (RX UART1) ← GPIO18 (TX nodo 1), con GND común.
- GPIO18 del nodo 2 queda como TX sin conectar.
- GPIO25 → Sallen-Key → PAM8403 → parlante, con el acoplamiento del montaje.
- GPIO4 → resistencia de 220–330 Ω → ánodo del LED; cátodo a GND.
- GPIO32 → botón de filtro → GND.
- GPIO33 → botón de reproducción → GND.

El LED indica errores o pérdidas recientes (500 ms), o ausencia de INPUT
válido por 200 ms. Arranca encendido hasta recibir INPUT.

## Contadores del monitor

El resumen de aproximadamente un segundo usa `vista breve` por defecto:

```text
#0001 | FIR | GRABANDO 2.048 s | RX 15.6/s | RMS 0.025 fondo 0.003 | proc T 0.000 ms E 0.000 ms
```

Muestra el modo, estado y segundos guardados; durante REPRODUCIENDO muestra
`actual/total s`, según la posición decodificada (el audio puede seguir en las
colas del DAC). RX es la tasa de paquetes INPUT válidos por segundo, calculada
con el tiempo real entre resúmenes. RMS y fondo tienen tres decimales; `proc T`
y `E` son los promedios temporal y espectral por bloque, en milisegundos.

Solo si aumentó algún contador de error, pérdida o desborde desde el resumen
anterior se añade `ALERTA`, con el aumento y el total de cada contador afectado;
por ejemplo, ` | ALERTA err_crc +1 (total 3), perdidos +2 (total 2)`.
Si no hay nuevos incidentes, la alerta desaparece en el siguiente resumen aunque
los totales sigan siendo distintos de cero. INPUT, DIAG y sesiones no disparan
alertas. Mientras se escribe se pospone la impresión: el siguiente resumen
incluye los aumentos desde el anterior y RX usa todo ese tiempo transcurrido.

`vista todo` conserva la línea completa anterior. Sus contadores son acumulados
desde el arranque, excepto los tiempos de procesamiento, calculados por
intervalo. Ambas vistas actualizan la referencia de las alertas y de la tasa RX;
cambiar de vista no reinicia los totales. Los campos de la línea completa son:

| Campo | Significado |
| --- | --- |
| INPUT / DIAG | Paquetes válidos de cada tipo, también durante reproducción. |
| err_trama | Más de 2094 bytes sin delimitador; descarta hasta el siguiente cero. |
| err_cobs | COBS inválido o salida mayor que el búfer. |
| err_crc | CRC distinto del calculado. |
| err_cabecera | Cabecera, origen, destino, tipo o tamaños inválidos. |
| perdidos | Saltos hacia delante de sequence dentro de la sesión, incluidos ambos tipos. |
| sesiones | Primera sesión y cada cambio posterior; no es un error. |
| DAC … B | Códigos de 8 bits aceptados por el controlador, incluido silencio continuo. |
| desbordes_dac | Timeout de escritura de un segundo; se conserva y reintenta el resto. No cuenta la espera normal por espacio en la cola. |
| proc total prom / max … us | Decodificación, ambas rutas, todas las métricas, selección, conversión y encolado por bloque reproducido; excluye la espera DMA en la tarea DAC. |
| proc temporal prom / max … us | FIR y notch, selección temporal y FFT de métricas de esa salida. |
| proc espectral prom / max … us | Historial, ventanas, FFT, estimación del ruido, ganancia, IFFT, solape y FFT de métricas de esa salida. |

Los tres tiempos muestran 0/0 si no hubo bloques reproducidos en el intervalo.
Se reinician también al comenzar otra reproducción y mientras se escribe en
la consola; no representan el retardo algorítmico ni la espera del DAC.
Las métricas finales tienen acumuladores independientes para toda la reproducción,
que no se reinician al imprimir resúmenes ni mientras se escribe.

La primera secuencia establece la referencia sin inferir pérdidas anteriores.
Se contempla el retorno de UINT32_MAX a cero; duplicados y secuencias anteriores
no suman pérdidas. `first_sample` no programa la reproducción.

## Prueba entre placas

1. Conectar GPIO33 a GND mediante un botón y arrancar el nodo 1 con micrófono.
2. En silencio, comprobar ESPERANDO y capacidad impresa suficiente; esperar
   unos 2 s hasta `Grabación: fondo calibrado <valor>` antes de iniciar P1.
3. Reproducir P1 desde la laptop: debe pasar a GRABANDO y, aproximadamente un
   segundo después de terminar la señal, a LISTA. Con capacidad máxima debe
   poder guardar la prueba de 10 s, el pre-disparo y la cola de silencio.
4. Pulsar GPIO33: escuchar el pitido en SIN FILTRO. Esperar LISTA, elegir NOTCH
   con GPIO32 o `modo notch` y repetir: el pitido debe atenuarse.
5. Hablar o aplaudir: comprobar que una actividad nueva reemplaza la grabación.
6. Revisar INPUT y DIAG durante reproducción: aproximadamente 15–16 por segundo,
   errores, perdidos y desbordes_dac en cero. Medir proc prom/max en cada modo;
   cada bloque debe procesarse en menos de 64 000 us.
7. Probar `grabacion`, `umbral 3`, `banda 100 1200` y `notch 2150 8.5`;
   comprobar rechazo de valores fuera de rango. Ejecutar `calibrar` en silencio
   y esperar el fondo calibrado. Durante reproducción, verificar que `calibrar`
   imprime el rechazo y el audio continúa. Reiniciar el nodo 1 y comprobar
   que la sesión nueva repite la calibración.
8. Desconectar RX durante reproducción: el LED informa ausencia, pero la
   grabación sigue hasta terminar. Reconectar y comprobar recuperación de RX.

### Prueba del paso 6b-2 (pendiente en placa)

1. Tras compilar y cargar esta versión, revisar RAM y capacidad al arrancar,
   comprobar que cabe la señal, calibrar en silencio y grabar P1 con el micrófono.
   `estado` debe indicar alfa 3, ganancia mínima 0.05, N = 1024 y H = 512.
2. Elegir `modo sin`, ejecutar `reproducir` y esperar LISTA. Elegir `modo espectral`
   y reproducir la misma grabación: comprobar si baja claramente el pitido de
   2150 Hz. Registrar el resultado; si no baja, queda pendiente ese criterio de P1.
3. Grabar P3, comparar SIN FILTRO y ESPECTRAL y comprobar que baja el ruido blanco.
   Repetir la misma grabación completa con `espectral 1 0.1` y `espectral 8 0.02`.
   Elegir los parámetros antes de cada reproducción y esperar LISTA entre pruebas;
   anotar reducción del ruido, pérdida de audio útil y ruido musical.
4. Repetir una reproducción con idénticos parámetros: no debe aparecer audio
   residual de la anterior. Se reinicia el calentamiento, se conservan alfa/gmin
   y se recupera la cola final. Verificar el ciclo del botón GPIO32.
5. Probar `espectral 0.5 0` y `espectral 10 0.5`; ambos extremos son válidos.
   Probar `espectral 0.4 0.05`, `espectral 3 0.6`, `espectral nan 0.05`,
   `espectral 3 inf`, `espectral 3` y `espectral 3 0.05 extra`: todos deben
   imprimir error y conservar los últimos valores válidos en `estado`.
   Restaurar `espectral 3 0.05` antes de seguir.
6. Durante una reproducción completa sin escribir comandos, comprobar
   `proc temporal`, `proc espectral` y `proc total` en todos los modos.
   Ambas rutas se calculan siempre y el máximo total debe ser mucho menor
   que 64 000 us. Errores, `perdidos` y `desbordes_dac` deben mantenerse en 0.

La reconstrucción con ganancia 1 corresponde a la base 6b-1; esta versión ya
modifica el espectro y no se espera que suene igual a SIN FILTRO. Estos pasos
son instrucciones de validación, no resultados medidos de la resta espectral.

El ruido de sala y una señal presente durante la calibración inicial pueden
alterar el disparo. En LISTA el fondo queda fijo; ajustar el umbral o ejecutar
`calibrar` en silencio si cambia mucho el ambiente. Una actividad continua llena la memoria
y puede disparar otra grabación después; no se conserva la anterior al reemplazarla.

## Compilar, subir y abrir monitor

En PlatformIO, seleccionar proyecto nodo2 y entorno esp32dev. Usar Build,
Upload y Monitor en el puerto USB de esta placa; UART0 funciona a 115200.

## Banda protegida y modo automático

El nodo 1 es la fuente de la banda protegida. La placa recibe mensajes
`CONTROL CONFIG` por UART1 al arrancar, cuando cambia la banda y repetidos
aproximadamente cada segundo. Cada configuración tiene un `config_id`; una
configuración con el mismo identificador no se aplica dos veces. La banda se
valida en el receptor y se muestra como:

```text
Banda del nodo 1: 100-1200 Hz (config 1)
```

Si llega una configuración nueva durante `REPRODUCIENDO`, se guarda y se aplica
al terminar la reproducción. El comando local `banda <inf> <sup>` sigue
disponible para pruebas, pero una configuración con un ID nuevo del nodo 1
vuelve a ser la vigente. Repetir el mismo ID conserva el ajuste local.

El modo automático se controla con:

```text
auto on
auto off
```

El valor inicial es `off`. El diagnóstico se guarda junto con cada grabación,
usando los DIAG válidos recibidos mientras el estado es `GRABANDO`; no se usa
el diagnóstico en vivo durante una reproducción posterior. Se conserva la
sugerencia más frecuente contando por `filtro_n2`, sumando todos los tipos de
ruido y excluyendo el filtro 0. Para el filtro ganador se informa su tipo de
ruido más frecuente. En empates de filtro o tipo gana el identificador menor.
Para notch o peine se usa la mediana de los picos válidos del filtro ganador.
Sin sugerencias se guarda tipo 0, filtro 0 y pico −1. Calibrar borra también el
diagnóstico, sus votos y sus picos; la misma limpieza ocurre al invalidar el audio
por una nueva sesión y al comenzar otra grabación.

**Limitación de asociación temporal:** no se conserva el diagnóstico del audio
del pre-disparo. Además, INPUT llega antes de su DIAG; si ese INPUT termina la
grabación, el estado ya es LISTA cuando llega el DIAG y este no se incluye en la
votación. Se mantiene esta aproximación sin asociar diagnósticos por índices de
muestras.

Al iniciar una reproducción con `auto on`:

| Sugerencia | Acción |
| --- | --- |
| Filtro 0 | `SIN FILTRO` |
| Filtro 1 | FIR con la banda protegida vigente |
| Filtro 2 | Notch en el pico guardado, Q 8.5 |
| Filtro 3 | Notch en el pico dominante, Q 8.5 |

La ruta `ESPECTRAL` no se reemplaza por el automático. Si ya estaba
seleccionada, se mantiene como salida y solo se actualizan los parámetros de la
ruta temporal. El botón GPIO32 y cualquier comando `modo` desactivan el
automático y muestran `Auto: desactivado`.

`estado` y `grabacion` muestran el estado de `auto` y el diagnóstico guardado.
Como el nodo 1 todavía puede informar diagnóstico 0 para señales de banda
ancha, P3 puede reproducirse automáticamente como `SIN FILTRO`; esto queda
como limitación del diagnóstico actual del nodo 1.

### Prueba de banda y automático con dos placas

Pendiente de ejecutar en hardware con ambos firmwares actualizados:

1. Conectar TX GPIO18 de nodo 1 a RX GPIO19 de nodo 2 y GND común. Arrancar
   ambas placas: nodo 2 debe informar `100-1200 Hz (config 1)` y `estado` debe
   mostrar origen `nodo1`. En `vista todo`, CONTROL debe aumentar aproximadamente
   una vez por segundo, sin repetir el mensaje de aplicación del mismo ID.
2. En nodo 1, ejecutar `banda 100 3000`: nodo 2 debe aplicar config 2 tras el
   DIAG del bloque. Repetir el comando conserva config 2. `banda 0 3000` y
   `banda 100 4000` deben rechazarse sin cambiar banda ni ID.
3. Reiniciar solo nodo 2: debe recuperar la banda vigente en aproximadamente
   un segundo. Probar `banda 100 1500` localmente: las repeticiones de config 2
   deben conservar ese ajuste. Cambiar a `banda 100 1200` en nodo 1 debe aplicar
   config 3 con origen `nodo1`.
4. En nodo 2, ejecutar `auto on`, grabar un tono fuera de banda (P1, cercano a
   2148.4 Hz) y reproducir con la sala en silencio: debe usar el diagnóstico
   guardado y seleccionar NOTCH. Cambiar la banda en nodo 1 durante la
   reproducción: debe aplicarse al terminar, sin cortar el audio.
5. Con una grabación terminada, ejecutar `calibrar` y consultar `estado` y
   `grabacion`: deben mostrar diagnóstico tipo 0, filtro 0 y pico −1, sin conservar
   el anterior. Esperar la calibración en silencio antes de grabar otra vez.
6. Comprobar P3 sin detección tonal → SIN FILTRO; botón o `modo` → auto off;
   `modo espectral`, `auto on` y reproducir → conserva ESPECTRAL.
7. Revisar totales con `vista todo`: sin errores, pérdidas ni desbordes DAC en
   nodo 2; sin nuevos overruns ni desbordes ADC en nodo 1, con periodos próximos
   a 64 ms. La votación entre distintos tipos requiere DIAG de prueba: el nodo 1
   actual solo sugiere tonal/notch; un caso de 4 votos FIR de un tipo más 4 de
   otro debe ganar frente a 5 votos notch, y un empate debe elegir el menor ID.

## Métricas de cuatro modos en una reproducción (CSV v3)

Al terminar cada reproducción, después de drenar el DAC y antes de aplicar una
banda pendiente, se imprime una tabla de cuatro modos y cuatro líneas `METRICAS,3,`: SIN FILTRO,
FIR, NOTCH y RESTA. Se evalúan todos con la misma grabación y reproducción,
aunque solo se escuche el seleccionado. No hace falta repetir para cada filtro.
NOTCH usa su frecuencia/Q vigentes; no busca un notch óptimo distinto para cada
audio. Esos parámetros se incluyen en las cuatro filas para interpretar la prueba.
`metricas` vuelve a mostrar el mismo informe; no recalcula ni cambia la RAM
registrada. Antes de terminar la primera reproducción avisa que no hay resultados.

Son **estimadas sin referencia limpia**. La entrada `x` es la grabación μ-law
**decodificada**, no el INPUT original previo a grabación. Las salidas medidas
son float antes del recorte y cuantización del DAC, filtro analógico y parlante.
La placa no calcula MSE o SNR respecto de una señal limpia desconocida. Para las
métricas exactas en PC se necesita una referencia limpia y alineamiento adecuado.

### Selección temporal independiente

La ruta temporal conserva su último modo SIN FILTRO, FIR o NOTCH aunque se
escuche ESPECTRAL. Por ejemplo, ejecutar `modo fir`, luego `modo espectral` y
`reproducir` permite escuchar resta mientras se evalúan **los cuatro modos**. `estado`
muestra la selección temporal independiente. Al arrancar es SIN FILTRO.
Con `auto on`, el diagnóstico configura la ruta temporal al comenzar cada
reproducción, incluso si la escucha permanece en ESPECTRAL. Ambas rutas siguen
procesando los mismos bloques; se conservan las salidas FIR y NOTCH separadas
para medirlas, sin modificar sus coeficientes ni sus algoritmos. No se añade un segundo DAC.

### Alineamiento y ventana común

Se compara el mismo número L de muestras para x y las cuatro salidas
(SIN FILTRO reutiliza x):

- SIN FILTRO: `y[n]` frente a `x[n]`, desplazamiento cero.
- FIR: `y[n+18]` frente a `x[n]`, retardo de grupo de 2.25 ms.
- NOTCH: desplazamiento fijo cero. El IIR tiene fase y retardo de grupo dependientes
  de frecuencia; su MSE incluye esa modificación de fase. Cero no implica fase nula.
- RESTA: `y[n+H]` frente a `x[n]`, H=N/2; retardo de 16/32/64 ms.

Se conserva un lote anterior de x, FIR, NOTCH y RESTA: la salida espectral se alinea con su desplazamiento vigente, y las últimas 18 muestras del FIR alineado se
completan con el principio de su bloque actual. El bloque de ceros de vaciado
existente recupera las últimas muestras reales. No se incluyen en el MSE ni el
silencio inicial del espectral ni las colas posteriores al tramo alineado de L
muestras. Los retardos reportados son algorítmicos; excluyen adquisición por
bloques, comunicación, colas/DMA, circuito analógico y tiempo hasta oír el audio.

Para energía se usa FFT de N vigente, avance H=N/2 y raíz de Hann periódica, igual para
x, FIR, NOTCH y RESTA **ya alineadas y reconstruidas**. SIN FILTRO reutiliza
la energía de x y su MSE es cero; no se añade una FFT idéntica. Se analizan ventanas
`[ceros, bloque 0]`, `[bloque 0, bloque 1]`, ..., `[último bloque, ceros]`.
Las ventanas al cuadrado suman uno para cada muestra real, incluidos los bordes.
Se suman potencias unilaterales `2*|FFT|²/N` (DC/Nyquist llevan peso 1), sin
retirar DC ni cambiar el audio. Solo se acumulan bins con centro en 100–3000 Hz.
Las frecuencias se asignan por el centro del bin, con resolución 8000/N Hz.
En esta descripción de ventanas, cada bloque de análisis tiene H muestras,
aunque el transporte y la reproducción entregan lotes de 512.

Se reutilizan tabla, ventana y área de trabajo FFT de `espectral` en llamadas
secuenciales después de reconstruir el audio. Las FFT de métricas no cambian el
historial, solape ni estimador. No se confunde el espectro interno modificado con
el espectro de la salida final tras solape y síntesis.

### Definiciones

La banda protegida, el pico del diagnóstico y los parámetros se
capturan al comenzar la reproducción. Las energías se acumulan en double durante
el tramo completo; los cocientes y logaritmos se calculan al imprimir. No se
promedian cocientes ni dB de bloques individuales.

| Campo | Definición y límite de interpretación |
| --- | --- |
| SNR estimada entrada/salida | `10*log10(E_dentro/E_fuera)`, dentro de 100–3000 Hz. Es relación por bandas: ruido dentro de la protección cuenta como energía interior, y señal útil fuera cuenta como exterior. |
| ΔSNR estimada | SNR estimada de salida menos SNR estimada de entrada. |
| Energía en banda conservada % | `100*E_dentro_salida/E_dentro_x`. No distingue ruido de señal limpia y puede superar 100 %. |
| Atenuación dB | `10*log10(E_interferencia_x/E_interferencia_salida)`. Positiva indica reducción. Si el pico guardado es finito y está en 100–3000, usa el bin más cercano ±2, recortado a ese intervalo; si no, usa toda la energía exterior a la protección. |
| MSE(x) | `sum((y_alineada-x)^2)/L`. Mide cuánto cambió la ruta la entrada contaminada; reducir ruido puede aumentar este MSE. |
| Retardo ms | 0 fijo para SIN FILTRO/NOTCH, 2.25 para FIR y H/8 para RESTA, con la salvedad de fase del notch indicada arriba. |
| Proc prom/max ms por modo | FIR y NOTCH: cálculo **conjunto y compartido** de ambos filtros + FFT de métricas de esa salida. RESTA: su procesamiento y FFT de métricas. SIN FILTRO: 0 adicional, reutiliza x. No son tiempos aislados de cada filtro: no sumar filas. |
| Carga por ruta % | `100*proc_prom_us/64000`. No es una medición del uso global de CPU del sistema. |
| Proc total prom/max | Decodificación, cuatro modos, métricas completas (incluida FFT de x y MSE), conversión y encolado. Es la medida para contrastar con el plazo de 64 ms; los tiempos de las rutas no incluyen el trabajo común. |
| Proc métricas prom/max | Coste completo de alineamiento, MSE y FFT de métricas; ya está incluido en total, no debe sumarse otra vez. |
| RAM libre/mayor bloque B | RAM interna con capacidad de 8 bits al terminar, antes de imprimir y aplicar CONFIG pendiente; incluye la reserva de audio todavía existente. No es un máximo de consumo de toda la ejecución. |

`NA` indica un valor no disponible: energías cero, cociente indefinido o informe
invalidado. No se añade un epsilon para inventar un dB finito. Con protección
100–3000 no existen bins exteriores en el intervalo medido: SNR y ΔSNR son NA,
y también la atenuación exterior si no hay pico. Energía en banda y MSE pueden
seguir disponibles. Si ambas señales son silencio, sus cocientes son NA y el
MSE válido es cero. `OK` significa configuración consistente y datos finitos;
no garantiza que todas las razones tengan denominador distinto de cero.

Se permite cambiar la escucha durante la reproducción, incluida la selección
temporal, sin invalidar: siempre se miden los cuatro modos. Recalcular
banda/notch o cambiar los parámetros espectrales marca
el informe `CONFIG_CAMBIADA`; se conserva la reproducción y sus tiempos, pero
las métricas de señal salen NA para evitar comparar una mezcla de configuraciones
como un solo filtro. El CSV conserva los parámetros iniciales, no los finales.
Cambiar solo el modo de escucha no cambia el procesamiento que se está midiendo.
Un comando espectral con los mismos parámetros efectivos tampoco invalida.
Datos no finitos marcan `DATOS_NO_FINITOS`; un tramo vacío, `SIN_MUESTRAS`.
Una nueva reproducción inicia acumuladores nuevos y vuelve a permitir `OK`.

### CSV para la computadora

Cada informe lleva exactamente cuatro registros con punto decimal, sin unidades
dentro de los campos y `NA` para valores no disponibles. Versión 3: 35 campos, los 33 de v2 más `n_fft` y `h_fft` al final; cabecera para el script de PC:

```text
METRICAS,version,reproduccion,estado,ruta,modo,banda_lo_hz,banda_hi_hz,pico_hz,snr_x_db,snr_y_db,delta_snr_db,energia_banda_pct,atenuacion_db,mse_x,retardo_ms,proc_prom_ms,proc_max_ms,carga_pct,ram_libre_b,ram_bloque_b,muestras,bloques_proc,proc_total_prom_ms,proc_total_max_ms,carga_total_pct,metricas_prom_ms,metricas_max_ms,notch_hz,notch_q,alfa,ganancia_minima,metodo_atenuacion,n_fft,h_fft
```

`ruta` es `temporal` o `espectral`; `modo` es `SIN_FILTRO`, `FIR`, `NOTCH` o
`RESTA`. El método de atenuación es `pico` o `fuera_banda`. El identificador de
reproducción aumenta hasta reiniciar la placa; `metricas` repite ese ID. Los
campos comunes, RAM y SNR de entrada son iguales para las cuatro filas del informe.
Hay tres registros `temporal` (SIN_FILTRO, FIR, NOTCH) y uno `espectral` (RESTA).
El script conserva compatibilidad con v1/v2 (N=1024, H=512 fijos en esas
versiones); v1 contiene solo dos resultados. No inventa modos no medidos.
`bloques_proc` incluye la llamada de vaciado; `muestras` solo cuenta el audio
real alineado. No mezclar esos dos contadores para inferir duración.

### Recursos y validación pendiente en placa

Los búferes auxiliares suman **30 KiB de arreglos float estáticos**, frente a
18 KiB de v1: entrada preservada, salidas FIR y NOTCH independientes, cuatro bloques
anteriores y cuatro historiales de análisis. El incremento sobre v1 es **12 KiB** (2 KiB más que v2 para la salida
espectral anterior al compensar retardos menores que 512), además
de resúmenes/contadores. No hay reservas por bloque ni duplicación de ventana,
tabla o área FFT. La duración máxima disponible de grabación puede disminuir;
comprobar la capacidad impresa al arrancar.

Se ejecutan cuatro FFT de métricas por ventana alineada (x, FIR, NOTCH, RESTA),
frente a tres en v1. La llamada final contiene `4*(512/H + 1)` FFT al añadir la ventana de
borde (8 con N=1024, 12 con N=512, 20 con N=256). Sus tiempos se incluyen en máximos y promedios; hay que medir esa llamada
además de las normales. SIN FILTRO reutiliza el análisis de x. Los promedios
incluyen la primera llamada que prepara el alineamiento. El tiempo total incluye
costos compartidos y es el que debe quedar holgado frente a 64 ms.

### Validación realizada y pendiente

Sin compilar ni cargar firmware: comprobaciones estáticas, 13 pruebas de parser,
captura y referencia numérica en PC, integración con el registro de filtros de
PlatformIO instalado, exportación
de tabla/CSV y generación de figuras PNG/SVG con datos sintéticos. Las pruebas
numéricas independientes comprueban las convenciones de retardo y ventanas, no
ejecutan el C++. Después, el usuario probó esta versión en placa: seis informes
de 91648 muestras, máximo total observado 58.918 ms, RAM libre 82812 B y
mayor bloque 55296 B; sin aumentos de errores, pérdidas ni desbordes DAC en los
reportes recibidos. El margen mínimo observado es 5.082 ms: cumple en estas
corridas, pero no se declara holgura amplia ni garantía para otros escenarios.
El registro está en [VALIDACION_METRICAS.md](../../herramientas_pc/VALIDACION_METRICAS.md).

Después de cargar **nodo 2**, con una grabación LISTA:

1. Conservar parámetros, escribir `reproducir` o usar el botón. Al terminar deben
   aparecer cuatro filas de tabla y cuatro `METRICAS,2,` con el mismo ID. Comprobar
   que SIN_FILTRO tiene MSE 0, energía 100%, ΔSNR 0 y atenuación 0 cuando se definan.
2. Revisar máximo total holgado frente a 64 ms, RAM libre, mayor bloque y capacidad
   de grabación. Sin aumentos nuevos de errores, pérdidas ni desbordes DAC. El
   vaciado puede producir el máximo de procesamiento.
3. Escribir `metricas`: repite los cuatro registros, ID y RAM originales. El
   analizador de PC no debe duplicar las filas. No vuelve a procesar audio.
4. Cambiar solo la escucha durante otra reproducción: informe OK. Cambiar un
   parámetro FIR, notch o espectral: CONFIG_CAMBIADA, métricas de señal NA. La
   siguiente reproducción con configuración estable debe volver a OK.
5. Con protección 100–3000: SNR/ΔSNR NA; MSE y energía pueden seguir definidos.
   En silencio digital los cocientes son NA y MSE válido es 0.
6. Cambiar CONFIG desde nodo 1 durante reproducción: sigue difiriéndose hasta
   después del informe. Nodo 1 y los paquetes UART no se modifican en esta etapa.
7. Abrir el monitor con el filtro `metricas_csv` activado en `platformio.ini`.
   Aparecerá la ruta del CSV al terminar la primera reproducción. Probar comandos
   normales y confirmar que se sigue mostrando toda la consola.
8. Analizar el CSV según el [README de PC](../../herramientas_pc/README.md#captura-y-gráficos-de-métricas).
   Comparar las cifras de la tabla de placa, CSV e informe. El archivo solo guarda
   líneas de métricas; los gráficos son de valores resumidos, no ondas/espectros.

Las pruebas P1/P2/P3/P5 sirven para comparar filtros; P4 sigue como limitación del
diagnóstico de nodo 1, fuera del alcance de estos cambios.

## N configurable por CONFIG de nodo 1

`n 256|512|1024` se escribe en **nodo 1**. Aquí no hay un comando local paralelo:
la placa recibe N/H en los campos de CONFIG de 32 bytes ya existentes. Se valida
N y H=N/2; INPUT sigue con 512 float32, a 921600 baudios, uno cada 64 ms.

Se aplican juntos banda, N e ID. Si está REPRODUCIENDO, se guarda únicamente la
configuración más reciente; se imprime el informe con sus parámetros iniciales,
y después se aplica la pendiente. Un N cambiado limpia ventana, estimador y
solape espectrales, conservando alfa/ganancia mínima. Si N es el mismo no reinicia
espectral; si la banda es la misma tampoco reinicia FIR. Los coeficientes y
retardos temporales se conservan al cambiar solo N.

`estado` muestra el N/H activo. El procesamiento espectral divide cada lote de
512 en 512/H saltos: 1, 2 o 4. La tabla y los arreglos permanecen dimensionados
para 1024; no se reserva memoria al cambiar N. Ocho tramas del estimador y la
mediana de 31 bins conservan sus cantidades; su duración y cobertura en Hz varían.

Las métricas usan el **mismo N y ventana vigentes** para x y las salidas, con
avance H. El retardo espectral compensado/reportado es 64/32/16 ms para
N=1024/512/256. Para H menor que 512, la compensación usa la cola del bloque
espectral anterior y el principio del actual. La llamada final de 512 ceros sigue
recuperando el final; solo se miden las L muestras reales y una ventana de borde H.
MSE temporal debe conservarse con la misma grabación y parámetros. Las energías
por banda pueden variar por resolución, fuga y asignación del centro de los bins;
pico ±2 cubre distinto ancho en Hz según N.

El retardo algorítmico **no es la latencia completa hasta el parlante**: el INPUT,
la tarea DAC y sus colas siguen entregando lotes de 512. El plazo de CPU sigue
siendo 64 ms por lote. Hay 4 × (512/H) FFT de métricas por lote alineado y cuatro
adicionales en el vaciado para la ventana final de H ceros. Validar máximos y
pérdidas para cada N, no extrapolar los tiempos históricos de CSV v2.

El CSV actual es `METRICAS,3,...,metodo_atenuacion,n_fft,h_fft`, cuatro filas con
el N/H inicial del informe. La captura y figuras de PC aceptan v1/v2/v3 y muestran
N/H en tabla y figura. Los resultados v2 ya registrados siguen siendo evidencia
de la versión anterior; esta ampliación queda pendiente de compilación y prueba
en placa. Guía: [PRUEBA_N_CONFIGURABLE.md](../../herramientas_pc/PRUEBA_N_CONFIGURABLE.md).

### Cierre de métricas fuera del plazo de audio

Las cuatro FFT de la última ventana de borde se calculan cuando el DAC confirma
que terminó la reproducción, antes de imprimir el informe y de aplicar CONFIG
pendiente. Se conserva la misma energía acumulada y el mismo MSE; solo cambia
el momento de ejecutar esa ventana. El bloque de ceros que vacía las rutas
sigue procesándose y encolándose durante la reproducción.

La línea `Cierre de métricas después del DAC` informa el costo de esas cuatro
FFT por separado. Este costo está excluido de proc/carga por bloque, tanto en
la tabla como en el CSV `METRICAS,3,`; esas columnas miden el trabajo necesario
antes de encolar cada bloque. El formato CSV conserva sus 35 campos. Para medir
el costo computacional completo de una reproducción, sumar el cierre a
`proc_total_prom × bloques`; conservar el informe de consola para ese dato.
La carga máxima por bloque todavía debe verificarse en placa: diferir el cierre
no garantiza que los bloques normales cumplan el plazo de 64 ms.
