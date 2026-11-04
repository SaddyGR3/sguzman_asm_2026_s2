# Nodo 1: emisor

Adquiere audio del micrófono MAX4466 por un canal ADC. Cada 64 ms completa
512 muestras a 8 kHz y envía INPUT + DIAG por UART1, TX GPIO18, hacia la
placa que integra los nodos 2 y 3. UART0 (USB) se usa para la consola.

## Qué hace

- **Entrada predeterminada:** micrófono por GPIO36 (ADC1 canal 0), a 24 kHz,
  12 bits y 12 dB. El ritmo lo marca la adquisición ADC, sin temporizador.
- **Procesamiento:** tabla raw → mV, FIR de 37 coeficientes con decimación ÷3
  a 8 kHz, pasa altos de 10 Hz y normalización con escala de 1200 mV.
- **Diagnóstico:** FFT de 1024 muestras, salto de 512, detección tonal fuera
  de la banda protegida y persistencia.
- **Salida única:** INPUT + DIAG por UART1 a 921600 baudios, 8N1, con destino
  lógico nodo 2. La cabecera tiene 32 B; se usan CRC-32, COBS y delimitador 0x00.
- **Arranque:** comprueba CRC y COBS, imprime la cabecera INPUT y escribe un
  0x00 inicial en UART1 para resincronizar el receptor tras reiniciar.

El formato de los paquetes está en [contrato_nodos.md](../../documentos/contrato_nodos.md).
Las rutas históricas del contrato no representan el cableado actual: el nodo 1
solo transmite hacia la placa conjunta por UART1.

## Entrada por micrófono

Conexiones del MAX4466:

- VCC a 3.3 V.
- GND al pin G de la placa.
- OUT a la pata − del capacitor de 10 µF de x.

Cadena de entrada: MAX4466 → capacitor de 10 µF de x → divisor de 1.32 V
→ Sallen-Key (mitad A del LM358) → GPIO36.

ADC1 usa un solo patrón a 24000 Hz, un pool de 16384 B y tramas DMA de
1024 B. Cada bloque consume 1536 muestras crudas y entrega 512 muestras de x.
El FIR, la fase de decimación y el pasa altos conservan su estado entre bloques.

La tabla raw → mV se calcula al arrancar con la calibración de ESP-IDF:
4096 valores int16_t (8192 B) si caben; de lo contrario, int32_t (16384 B).
Se aprovecha la calibración eFuse cuando está disponible; si falta, se informa
el uso de Vref por defecto. Durante la adquisición solo se consulta la tabla.
La configuración del proyecto conserva −O2 y CPU de 240 MHz.

**Lección de montaje:** los equipos externos (YP-05 y otras placas) se conectan
al **pin G de la placa**, nunca al carril de GND de la protoboard del circuito
analógico.

## Generador de respaldo

El generador permite continuar si falla la captura por micrófono y probar la
placa de los nodos 2 y 3 sin señal acústica. Para activarlo, cambiar
`FUENTE_ENTRADA` de `Fuente::ADC` a `Fuente::GENERADOR` en `src/main.cpp`
y volver a compilar. El valor predeterminado es `Fuente::ADC`.

Genera x = s + i: s contiene tonos de 300, 700 y 1100 Hz; i contiene un tono
de 2150 Hz. Los arreglos s e i solo se usan para formar x. En este modo,
un temporizador de 64 ms marca el ritmo. La salida sigue siendo únicamente
INPUT + DIAG por UART1.

## Consola y contadores

Comandos por UART0 a 115200 baudios:

- `banda <lo> <hi>`: cambia la banda protegida; inicialmente 100–1200 Hz.
- `estado`: muestra la banda, la vista y el diagnóstico actual.
- `vista diag`: resumen compacto, con `ADC x <min>-<max> mV` solo en modo ADC.
- `vista todo`: diagnóstico detallado, periodos, procesamiento, empaquetado,
  tamaños de paquetes, pila libre y estadísticas TX de UART1. En ADC también
  muestra crudos, mV, frecuencias, desbordes del pool, saturaciones y tiempos.

Los resúmenes se imprimen cada 16 bloques, aproximadamente cada 1.024 s.
`procesamiento max` excluye la espera de adquisición ADC. El tiempo de
calibración incluye la extracción, consulta de tabla y estadísticas; el tiempo
de filtrado incluye FIR, pasa altos y normalización. El análisis se mide aparte.

`overruns` es la suma acumulada de bloques atrasados del temporizador (solo
GENERADOR) y descartes TX de UART1 (ambos modos). Cada descarte TX cuenta una
pareja INPUT + DIAG que no se pudo encolar completa, sin reintento. Se informa
en el siguiente DIAG que logre transmitirse; la consola muestra también el
contador específico de descartes TX.

En ADC, DIAG informa además los desbordes del pool y las saturaciones acumuladas.
La bandera de discontinuidad (0x0010) se activa solo cuando aumenta el contador
de desbordes del pool; este cuenta eventos, no la cantidad exacta de muestras
perdidas. `first_sample` avanza 512 por bloque. Se conservan las banderas de
calentamiento (0x0002), reinicio (0x0004) y ventana parcial (0x0020).

## Requisitos

VS Code con la extensión PlatformIO. El proyecto usa `framework = espidf`
(ESP-IDF) y ESP-DSP, declarado en `src/idf_component.yml`.

## Compilar, subir y monitor

Desde `proyecto1/firmware/nodo1/`:

```sh
pio run
pio run -t upload
pio device monitor -p /dev/ttyUSB0 -b 115200
```

O con los botones de PlatformIO en VS Code.

## Validación

Recibir UART1 con [receptor_nodo1.py](../../herramientas_pc/README.md), usando
`--enlace n2 --solo-protocolo` y el puerto del adaptador, o conectar directamente
la placa de los nodos 2 y 3. Verificar INPUT + DIAG sin errores en ambos modos.

En ADC, comprobar en reposo x alrededor de 1340 mV, frecuencias próximas a
24000 Hz y 8000 Hz, y cero desbordes del pool. Reproducir un tono fuera de la
banda protegida (por ejemplo, 2150 Hz) o P1 desde el parlante de la laptop hacia
el micrófono y verificar detección tras calentamiento y persistencia. Revisar
los tiempos y contadores con `vista todo`.

## Problemas conocidos

- **Subida lenta:** `upload_speed = 115200` en `platformio.ini`. A velocidades
  mayores la subida falló con esta placa.
- **Falla un include de ESP-DSP** (por ejemplo `dsps_fft2r.h`) después de cambiar
  dependencias: `pio run -t fullclean` y volver a compilar.
- **Basura en el monitor con el YP-05 conectado:** PlatformIO puede abrir el
  puerto equivocado. Indicar el puerto con `-p /dev/ttyUSB0`.
