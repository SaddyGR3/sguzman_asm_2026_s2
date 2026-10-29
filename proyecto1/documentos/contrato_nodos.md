# Contrato entre nodos — Proyecto Grupal 1

**CE1110 Análisis de Señales Mixtas — Sistema distribuido de reducción adaptativa de ruido en tiempo real**

Referencia técnica común para cualquier tarea del proyecto. Todo nodo, script de prueba o simulación debe respetar este documento. Si algo necesita cambiar, se cambia aquí primero y se avisa al grupo.

**Versión 3.1 (27 oct):** agrega el 0x00 inicial al arrancar (sección 4) y el manejo del cambio de sesión en el receptor (sección 9). Ajuste del 28 oct: rechazo del FIR pasa bajas del nodo 2 a ≥ 45 dB y Q automática del notch = 8.5 (sección 7), según lo verificado en la simulación. **Versión 3 (25 oct).** Incorpora el plan de frecuencias y pruebas cerrado (P1–P6): banda protegida, campos nuevos de DIAG y CONTROL, N configurable y FIR del nodo 2 calculado en la placa. El protocolo se alinea con lo definido en la Tarea 1 (`proyecto1/tarea1/seccion_2_5/docs/2_5_arquitectura_comunicacion.md` y `proyecto1/tarea1/revision/paso_9/calcular_comunicacion.py`). Ante cualquier diferencia, **rige la Tarea 1**.

- **[Tarea 1]:** definido en la Tarea 1; se respeta tal cual.
- **[Aprobado]:** decidido por el grupo después de la Tarea 1.
- **[Propuesta]:** nuevo, pendiente de aprobación antes de programarlo.
- **[Pendiente]:** se define junto con las pruebas P1–P5.

---

## 1. Parámetros del sistema

| Parámetro | Valor | Origen |
|---|---|---|
| Frecuencia de muestreo fs | 8000 Hz | [Tarea 1] |
| Tamaño de FFT N | 1024 muestras (Δf = 7.8125 Hz) | [Tarea 1] |
| Avance (hop) | 512 muestras (50 % de solape), un bloque cada 64 ms | [Tarea 1] |
| Ventana espectral | raíz de Hann periódica, en análisis y en síntesis | [Tarea 1] |
| Formato numérico interno y de transporte | float32 (IEEE 754), señal normalizada en [−1, 1) | [Tarea 1] |
| Retardo del FIR del nodo 2 | 18 muestras (2.25 ms), fijo con cualquier banda protegida | [Tarea 1] |
| Retardo de reproducción objetivo | 256 ms (cuatro avances) | [Tarea 1] |
| Banda del sistema | 100–3000 Hz | [Aprobado] |
| Filtros analógicos (anti-aliasing y reconstrucción) | Sallen-Key Butterworth, fc ≈ 3.4 kHz (ver guía de hardware) | [Aprobado] |
| Entorno de firmware | PlatformIO, `framework = espidf`, C++, biblioteca ESP-DSP | [Aprobado] |
| Generador de tonos del emisor | tabla de seno de 1024 valores con acumulador de fase de 32 bits | [Aprobado] |
| Muestreo del ADC (nodo 1) | modo continuo a 24 kHz; FIR de decimación (paso hasta 3 kHz, rechazo desde 5 kHz, 40–50 dB) y se toma 1 de cada 3 muestras para obtener 8 kHz. El modo continuo del ESP32 no baja de 20 kHz y ocupa el I2S0 | [Aprobado] |

**Banda protegida** [Aprobado]: dónde está la señal útil en cada prueba; es distinta de la banda del sistema. Por defecto 100–3000 Hz. Se configura en la consola del nodo 1, que la reenvía a los nodos 2 y 3 en CONTROL CONFIG (sección 6); así los tres nodos no pueden quedar con bandas distintas.

**Tamaño de análisis N** [Aprobado]: configurable en 256, 512 o 1024 (por defecto 1024), con H = N/2, mediante los campos N y H de CONTROL y DIAG. El transporte no cambia: `sample_count` sigue fijo en 512 y el análisis parte cada lote de 512 en sub-bloques de N/2. N = 1024 es el máximo configurado en ESP-DSP.

### Conversión ADC y DAC [Aprobado]

