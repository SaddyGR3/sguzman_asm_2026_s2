# Nodo 2: receptor UART, filtros y salida DAC

Recibe la señal contaminada `x` del nodo 1 y permite escucharla sin filtro,
con un FIR de la banda protegida o con un notch, mediante un botón o comandos
en el monitor USB.
El nodo 1 genera la señal continuamente en bloques de 512 muestras cada 64 ms;
la computadora solo alimenta las placas por USB, carga el firmware y muestra
diagnósticos. El audio se produce en el DAC del nodo 2 y sale por el parlante.
Valida COBS, CRC-32/ISO-HDLC y cabecera de INPUT y DIAG. UART1 recibe a 921600
baudios, 8N1, con 16 KB de búfer y lecturas de hasta 1024 bytes sin espera.
Al arrancar descarta hasta el primer `0x00`; ignora las tramas vacías.
Por UART2 envía a GPIO17 un FIR_OUT por cada INPUT procesado, con la salida
seleccionada antes de cuantizarla para el DAC y el mismo `first_sample` del INPUT.
La sesión del nodo 2 cambia en cada arranque y la secuencia avanza por paquete.

Cada INPUT válido se procesa y su salida se escribe al DAC continuo de GPIO25: 8 kHz,
APLL y seis búferes DMA de 512 bytes físicos. No hay cola de audio, reintentos ni
temporización por bloques. La conversión es `round(127.5 + 127.5*v)`, limitada a
0–255; una muestra no finita a la entrada del DAC produce 128 sin rechazar el INPUT.
Se requiere `CONFIG_DAC_DMA_AUTO_16BIT_ALIGN=y`, ya presente en la configuración.

Cuando se agota el audio, el DAC mantiene el último valor; el capacitor bloquea
ese nivel constante. Tras 200 ms sin INPUT válido se intenta escribir una sola vez
un bloque de 512 códigos 128, también al arrancar sin emisor. Otro INPUT rearma
el watchdog. Las escrituras usan timeout cero; si quedan incompletas se descarta
el resto, incluido el bloque de silencio. Puede haber clics en las transiciones.
La diferencia entre relojes se acepta en esta versión y se observa en los desbordes.

## Filtro

Conectar un botón entre **GPIO32 y GND**; usa el pull-up interno. Arranca en
`SIN FILTRO` (constante `MODO_INICIAL` en `src/main.cpp`). Cada pulsación avanza
`SIN FILTRO → FIR → NOTCH → SIN FILTRO` e imprime `Filtro: <modo>`.
El botón se lee una vez por INPUT válido y detecta el flanco de 1 a 0, sin
temporizador de antirrebote. Sin INPUT no se atiende el botón; evitar pulsaciones
más cortas que el periodo de un bloque (64 ms).

| Modo | Salida y qué debe oírse |
| --- | --- |
| SIN FILTRO | La señal `x`, con los tres tonos y el pitido de 2150 Hz. |
| FIR | Kaiser de 37 coeficientes. Al arrancar es pasa bajas con corte de 1500 Hz; reduce el pitido y conserva los tonos. Retardo de 18 muestras (2.25 ms). |
| NOTCH | Al arrancar rechaza 2150 Hz con Q = 8.5; reduce el pitido y conserva los tonos. |

Los coeficientes se calculan en `double` al arrancar o al cambiarlos y se guardan
en `float`. Ambos filtros procesan siempre las 512 muestras y conservan sus estados
entre bloques y cambios de modo. Al cambiar los parámetros de un filtro se reinicia
solo su propio estado. Las entradas no finitas se sustituyen por cero solo para los
filtros; en `SIN FILTRO` se conserva la conversión del DAC.
El recorte se hace únicamente al convertir al DAC. Al cambiar puede oírse un clic.

## Comandos desde el monitor

El monitor de **nodo 2** usa el mismo cable USB con el que se programa la placa:
no hace falta ningún cable adicional ni programa aparte. PlatformIO envía cada
tecla y el firmware muestra lo que escribís. Mientras haya un comando a medio
escribir, el resumen periódico se pausa; **Enter** lo ejecuta y el resumen vuelve
aproximadamente un segundo después. Podés corregir con **Backspace**. Tras Enter
aparece el resultado del comando. Los comandos se leen sin espera y se aplican
entre paquetes INPUT completos.

| Comando | Efecto |
| --- | --- |
| `estado` | Muestra modo, banda, notch y todos los coeficientes vigentes. |
| `modo sin`, `modo fir`, `modo notch` | Elige qué se oye por el parlante, igual que el botón. |
| `banda <inf> <sup>` | Recalcula el FIR para la banda protegida en Hz. |
| `notch <f> <q>` | Centra el notch en `f` Hz con factor de calidad `q`. |

`banda` indica qué zona de frecuencias debe conservar el FIR. Por ejemplo,
`banda 100 1200` conserva los tonos útiles y reduce el pitido de 2150 Hz;
`banda 100 3000` deja pasar también ese pitido. `notch` indica una frecuencia
puntual que se quiere atenuar: `notch 2150 8.5` reduce el pitido de 2150 Hz.
Un Q mayor hace el rechazo más estrecho; uno menor afecta una zona más amplia.
Estos comandos ajustan los filtros, pero para escucharlos hay que seleccionar
`modo fir` o `modo notch`, respectivamente.

