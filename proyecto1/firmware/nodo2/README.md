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
`SIN FILTRO`; cada flanco de 1 a 0 avanza
`SIN FILTRO → FIR → NOTCH → ESPECTRAL → SIN FILTRO`.
Este botón mantiene la lectura una vez por INPUT válido, sin antirrebote;
sin INPUT no se atiende y conviene pulsarlo por más de 64 ms.

| Modo | Salida |
| --- | --- |
| SIN FILTRO | Audio grabado sin filtrar, después de decodificar μ-law. |
| FIR | Kaiser de 37 coeficientes. Inicialmente pasa bajas con corte de 1500 Hz; retardo de 18 muestras (2.25 ms). |
| NOTCH | Inicialmente rechaza 2150 Hz con Q = 8.5. |
| ESPECTRAL | FFT → resta espectral con piso de ruido adaptativo → IFFT con solape y suma; retardo algorítmico adicional de 512 muestras (64 ms). |

Los coeficientes se calculan en double y se guardan en float. Ambos filtros
procesan todas las muestras reproducidas y mantienen estado entre bloques y
cambios de modo. Al empezar cada reproducción se reinician sus estados,
conservando los parámetros. Cambiar banda o notch reinicia solo ese filtro.
El modo vigente elige la salida de cada bloque; no hay selección automática.

## Ruta espectral

Los pasos **6b-1 y 6b-2** implementan el nodo 3 en esta misma placa, en `src/espectral.*`.
Reutiliza de `nodo1/src/espectro.cpp` la raíz de Hann periódica, la tabla y las
llamadas FFT de ESP-DSP. No quita la media antes de la FFT y conserva los valores
complejos. Calcula sus propias magnitudes y piso de ruido; no usa la referencia
limpia ni el diagnóstico del nodo 1 para decidir la ganancia espectral.

Cada bloque decodificado alimenta **las dos rutas independientes**, aunque se
escuche una sola: FIR y notch procesan todas las muestras, y el espectral recibe
esas mismas muestras antes de que se seleccione la salida temporal. La ventana
es **N = 1024**, el avance **H = 512** y la frecuencia de muestreo **8000 Hz**.
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
FFT y división por **1024 una sola vez**. No se aplica otra escala al solape.

`modificar_espectro()` aplica una ganancia real a las partes real e imaginaria
de cada bin positivo y repone `X[N-k] = conj(X[k])`. DC y Nyquist mantienen parte
imaginaria cero. La ganancia conserva la fase de cada bin y la simetría necesaria
para obtener una salida real; su cálculo se describe en "Resta espectral".

El historial y la cola se limpian al iniciar **cada** reproducción. El primer
bloque espectral corresponde a silencio; el segundo entrega el primer
bloque grabado con las ganancias correspondientes. El retardo algorítmico adicional es **H/fs = 64 ms**, aparte de
las colas y DMA del DAC. Al agotar la grabación, el lazo de reproducción procesa
un bloque extra de ceros por ambas rutas antes de marcar el último bloque del
DAC. Así se recuperan las últimas 512 muestras del espectral. Este vaciado se
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
| `modo sin`, `modo fir`, `modo notch`, `modo espectral` | Selecciona la salida. |
| `banda <inf> <sup>` | Recalcula el FIR; admite 100 ≤ inf < sup ≤ 3000 Hz. |
| `notch <f> <q>` | Recalcula el notch; admite 100–3000 Hz y Q de 0.5–20. |
| `espectral <alfa> <gmin>` | Ajusta la resta; alfa 0.5–10, gmin 0–0.5. No selecciona el modo ni reinicia el estimador. |
| `reproducir` | Igual que GPIO33; requiere LISTA. |
| `umbral <factor>` | Ajusta el disparo, de 1.5 a 20; inicialmente 3.0. |
| `calibrar` | Repite la calibración en silencio (16 bloques ignorados + mediana de 16); no disponible durante reproducción. |
| `grabacion` | Muestra estado, duración guardada, capacidad, ruido de fondo y umbral. |

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

El resumen de aproximadamente un segundo agrega estado de grabación, RMS del
último INPUT y ruido de fondo. Los contadores son acumulados desde el arranque,
excepto los tiempos de procesamiento, calculados por intervalo.

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
| proc total prom / max … us | Decodificación, ambas rutas, selección, conversión y encolado por bloque reproducido; excluye la espera DMA en la tarea DAC. |
| proc temporal prom / max … us | FIR y notch, con selección de la salida temporal, por bloque reproducido. |
| proc espectral prom / max … us | Historial, ventanas, FFT, estimación del ruido, ganancia, IFFT y solape por bloque reproducido. |

Los tres tiempos muestran 0/0 si no hubo bloques reproducidos en el intervalo.
Se reinician también al comenzar otra reproducción y mientras se escribe en
la consola; no representan el retardo algorítmico ni la espera del DAC.

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