- **ADC (nodo 1, 12 bits):** atenuación de 12 dB (mide de 150 a 2450 mV). Cada muestra se convierte a voltaje con la calibración de ESP-IDF y se normaliza respecto al centro de la entrada: `x = (v − 1.32 V) / 1.25 V`. Así el pico de 0.8 corresponde a 0.32–2.32 V. Antes de normalizar se resta el nivel DC estimado.
- **DAC (nodos 2 y 3, 8 bits):** `código = redondear(127.5 + 127.5·y)`, limitado a 0–255. Cada vez que se limita se suma 1 al contador de saturaciones. Con |y| ≤ 0.8 la salida queda entre 0.33 y 2.97 V, dentro del rango del LM358 a 5 V.

---

## 2. Pines de cada placa [Aprobado]

| Función | Nodo 1 | Nodo 2 | Nodo 3 |
|---|---|---|---|
| UART0 (USB, consola) | GPIO1 / GPIO3 | GPIO1 / GPIO3 | GPIO1 / GPIO3 |
| UART1 TX / RX | GPIO18 / GPIO19 | GPIO18 / GPIO19 | GPIO18 / GPIO19 |
| UART2 TX / RX | GPIO17 / GPIO16 | GPIO17 / GPIO16 | GPIO17 / GPIO16 |
| ADC señal contaminada x | GPIO34 | — | — |
| ADC referencia s (opcional) | GPIO35 | — | — |
| DAC salida de audio | — | GPIO25 | GPIO25 |
| LCD I2C SDA / SCL | — | — | GPIO21 / GPIO22 |
| LED de error (pérdida o CRC) | GPIO4 | GPIO4 | GPIO4 |
| LED RGB (método activo) | — | — | GPIO13 / GPIO14 / GPIO27 |
| Botones | — | — | GPIO32 / GPIO33 (pull-up interno) |

**No usar:** GPIO6–11 (flash), GPIO0, 2, 12 y 15 (arranque). No conectar nada a la UART0. La UART1 se reasigna a GPIO18/19 porque sus pines por defecto están conectados a la flash.

---

## 3. Enlaces entre nodos [Tarea 1]

921600 baudios, 8N1, full duplex, TX cruzado a RX, tierra común y lógica de 3.3 V. Los tres enlaces funcionan en paralelo (no son un bus compartido).

| Enlace | Puertos | Cables | Sentido principal | Retorno |
|---|---|---|---|---|
| N1 ↔ N2 | UART1 de N1 ↔ UART1 de N2 | N1 GPIO18 → N2 GPIO19 · N2 GPIO18 → N1 GPIO19 | x y DIAG | estado y control |
| N1 ↔ N3 | UART2 de N1 ↔ UART1 de N3 | N1 GPIO17 → N3 GPIO19 · N3 GPIO18 → N1 GPIO16 | x, s opcional y DIAG | control y estado |
| N2 ↔ N3 | UART2 de N2 ↔ UART2 de N3 | N2 GPIO17 → N3 GPIO16 · N3 GPIO17 → N2 GPIO16 | salida FIR | control y estado |
| Tierra | — | GND de las tres placas unidos | — | — |

N1 encola las copias de x en ambas UART sin esperar a que termine una transmisión para iniciar la otra. El DIAG se envía después del lote de datos.

| Sentido | Bytes máximos por avance | Baudios mínimos | Ocupación a 921600 |
|---|---|---|---|
| N1→N2: INPUT + DIAG | 2196 | 343 125 | 37.23 % |
| N1→N3 con s: INPUT_REF + DIAG | 4252 | 664 375 | 72.09 % |
| N1→N3 sin s: INPUT + DIAG | 2196 | 343 125 | 37.23 % |
| N2→N3: FIR_OUT | 2094 | 327 188 | 35.50 % |

Se reservan hasta 10 CONTROL por segundo y por sentido (7000 baudios promedio); el enlace más exigente llega a 671 375 baudios (72.85 %). 115 200 baudios no alcanza.

---

## 4. Formato del paquete [Tarea 1]

```
[ cabecera 32 B | datos | CRC-32 4 B ]  →  codificación COBS  →  byte 0x00 delimitador
```

- **CRC-32/ISO-HDLC:** polinomio 0x04C11DB7 (reflejado 0xEDB88320), refin/refout verdaderos, init y xorout 0xFFFFFFFF. Se calcula sobre cabecera + datos antes de COBS y se transmite little-endian. Prueba: `"123456789"` → `0xCBF43926` (equivale a `zlib.crc32`).
- **COBS:** elimina los ceros internos para que 0x00 marque el fin de cada paquete. Vector de prueba: `11 00 22` → `02 11 02 22`.
- **Orden de bytes:** todos los campos en little-endian. No se envía una estructura C con su relleno: cada campo se serializa explícitamente.
- **Tamaño máximo tras COBS:** R + ⌊R/254⌋ + 2 bytes (R = cabecera + datos + CRC). Ningún paquete supera 4150 bytes en el cable.
- **0x00 inicial al arrancar** [Aprobado, 27 oct]: cada nodo emisor, al arrancar y antes de su primer paquete, escribe un único byte 0x00 en cada UART de enlace. Si el nodo se reinició mientras enviaba un paquete, ese 0x00 cierra los restos del paquete cortado, y el primer paquete de la sesión nueva (secuencia 0, bandera de reinicio) llega limpio. Los receptores ignoran las tramas vacías (dos 0x00 seguidos).
- **Referencia en Python:** `HEADER = struct.Struct("<HBBBBHIIQHBBI")` en `calcular_comunicacion.py`.