Se admite `100 ≤ inf < sup ≤ 3000`, `100 ≤ f ≤ 3000` y `0.5 ≤ q ≤ 20`.
Con banda inferior menor que 600 Hz, el FIR es pasa bajas con corte `sup + 300` Hz.
Desde 600 Hz, es pasa banda con cortes `inf - 300` y `sup + 300` Hz.
Un valor fuera de rango o un comando desconocido imprime una línea `Error:` y
no cambia la configuración. Los valores iniciales son banda **100–1200 Hz** y
notch **2150 Hz, Q = 8.5**. Solo se guardan en RAM: al reiniciar vuelven los
valores iniciales.

## Conexiones

- GPIO19 (RX del nodo 2) ← GPIO18 (TX del nodo 1), con GND común.
- GPIO18 del nodo 2 queda configurado como TX, sin conectar.
- GPIO25 → capacitor de 10 µF → entrada del PAM8403, con GND común.
- GPIO4 → resistencia de 220–330 Ω → ánodo del LED; cátodo a GND.
- GPIO32 → botón → GND.
- GPIO17 (TX UART2 del nodo 2) → RXD del YP-05 o RX del nodo 3; GND común.

Para probar con el YP-05: conectarlo a la PC por USB, poner su jumper en 3.3 V
y dejar VCC y TXD sin conectar. GPIO16 (RX UART2) queda sin conectar.

El LED se enciende si hubo errores o pérdidas en los últimos 500 ms, o si no hay
INPUT válido en los últimos 200 ms. Arranca encendido hasta recibir INPUT.

## Compilar, subir y abrir monitor

En PlatformIO, seleccionar el proyecto **nodo2**, entorno **esp32dev**, y usar
Build, Upload y Monitor en el puerto de esta placa. El monitor usa UART0 a 115200.
Desde una terminal ubicada en `proyecto1/firmware/nodo2/`:

```sh
pio run -e esp32dev
pio run -e esp32dev -t upload --upload-port /dev/ttyUSB_NODO2
pio device monitor --port /dev/ttyUSB_NODO2 --baud 115200
```

Reemplazar `/dev/ttyUSB_NODO2` por el puerto real. En VS Code, abrir el monitor
de la placa **nodo2** y escribir los comandos en su terminal.

## Contadores del monitor

Cada resumen empieza con `Filtro: <modo>`. Los contadores se imprimen acumulados
cada aproximadamente un segundo; solo se reinician al reiniciar el nodo 2.

| Campo | Significado |
| --- | --- |
| INPUT / DIAG | Paquetes válidos de cada tipo. |
| err_trama | Más de 2094 bytes sin delimitador después de sincronizar; se descarta hasta el siguiente cero. |
| err_cobs | COBS inválido o datos decodificados que exceden el espacio disponible. |
| err_crc | CRC recibido distinto del calculado. |
| err_cabecera | Paquete demasiado corto para sus campos o cabecera, tipo, formato, canales o tamaños inválidos. |
| perdidos | Paquetes faltantes por salto modular de `sequence`, incluidos INPUT y DIAG, dentro de una sesión. |
| sesiones | Primera sesión recibida y cada cambio posterior de `session_id`; no es un error. |
| DAC … B | Bytes de códigos de 8 bits aceptados por el driver, incluido el silencio del watchdog. |
| desbordes_dac | Escrituras que no aceptaron las 512 muestras completas, incluido el silencio. |
| proc prom / max … us | Tiempo promedio y máximo por INPUT en el último intervalo: convertir las 512 muestras, calcular ambos filtros y entregar el bloque al DAC; 0/0 si no hubo INPUT. Debe quedar por debajo de los 64 000 µs disponibles por bloque. |
| FIR_OUT | Paquetes completos encolados para transmitir por GPIO17 desde el arranque. |
| descartes_tx | Paquetes descartados porque no hubo espacio suficiente en el búfer UART2. |

La primera secuencia recibida de cada sesión establece la referencia, sin inferir
pérdidas anteriores. El seguimiento contempla el retorno de `UINT32_MAX` a cero;
duplicados y secuencias anteriores no suman pérdidas ni retroceden la referencia
(se distinguen saltos hacia delante menores que media vuelta del contador).
`first_sample` no se usa para detectar huecos ni programar audio.

## Prueba entre placas

1. Subir **nodo2** desde la barra de PlatformIO y abrir su monitor en su puerto.
2. En el monitor del nodo 2, escribir `estado` y pulsar Enter. Debe decir
   `SIN FILTRO`, banda 100–1200 Hz, notch 2150 Hz Q 8.5. La línea de arranque
   también muestra el botón GPIO32 y los primeros
   coeficientes FIR aproximadamente `[0.001128111831, 0.002301285580, 0]`,
   notch `b ≈ [0.909373858311, 0.213770873244, 0.909373858311]` y
   `a ≈ [1, 0.213770873244, 0.818747716622]`. Se imprimen los valores almacenados
   en `float`: comparar con tolerancia de `1e-6`, no exigir los doce decimales.
