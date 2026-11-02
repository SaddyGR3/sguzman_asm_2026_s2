# Nodo 1: emisor

Emisor del nodo 1 para el avance. Cada 64 ms genera un bloque de 512 muestras a 8 kHz y lo envía por UART.

## Qué hace

- **Señal:** la señal útil s son tonos de 300, 700 y 1100 Hz, y la interferencia está en 2150 Hz. Envía x = s + interferencia.
- **Paquete:** cabecera de 32 B, datos en float32, CRC-32, COBS y delimitador 0x00.
- **Envío**, a 921 600 baudios, 8N1:
  - UART1, TX en GPIO18, hacia el nodo 2: INPUT + DIAG.
  - UART2, TX en GPIO17, hacia el nodo 3: INPUT_REF (x y s intercalados) + DIAG.
- **UART0 (USB):** queda solo para la consola.
- **Arranque:** escribe un 0x00 en cada UART para que el receptor se resincronice tras un reinicio.

El formato completo está en [contrato_nodos.md](../../documentos/contrato_nodos.md).

## Requisitos

VS Code con la extensión PlatformIO. El proyecto usa `framework = espidf` (ESP-IDF) y ESP-DSP, que PlatformIO descarga solo la primera vez (declarado en `src/idf_component.yml`).

## Compilar, subir y monitor

Desde `proyecto1/firmware/nodo1/`:

```
pio run
pio run -t upload
pio device monitor -p /dev/ttyUSB0 -b 115200
```

O con los botones de PlatformIO en VS Code.

## Salida por DAC

En `src/main.cpp`, `SALIDA_DAC = true` habilita GPIO25 (DAC canal 0) a 8 kHz
con reloj APLL y seis búferes DMA de 512 bytes. Al arrancar, el firmware informa
qué señal está activa. El estado inicial es `DAC_SENAL_LIMPIA_INICIAL = false`:
saca `x`, con la interferencia de 2150 Hz; la señal limpia `s_util` contiene
solo los tonos de 300, 700 y 1100 Hz.

Conecta un botón entre GPIO32 y GND. Cada pulsación alterna la salida entre `x`
y `s`; el monitor indica el cambio como `DAC: señal contaminada (x)` o
`DAC: señal limpia (s)`.

Montaje: GPIO25 → capacitor de 10 µF → entrada del PAM8403 con perilla de volumen
→ parlante. Une las masas del ESP32 y del amplificador. Empieza con la perilla
al mínimo y sube poco a poco.

Con `DAC_SENAL_LIMPIA = false` se oye la mezcla de tonos con un pitido agudo
de 2150 Hz; con `true` el pitido desaparece. Un siseo agudo de fondo es normal:
falta el filtro de reconstrucción.

El resumen muestra `DAC` (bytes de 8 bits aceptados, acumulados) y
`desbordes_dac` (bloques que no entraron completos). La escritura no espera
espacio DMA y descarta el resto si no cabe. Comprueba que `desbordes_dac`
permanezca en 0 (o casi 0) y `overruns` en 0.

## Problemas conocidos

- **Subida lenta:** `upload_speed = 115200` en `platformio.ini`. A velocidades mayores la subida falló con esta placa.
- **Falla un include de ESP-DSP** (por ejemplo `dsps_fft2r.h`) después de cambiar dependencias: `pio run -t fullclean` y volver a compilar.
- **Basura en el monitor con el YP-05 conectado:** PlatformIO puede abrir el puerto equivocado. Indica el puerto con `-p /dev/ttyUSB0`.

## Prueba de lazo

`PRUEBA_LAZO` en `src/main.cpp` vale `false` por defecto. Con `true`, se puentea GPIO18→GPIO19 y GPIO17→GPIO16, y la placa compara lo enviado con lo recibido.

## Validación

Con [receptor_nodo1.py](../../herramientas_pc/README.md), que recibe cada enlace en la PC y valida los paquetes.