### Cabecera (32 bytes)

| Offset | Campo | Tipo | Significado |
|---|---|---|---|
| 0 | magic | uint16 | **0x5341**; en el cable, bytes `41 53` |
| 2 | version | uint8 | 1 |
| 3 | type | uint8 | 1 INPUT, 2 INPUT_REF, 3 FIR_OUT, 4 DIAG, 5 CONTROL |
| 4 | src | uint8 | nodo emisor: 1, 2 o 3 |
| 5 | dst | uint8 | nodo receptor: 1, 2 o 3 |
| 6 | flags | uint16 | ver tabla de banderas |
| 8 | session_id | uint32 | identificador común del ensayo; cambia al reiniciar |
| 12 | sequence | uint32 | contador de paquetes por sentido de enlace, módulo 2³² |
| 16 | first_sample | uint64 | índice de la primera muestra del bloque o de la ventana asociada |
| 24 | sample_count | uint16 | 512 en paquetes con muestras; 0 en los demás |
| 26 | format | uint8 | 1 float32; 0 metadatos |
| 27 | channels | uint8 | 1 para x o y; 2 para x y s intercalados; 0 metadatos |
| 28 | payload_bytes | uint32 | longitud de datos, a validar antes de copiar |

En las pruebas con la PC, la PC usa el número del nodo al que imita.

### Tipos de mensaje

| Código | Nombre | Datos | Sentido |
|---|---|---|---|
| 1 | INPUT | 512 × float32 = 2048 B | N1 → N2, N1 → N3 sin referencia |
| 2 | INPUT_REF | 512 × 2 × float32 = 4096 B, intercalados `x[0], s[0], x[1], s[1], …` | N1 → N3 con referencia |
| 3 | FIR_OUT | 512 × float32 = 2048 B, índices de la salida causal | N2 → N3 |
| 4 | DIAG | 64 B | N1 → N2, N1 → N3 |
| 5 | CONTROL | 32 B | en ambos sentidos |

Ambas rutas reciben exactamente los mismos bytes float32 de x. El retardo de 18 muestras del FIR se interpreta desde la configuración, no se corrige en los índices.

### Banderas

| Valor | Significado |
|---|---|
| 0x0001 | referencia válida |
| 0x0002 | calentamiento (el estimador todavía no tiene suficiente historial) |
| 0x0004 | reinicio |
| 0x0008 | saturación |
| 0x0010 | discontinuidad |
| 0x0020 | ventana inicial parcial |

### Tamaños por paquete

| Paquete | Datos | Cabecera + datos + CRC | Máximo en el cable |
|---|---|---|---|
| INPUT o FIR_OUT | 2048 B | 2084 B | 2094 B |
| INPUT_REF | 4096 B | 4132 B | 4150 B |
| DIAG | 64 B | 100 B | 102 B |
| CONTROL | 32 B | 68 B | 70 B |

---

## 5. Paquete DIAG (64 bytes) [Tarea 1 + Aprobado]