3. Con el nodo 1 encendido y conectado, escuchar la mezcla y el pitido de 2150 Hz.
4. Enviar `modo fir`: el pitido debe bajar. Enviar `banda 100 3000`: el pitido
   vuelve a oírse porque 2150 Hz queda dentro de la banda. Enviar
   `banda 100 1200`: el pitido vuelve a bajar. El monitor imprime los 37
   coeficientes nuevos después de cada cambio.
5. Enviar `modo notch` y luego `notch 1100 1`: el pitido de 2150 Hz vuelve
   y se pierde el tono útil de 1100 Hz. Enviar `notch 2150 8.5`: el pitido baja.
   `estado` debe mostrar los valores restaurados y los coeficientes actuales.
6. Probar `modo sin`, `modo fir`, `modo notch` y el botón GPIO32: cada cambio
   debe reflejarse en `Filtro: <modo>`. Al cambiar puede oírse un clic.
7. Enviar `banda 100 3500` y `notch 2150 0`: cada uno debe imprimir un error;
   `estado` debe conservar los valores válidos anteriores.
8. Comprobar los contadores en los tres modos:
   INPUT y DIAG deben aumentar unos 15–16 por segundo (~15.6 INPUT/s), con todos
   los errores, `perdidos` y `desbordes_dac` en cero y LED apagado.
9. Desconectar el cable de GPIO19: el LED se enciende al cumplirse 200 ms sin INPUT
   y el watchdog escribe silencio una vez. El audio deja de sonar; comprobar si
   hay clics de transición. Al reconectar debe recuperarse automáticamente.
   Pueden aumentar pérdidas y errores si se corta o recupera una trama a medias.
10. Presionar EN en el nodo 1: debe aumentar `sesiones` y continuar la recepción
   sin pérdidas atribuidas al reinicio de secuencia. Con el enlace en reposo no
   deberían aparecer errores; un reinicio en plena trama puede dejar un error
   de trama truncada antes de recuperar la sincronización.
11. Con el nodo 1 enviando, observar `proc prom` y `max` durante unos segundos en
    `modo sin`, `modo fir` y `modo notch`. Anotar los valores para el informe;
    deben quedar por debajo de 64 000 us por bloque. Sin INPUT se muestra 0/0.

Medición recibida del monitor, con el nodo 1 enviando (paso 3c):

| Modo | `proc prom` observado | Mayor `max` observado |
| --- | --- | --- |
| SIN FILTRO | 4824 us | 4844 us |
| FIR | 4830–4831 us | 4851 us |
| NOTCH | 4815–4817 us | 4842 us |

El peor bloque observado tardó 4851 us, alrededor del 7.6 % de los 64 000 us
disponibles. INPUT avanzó unas 15–16 veces por segundo; `err_trama`, `err_cobs`,
`err_crc`, `err_cabecera`, `perdidos` y `desbordes_dac` permanecieron en cero.
Los tiempos de los tres modos son parecidos porque ambos filtros se calculan
para cada INPUT y el modo solo elige cuál salida se entrega al DAC.

## Prueba de FIR_OUT con YP-05

Con nodo 1, nodo 2 y YP-05 conectados por sus respectivos USB, identificar el
puerto real del YP-05 conectándolo de último y comparando la salida de
`python3 -m serial.tools.list_ports -v` antes y después. Linux suele asignarle
un nombre como `/dev/ttyUSB0` o `/dev/ttyUSB1`.
Subir este firmware **solo al nodo 2**. El YP-05 recibe por RXD desde GPIO17;
su VCC y TXD quedan libres. Desde la raíz del repositorio, con las dependencias
de `herramientas_pc/` instaladas, ejecutar:

```sh
python3 proyecto1/herramientas_pc/receptor_nodo1.py --puerto /dev/ttyUSB1 --enlace n2out --segundos 60
```

Cambiar `/dev/ttyUSB1` por el puerto real del YP-05. No usar el puerto USB del
nodo 2, que se reserva para su monitor serie. La captura debe terminar
con `RESULTADO: OK`, alrededor de 15–16 FIR_OUT por segundo, sin errores ni
paquetes perdidos. En el monitor USB propio del nodo 2, `FIR_OUT` debe aumentar
y `descartes_tx` permanecer en cero. Durante otra captura, pulsar EN del nodo 2:
el validador debe registrar una sesión nueva sin pérdidas. `FIR_OUT` es el nombre
del tipo de paquete incluso en `SIN FILTRO` o `NOTCH`: sus muestras son las de
la salida seleccionada en ese momento.

Captura reportada el 3 nov 2026: 937 FIR_OUT válidos en 60 s (15.62/s), una
sesión, cero errores, cero paquetes perdidos y `RESULTADO: OK`. Queda por probar
el reinicio con EN durante una captura para confirmar el cambio de sesión.
