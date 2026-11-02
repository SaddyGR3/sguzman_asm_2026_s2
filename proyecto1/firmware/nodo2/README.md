# Nodo 2: receptor UART y salida DAC

En este paso reproduce directamente la señal contaminada `x` del nodo 1, sin filtro.
Valida COBS, CRC-32/ISO-HDLC y cabecera de INPUT y DIAG. UART1 recibe a 921600
baudios, 8N1, con 16 KB de búfer y lecturas de hasta 1024 bytes sin espera.
Al arrancar descarta hasta el primer `0x00`; ignora las tramas vacías.

Cada INPUT válido se escribe inmediatamente al DAC continuo de GPIO25: 8 kHz,
APLL y seis búferes DMA de 512 bytes físicos. No hay cola de audio, reintentos ni
temporización por bloques. La conversión es `round(127.5 + 127.5*v)`, limitada a
0–255; NaN e infinitos producen 128 sin rechazar el INPUT.
Se requiere `CONFIG_DAC_DMA_AUTO_16BIT_ALIGN=y`, ya presente en la configuración.

Cuando se agota el audio, el DAC mantiene el último valor; el capacitor bloquea
ese nivel constante. Tras 200 ms sin INPUT válido se intenta escribir una sola vez
un bloque de 512 códigos 128, también al arrancar sin emisor. Otro INPUT rearma
el watchdog. Las escrituras usan timeout cero; si quedan incompletas se descarta
el resto, incluido el bloque de silencio. Puede haber clics en las transiciones.
La diferencia entre relojes se acepta en esta versión y se observa en los desbordes.

## Conexiones

- GPIO19 (RX del nodo 2) ← GPIO18 (TX del nodo 1), con GND común.
- GPIO18 del nodo 2 queda configurado como TX, sin conectar.
- GPIO25 → capacitor de 10 µF → entrada del PAM8403, con GND común.
- GPIO4 → resistencia de 220–330 Ω → ánodo del LED; cátodo a GND.

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

Reemplazar `/dev/ttyUSB_NODO2` por el puerto real. Estos comandos son instrucciones
para la prueba; no se ejecutaron durante la implementación.

## Contadores del monitor

Se imprimen acumulados cada aproximadamente un segundo; solo se reinician al
reiniciar el nodo 2.

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

La primera secuencia recibida de cada sesión establece la referencia, sin inferir
pérdidas anteriores. El seguimiento contempla el retorno de `UINT32_MAX` a cero;
duplicados y secuencias anteriores no suman pérdidas ni retroceden la referencia
(se distinguen saltos hacia delante menores que media vuelta del contador).
`first_sample` no se usa para detectar huecos ni programar audio.

## Prueba entre placas

1. Subir **nodo2** desde la barra de PlatformIO y abrir su monitor en su puerto.
2. Con el nodo 1 encendido y conectado, escuchar la mezcla y el pitido de 2150 Hz.
   INPUT y DIAG deben aumentar unos 15–16 por segundo (~15.6 INPUT/s), con todos
   los errores, `perdidos` y `desbordes_dac` en cero y LED apagado.
3. Desconectar el cable de GPIO19: el LED se enciende al cumplirse 200 ms sin INPUT
   y el watchdog escribe silencio una vez. El audio deja de sonar; comprobar si
   hay clics de transición. Al reconectar debe recuperarse automáticamente.
   Pueden aumentar pérdidas y errores si se corta o recupera una trama a medias.
4. Presionar EN en el nodo 1: debe aumentar `sesiones` y continuar la recepción
   sin pérdidas atribuidas al reinicio de secuencia. Con el enlace en reposo no
   deberían aparecer errores; un reinicio en plena trama puede dejar un error
   de trama truncada antes de recuperar la sincronización.
