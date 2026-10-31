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

## Problemas conocidos

- **Subida lenta:** `upload_speed = 115200` en `platformio.ini`. A velocidades mayores la subida falló con esta placa.
- **Falla un include de ESP-DSP** (por ejemplo `dsps_fft2r.h`) después de cambiar dependencias: `pio run -t fullclean` y volver a compilar.
- **Basura en el monitor con el YP-05 conectado:** PlatformIO puede abrir el puerto equivocado. Indica el puerto con `-p /dev/ttyUSB0`.

## Prueba de lazo

`PRUEBA_LAZO` en `src/main.cpp` vale `false` por defecto. Con `true`, se puentea GPIO18→GPIO19 y GPIO17→GPIO16, y la placa compara lo enviado con lo recibido.

## Validación

Con [receptor_nodo1.py](../../herramientas_pc/README.md), que recibe cada enlace en la PC y valida los paquetes.
