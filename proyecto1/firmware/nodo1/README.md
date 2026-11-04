# Nodo 1: emisor

Emisor del nodo 1. Cada 64 ms obtiene un bloque de 512 muestras por canal a 8 kHz,
desde los generadores o desde la entrada ADC estéreo, y lo envía por UART.

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

Esta salida y su botón se usan solo en modo GENERADOR. En modo ADC se desactivan
porque el DAC continuo y el ADC continuo comparten I2S0; se escucha por el nodo 2.

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

## Entrada ADC estéreo y referencia

`FUENTE_ENTRADA` en `src/main.cpp` selecciona ADC o GENERADOR. En ADC:

- x: GPIO36 (ADC1 canal 0), jack patita 5 = L.
- s: GPIO39/VN (ADC1 canal 3), jack patita 1 = R.
- Jack patita 3 = GND, común con el nodo 1.

Cada entrada usa capacitor de 10 µF, divisor de 1.5 kΩ / 1 kΩ y una mitad del
LM358 como Sallen-Key. La PC reproduce WAV estéreo: L = x y R = referencia s.
ADC1 convierte alternadamente x–s a 48 kHz totales, 24 kHz por canal, con
12 bits y 12 dB. La tabla raw → mV se calcula al arrancar con la calibración
de ESP-IDF: 4096 valores int16_t (8 KB) si caben; de lo contrario int32_t (16 KB).
No se llama al calibrador por muestra durante la adquisición.

s se mide 20.83 µs después de x. Antes del FIR, se compensa con
`s_alineada[n] = (s[n-1] + s[n]) / 2`, inicializando la anterior con la primera s.
Esto retrasa s media muestra a 24 kHz y deja una ganancia `cos(pi*f/24000)`:
aproximadamente −0.04 dB a 700 Hz y −0.7 dB a 3 kHz. x no se compensa.
Cada canal conserva su propio FIR de decimación /3 y pasa altos de 10 Hz;
ambos usan escala de 1200 mV y entregan 512 muestras alineadas lógicamente.
Las diferencias de ganancia, offset y **fase** entre ambos Sallen-Key, por las
tolerancias de resistencias y sobre todo capacitores, no se corrigen en el
firmware: se miden con P1 y se documentan.

UART1 conserva INPUT + DIAG. UART2 envía INPUT_REF + DIAG, con
`x[0], s[0], x[1], s[1], …` y el mismo `first_sample`. El diagnóstico usa solo x.
Las desalineaciones se cuentan sin descartar bloques ni reiniciar estados;
un desborde del pool o una desalineación nuevos marcan discontinuidad (0x0010)
en los paquetes del siguiente bloque informado. `first_sample` avanza 512.
Un número par de resultados perdidos puede mantener la alternancia; el contador
de desbordes indica el evento, no la cantidad exacta de muestras omitidas.

**Si el anillo del jack (patita 1) está desconectado, s llega en silencio y las
métricas del nodo 3 que usan la referencia (MSE, SNR) no son válidas.** La bandera
0x0001 indica que se transmite el canal de referencia, no que se verificó su calidad.

`vista diag` muestra rangos de x y s en mV. `vista todo` añade crudos, frecuencias
por canal, desalineaciones, desbordes y tiempos. Los tiempos de calibración del
lazo incluyen la consulta de tabla, estadísticas y ensamblado; filtrado incluye
la compensación de s, FIR, pasa altos y normalización de los dos canales.
La configuración del proyecto selecciona −O2 y CPU de 240 MHz.

## Problemas conocidos

- **Subida lenta:** `upload_speed = 115200` en `platformio.ini`. A velocidades mayores la subida falló con esta placa.
- **Falla un include de ESP-DSP** (por ejemplo `dsps_fft2r.h`) después de cambiar dependencias: `pio run -t fullclean` y volver a compilar.
- **Basura en el monitor con el YP-05 conectado:** PlatformIO puede abrir el puerto equivocado. Indica el puerto con `-p /dev/ttyUSB0`.

## Prueba de lazo

`PRUEBA_LAZO` en `src/main.cpp` vale `false` por defecto. Con `true`, se puentea GPIO18→GPIO19 y GPIO17→GPIO16, y la placa compara lo enviado con lo recibido.

## Validación

Con [receptor_nodo1.py](../../herramientas_pc/README.md), que recibe cada enlace en la PC y valida los paquetes.