| Offset | Campo | Tipo | Significado |
|---|---|---|---|
| 0 | fs | uint32 | Hz |
| 4 | N | uint16 | tamaño de FFT vigente |
| 6 | H | uint16 | avance vigente (N/2) |
| 8 | metodo | uint8 | método sugerido para el nodo 3: 0 pasa todo, 1 picos, 2 resta, 3 top-k |
| 9 | calentamiento | uint8 | estado de calentamiento del estimador |
| 10 | tipo_ruido | uint8 | tipo de ruido detectado, códigos 0–5 de la sección 7 [Aprobado; en la Tarea 1 era reservado] |
| 11 | filtro_n2 | uint8 | filtro sugerido para el nodo 2: 0 pasa todo, 1 FIR de la banda protegida, 2 notch, 3 peine [Aprobado; en la Tarea 1 era reservado] |
| 12 | pico_Hz | float32 | frecuencia del pico dominante; −1.0 si no hay |
| 16 | banda_lo | float32 | inicio de banda de ruido; −1.0 si no hay |
| 20 | banda_hi | float32 | fin de banda de ruido; −1.0 si no hay |
| 24 | piso_resumen | float32 | RMS de las magnitudes del piso estimado (unidades de la FFT sin normalizar) |
| 28 | DC | float32 | nivel DC estimado |
| 32 | energia | float32 | energía de entrada del bloque |
| 36 | tiempo_us | uint32 | tiempo de análisis en µs |
| 40 | overruns | uint32 | desbordamientos de búfer, acumulado |
| 44 | perdidas | uint32 | bloques perdidos, acumulado |
| 48 | saturaciones | uint32 | muestras saturadas, acumulado |
| 52 | inicio_ventana | uint64 | índice de inicio de la ventana analizada |
| 60 | config_id | uint32 | configuración vigente |

Valores ausentes: −1.0 con un estado explícito, nunca valores no finitos. La banda protegida no va en el DIAG: es configuración, no diagnóstico (ver sección 6).

---

## 6. Paquete CONTROL (32 bytes) [Tarea 1 + Aprobado]

| Offset | Campo | Tipo | Significado |
|---|---|---|---|
| 0 | fs | uint32 | Hz |
| 4 | N | uint16 | tamaño de FFT: 256, 512 o 1024 |
| 6 | H | uint16 | avance: N/2 |
| 8 | metodo | uint8 | método |
| 9 | opcode | uint8 | 1 CONFIG, 2 START, 3 STOP, 4 STATUS, 5 ACK |
| 10 | status | uint16 | estado o resultado |
| 12 | config_id | uint32 | configuración preinstalada a usar |
| 16 | indice_efectivo | uint64 | primera muestra en la que rige el cambio |
| 24 | banda_lo | float32 | en CONFIG: inicio de la banda protegida en Hz; 0 en los demás opcodes [Aprobado; en la Tarea 1 era reservado] |
| 28 | banda_hi | float32 | en CONFIG: fin de la banda protegida en Hz; 0 en los demás opcodes [Aprobado; en la Tarea 1 era reservado] |

`config_id` remite a una configuración preinstalada (coeficientes, parámetros de reducción y escala), cuya huella se valida al preparar el ensayo. Los cambios se acuerdan para un índice futuro y se aplican tras el ACK de ambos filtros. Los comandos de configuración requieren ACK y un reintento acotado antes de empezar el ensayo. Un cambio de banda protegida o de N se envía en CONFIG, rige desde `indice_efectivo` después del ACK y genera un `config_id` nuevo.

---

## 7. Tipo de ruido y filtro sugerido [Aprobado]

Los códigos viajan en el DIAG: `tipo_ruido` (offset 10), `filtro_n2` (offset 11) y `metodo` (offset 8).

| tipo_ruido | Tipo de ruido | filtro_n2 | metodo (nodo 3) | Dato del DIAG que se usa |
|---|---|---|---|---|
| 0 | ninguno o desconocido | 0 pasa todo | 0 pasa todo | — |
| 1 | tonal (interferencia sinusoidal) | 2 notch IIR | 1 picos | pico_Hz |
| 2 | 50 o 60 Hz y armónicos | 3 peine con base de 50 o 60 Hz | 1 picos | pico_Hz = 50 o 60 |
| 3 | banda ancha (blanco) | 1 FIR de la banda protegida | 2 resta espectral | piso_resumen |
| 4 | banda limitada | 1 FIR de la banda protegida, o 2 notch si la banda es angosta | 2 resta espectral con protección de tonos | banda_lo, banda_hi |
| 5 | impulsivo | 1 FIR de la banda protegida | 2 resta espectral | energia |

Los nodos 2 y 3 siguen la sugerencia del DIAG en modo automático, o la configuración fijada por CONTROL en modo manual.

### FIR de la banda protegida (nodo 2) [Aprobado]

El nodo 2 calcula los coeficientes en la placa cada vez que cambia la banda protegida (reemplaza los juegos preinstalados):

