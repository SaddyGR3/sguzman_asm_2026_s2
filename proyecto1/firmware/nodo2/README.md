# Nodo 2: receptor UART, grabación, filtros y salida DAC

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
| REPRODUCIENDO | Decodifica bloques de 512, actualiza FIR y notch y entrega el modo seleccionado al DAC. Sigue leyendo y validando INPUT y DIAG, sin grabar ni disparar. Al drenar el audio y establecer silencio vuelve a LISTA. |

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
con `heap_caps_malloc`, después de iniciar los controladores y la tarea DAC.
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
`SIN FILTRO`; cada flanco de 1 a 0 avanza `SIN FILTRO → FIR → NOTCH → SIN FILTRO`.
Este botón mantiene la lectura una vez por INPUT válido, sin antirrebote;
sin INPUT no se atiende y conviene pulsarlo por más de 64 ms.

| Modo | Salida |
| --- | --- |
| SIN FILTRO | Audio grabado sin filtrar, después de decodificar μ-law. |
| FIR | Kaiser de 37 coeficientes. Inicialmente pasa bajas con corte de 1500 Hz; retardo de 18 muestras (2.25 ms). |
| NOTCH | Inicialmente rechaza 2150 Hz con Q = 8.5. |

Los coeficientes se calculan en double y se guardan en float. Ambos filtros
procesan todas las muestras reproducidas y mantienen estado entre bloques y
cambios de modo. Al empezar cada reproducción se reinician sus estados,
conservando los parámetros. Cambiar banda o notch reinicia solo ese filtro.
El modo vigente elige la salida de cada bloque; no hay selección automática.

## Comandos desde el monitor

El firmware muestra el eco de las teclas; Enter ejecuta y Backspace corrige.
Los comandos no esperan audio y se aplican entre bloques completos. Mientras
se escribe, se pausa el resumen periódico.

| Comando | Efecto |
| --- | --- |
| `estado` | Muestra modo, banda, notch y coeficientes vigentes. |
| `modo sin`, `modo fir`, `modo notch` | Selecciona la salida. |
| `banda <inf> <sup>` | Recalcula el FIR; admite 100 ≤ inf < sup ≤ 3000 Hz. |
| `notch <f> <q>` | Recalcula el notch; admite 100–3000 Hz y Q de 0.5–20. |
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
| proc prom / max … us | Decodificación, ambos filtros, conversión y encolado por bloque reproducido; excluye la espera DMA en la tarea DAC. 0/0 si no hubo bloques reproducidos. |

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

El ruido de sala y una señal presente durante la calibración inicial pueden
alterar el disparo. En LISTA el fondo queda fijo; ajustar el umbral o ejecutar
`calibrar` en silencio si cambia mucho el ambiente. Una actividad continua llena la memoria
y puede disparar otra grabación después; no se conserva la anterior al reemplazarla.

## Compilar, subir y abrir monitor

En PlatformIO, seleccionar proyecto nodo2 y entorno esp32dev. Usar Build,
Upload y Monitor en el puerto USB de esta placa; UART0 funciona a 115200.