- Ventana de Kaiser, **37 coeficientes siempre**, así que el retardo queda fijo en **18 muestras** con cualquier banda y la compensación del nodo 3 no cambia.
- Transición fija de 600 Hz; los cortes van en cada borde de la banda ± 300 Hz.
- **Pasa banda** entre los bordes inferior y superior de la banda protegida, como diferencia de dos pasa bajas.
- Si el borde inferior es menor que 600 Hz (incluye P1–P5), se usa **solo el pasa bajas**.
- Atenuación de diseño de 45 dB (β ≈ 3.975), igual que la Tarea 1: con la banda 100–1200 Hz los coeficientes coinciden exactamente con los de la Tarea 1.
- Rechazo: **≥ 45 dB** en el caso solo pasa bajas (la atenuación de diseño) y **≥ 40 dB** en el pasa banda (restar dos pasa bajas puede sumar sus errores).
- **Notch IIR de 2.º orden:** en modo automático usa Q = 8.5, centrado en el `pico_Hz` que envía el nodo 1 (ver *Plan de frecuencias*, P1).
- Cálculo: 37 valores de sinc × Kaiser, con la Bessel I0 por serie; tarda menos de 1 ms.
- Validación en la fase 1 contra `scipy.signal.firwin`, con tolerancia de 10⁻⁶.

---

## 8. Cambio de parámetros sin recompilar [Propuesta]

El enunciado exige poder ajustar parámetros durante la defensa sin recompilar.

- **Entre nodos:** CONTROL con `config_id` selecciona una configuración preinstalada [Tarea 1].
- **Consola USB de cada nodo:** comandos de texto para cambiar valores puntuales y consultar el estado, por ejemplo `set f_notch 2150`, `status`. Parámetros previstos:
  - nodo 1: frecuencias de los tonos del emisor, frecuencia de la interferencia, SNR objetivo, umbral de detección, **banda protegida y N** (los reenvía a los nodos 2 y 3 en CONTROL CONFIG);
  - nodo 2: modo automático o manual, filtro, frecuencia y Q del notch, base del peine (50 o 60 Hz);
  - nodo 3: modo automático o manual, método, α de la resta, ganancia mínima, protección de tonos, umbral y atenuación de picos.
- **Botones del nodo 3:** un botón cambia el método y el otro alterna entre modo automático y manual.

---

## 9. Qué hace el receptor con cada paquete [Tarea 1]

1. Acumula bytes hasta recibir 0x00. Si pasa de 4150 bytes sin delimitador, descarta hasta el próximo cero. Las tramas vacías (dos 0x00 seguidos, por ejemplo el 0x00 inicial de un emisor que arranca) se ignoran.
1b. **Cambio de sesión** [Aprobado, 27 oct]: si llega un paquete válido con otro `session_id`, el emisor se reinició. No es un error: se reinician la secuencia, el `first_sample` y el orden esperados. Los errores de decodificación entre el último paquete válido de la sesión vieja y el primero de la nueva se cuentan aparte, como errores de transición de sesión.
2. Decodifica COBS y valida CRC, magic, versión, destino, longitud, formato y que los valores sean finitos.
3. Un salto de `sequence` indica paquetes omitidos; `first_sample` y `sample_count` determinan si faltan muestras o solo diagnóstico.
4. Los duplicados y paquetes antiguos se descartan. Un bloque inválido nunca entra al historial de procesamiento.
5. No se retransmite audio vencido. Ante una pérdida: se registra el hueco, se marca el intervalo como inválido, se aplica silencio o una transición controlada en la salida, se reinician los estados que dependen del tramo faltante y el estimador vuelve a calentarse.
6. Los contadores (overruns, pérdidas, errores de CRC, saturaciones) se muestran en la consola USB, en la LCD del nodo 3 y con el LED de error [Aprobado].

**Sincronización:** N1 fija session_id, fs y el contador de muestras; los receptores usan esos índices como reloj lógico. N3 mantiene colas de 2048 muestras para la referencia y la salida FIR, y compara solo sesiones, configuraciones e índices coincidentes. Los índices no corrigen la deriva entre relojes: se requiere un reloj común o ajustar lentamente la reproducción según la ocupación de la cola.

---

## 10. Métricas y referencia limpia [Tarea 1]

- Con referencia válida (bandera 0x0001), el nodo 3 calcula MSE, SNR de entrada y de salida, ΔSNR y energía útil conservada para las dos rutas, compensando el retardo de 18 muestras del FIR.
- Sin referencia (por ejemplo en P6), las métricas que necesitan s se muestran como "N/D" y se usan estimaciones sin referencia.

---

## 11. Código compartido [Aprobado]

- Un archivo de definiciones para el firmware (`protocolo.h`, usado por los tres nodos en C++) y su equivalente para los scripts de la PC (`protocolo.py`), con las constantes y estructuras de este documento.
- COBS y CRC se replican de `calcular_comunicacion.py` y se prueban con sus vectores (`0xCBF43926` y `11 00 22` → `02 11 02 22`).
