# Guía de conexiones de hardware — Proyecto Grupal 1

Cómo conectar cada componente. Los pines exactos de cada placa están en el *Contrato entre nodos*.

---

## 1. Camino de la señal

1. La PC reproduce el WAV (señal + ruido) con cualquier reproductor.
2. El audio sale por la salida de audífonos de la PC, viaja por el cable auxiliar y llega al jack del nodo 1.
3. El circuito de entrada lo acondiciona y el ADC del nodo 1 lo convierte en muestras.
4. El nodo 1 envía bloques de muestras por UART a los nodos 2 y 3.
5. Cada nodo filtra a su manera y su DAC convierte el resultado otra vez en voltaje.
6. El filtro de reconstrucción suaviza la señal y el PAM8403 mueve el parlante.

Para el avance de la semana 12, el nodo 1 genera los tonos internamente y los pasos 1–3 no se usan todavía.

---

## 2. Entrada de audio (nodo 1)

**Conexión:** salida de audífonos de la PC → cable auxiliar 3.5 mm macho–macho → jack hembra PJ-307 en la protoboard.

**Jack PJ-307:** tiene 5 patitas; se usan 3:

| Contacto del conector | Señal | A dónde va |
|---|---|---|
| Punta (tip) | canal izquierdo = señal contaminada x | circuito de entrada → GPIO34 |
| Anillo (ring) | canal derecho = referencia limpia s (opcional) | segundo circuito de entrada → GPIO35 |
| Base (sleeve) | tierra | GND de la ESP32 |

Las otras 2 patitas son interruptores internos y no se conectan. Para identificar cada patita: enchufar el cable y medir continuidad con el multímetro contra la punta, el anillo y la base del conector. El jack no calza en la protoboard: soldarle 3 cables.

**En la PC:** al conectar el cable, el audio sale por ahí. Si no, elegir "Audífonos" como dispositivo de salida en la configuración de sonido. Empezar con el volumen a media escala y ajustarlo midiendo con el osciloscopio. Si la laptop no tiene jack, usar un adaptador USB a 3.5 mm.

**Circuito de entrada (por cada canal):**

1. **Capacitor de acople de 10 µF** en serie (quita el nivel DC de la PC). Si es electrolítico, el terminal **+** va hacia el divisor (lado de 1.32 V). Con el divisor forma un pasa altas de unos 27 Hz, debajo de la banda del sistema (100–3000 Hz).
2. **Divisor de 1.5 kΩ (hacia 3.3 V) + 1 kΩ (hacia GND)**, para centrar la señal en **1.32 V**, el punto medio del rango que mide el ADC.
3. **Filtro anti-aliasing:** Sallen-Key de ganancia unitaria (ver sección 3), con los mismos valores que el de reconstrucción. R1 se mantiene en 6.8 kΩ: a frecuencias de audio la impedancia baja de la PC domina sobre el divisor.
4. Resistencia de 1 kΩ en serie y dos diodos hacia GND y 3.3 V como protección del pin del ADC. Con la señal entre 0.3 y 2.3 V los diodos nunca conducen.

**Nivel en el ADC: entre 0.3 y 2.3 V (2 Vpp centrados en 1.32 V).** Con atenuación de 12 dB, el ADC del ESP32 mide de 150 a 2450 mV; fuera de ese rango lee mal o recorta. Esto fija el volumen de la PC y la amplitud máxima de los WAV (pico ≤ 0.8 en escala normalizada). Verificarlo con el osciloscopio en el pin del ADC.

**Muestreo:** en el ESP32 clásico el modo continuo del ADC no baja de 20 kHz. El nodo 1 muestrea a 24 kHz y baja a 8 kHz en el firmware en dos pasos:

1. **FIR de decimación a 24 kHz** (paso hasta 3 kHz, rechazo desde 5 kHz, 40–50 dB, unos 35 coeficientes). Quita lo que hay entre 5 y 12 kHz, que al bajar a 8 kHz se doblaría dentro de la banda útil.
2. **Tomar 1 de cada 3 muestras.** El FIR solo se calcula para las muestras que se conservan (unas 280 000 operaciones por segundo).

Protección contra aliasing por etapas: el filtro analógico protege el muestreo a 24 kHz (lo que se doblaría está por encima de 21 kHz, donde atenúa unos 32 dB) y el FIR de decimación protege la bajada a 8 kHz.

**Nunca conectar el audio directo al pin del ADC:** el audio tiene voltajes negativos y el ADC solo acepta 0–3.3 V.

**Por qué cable y no micrófono:** con micrófono no se controla la SNR (entra el ruido del aula), se pierde la alineación con la referencia limpia y hay riesgo de realimentación con los parlantes.

---

## 3. Op-amp LM358

- Usar la versión DIP-8 (con patitas), no la SOP-8.
- Alimentar con **5 V desde el pin VIN de la ESP32** (a 3.3 V no funciona bien) y GND.
- Capacitor de 100 nF entre su alimentación y GND, cerca del chip.
- Trae dos amplificadores por chip, uno por nodo:
  - nodo 1: una mitad filtra el canal x y la otra el canal s;
  - nodos 2 y 3: una mitad es el seguidor de voltaje del DAC y la otra el filtro de reconstrucción.
- No es rail-to-rail: a 5 V su entrada admite de 0 a 3.5 V y su salida va de unos 5 mV a unos 3.5 V con carga liviana. Las señales del proyecto (0.3–2.3 V en la entrada, 0.33–2.97 V en las salidas) caben.
- Para qué sirve: filtros activos. A la entrada evita el aliasing (lo que pasa de 4 kHz se dobla dentro de la banda útil y no se puede quitar después). A la salida quita los escalones del DAC y sus copias alrededor de 8 kHz.

**Filtro Sallen-Key (el mismo diseño para anti-aliasing y reconstrucción, armado tres veces):**

| Componente | Valor | Posición |
|---|---|---|
| R1 | 6.8 kΩ | entrada, en serie |
| R2 | 6.8 kΩ | en serie, después de R1 |
| C1 | 10 nF | del punto entre R1 y R2 a la salida del op-amp (realimentación) |
| C2 | 4.7 nF | de la entrada no inversora a tierra |
| Op-amp | LM358 como seguidor (salida unida a la entrada inversora) | ganancia unitaria |

Resultado: Butterworth, fc ≈ 3.41 kHz, Q ≈ 0.73. Atenúa unos −2 dB a 3 kHz y unos −7.5 dB a 5 kHz. Caída total esperada de la salida a 3 kHz: unos −4 dB (filtro más el efecto de retención del DAC); se declara en los criterios de aceptación.

---

## 4. Salida de audio (nodos 2 y 3)

1. DAC en GPIO25.
2. **Seguidor de voltaje** con una mitad del LM358 (salida unida a la entrada inversora, DAC a la no inversora). La documentación de ESP-IDF no especifica la resistencia de salida del DAC; el seguidor evita que altere el filtro.
3. Filtro de reconstrucción: el Sallen-Key de la sección 3, con la otra mitad del LM358.
4. Capacitor de unos 10 µF en serie: la señal va montada sobre un nivel DC que saturaría o calentaría el amplificador.
5. **Potenciómetro de 10 kΩ como atenuador (obligatorio).** El PAM8403 tiene ganancia fija de 24 dB (×16) y la señal del filtro (unos 2.6 Vpp) lo saturaría. Arrancar con el potenciómetro al mínimo y subir con cuidado.
6. PAM8403 → parlante de 4–8 Ω.

Una salida por nodo (dos parlantes) para escuchar y comparar ambos métodos.

---

## 5. Enlaces UART entre nodos

- Siempre TX de una placa → RX de la otra, y tierra común entre las tres placas.
- Todo trabaja a 3.3 V: no hace falta conversor de nivel.
- Cables cortos (921600 baudios).
- **No usar GPIO1/GPIO3 (UART0):** son los mismos que usa el USB para programar y para la consola.
- UART1 se reasigna a GPIO18/19 porque sus pines por defecto (GPIO9/10) están conectados a la flash.

El cableado de los tres enlaces está en el *Contrato entre nodos*, sección 3.

---

## 6. Adaptador YP-05 (USB a TTL)

Permite que la PC hable directamente con la UART1 o UART2 de una placa, sin tocar la UART0.

- **Poner el jumper en 3.3 V antes de conectar.**
- TX del YP-05 → RX de la UART que se está probando.
- RX del YP-05 → TX de esa UART.
- GND → GND.
- No conectar VCC: la ESP32 ya se alimenta por su USB.

Usos: recibir en la PC los paquetes del emisor y validarlos con un script, o imitar al nodo 1 para probar los nodos 2 y 3 por separado.

**Puertos con el YP-05 conectado:** la ESP32 suele quedar en `/dev/ttyUSB0` y el YP-05 en `/dev/ttyUSB1` (verificar con `ls /dev/ttyUSB*` antes y después de conectarlo). PlatformIO puede elegir el puerto equivocado; abrir el monitor indicando el puerto: `pio device monitor -p /dev/ttyUSB0 -b 115200`.

**Receptor de validación:** `proyecto1/herramientas_pc/receptor_nodo1.py` recibe un enlace (`--enlace n2` con el RX del YP-05 en GPIO18, `--enlace n3` en GPIO17), valida CRC, COBS, secuencia, banderas y DIAG, y confirma los picos de la FFT. Con `--archivo` reprocesa una captura guardada (`proyecto1/herramientas_pc/capturas/`).

---

## 7. LCD 1602 I2C (nodo 3)

| LCD | ESP32 |
|---|---|
| GND | GND |
| VCC | VIN (5 V) si en la guía original iba a 5 V, o 3.3 V si iba a 3.3 V |
| SDA | GPIO21 |
| SCL | GPIO22 |

Si enciende pero no muestra texto, ajustar el tornillo de contraste en la parte de atrás. Solo caben 32 caracteres: rotar pantallas cada pocos segundos (método, energía, MSE, SNR).

---

## 8. LEDs y botones

- **LED de error (GPIO4, los tres nodos):** se enciende al perder un bloque o fallar un CRC. Cumple el requisito de indicar pérdidas y desbordamientos.
- **LED RGB (nodo 3):** indica el método activo.
- **Botones (nodo 3, GPIO32 y GPIO33 con pull-up interno):** cambiar de método y alternar modo automático/manual sin recompilar.

---

## 9. Pines que no se deben usar

- GPIO6–11: conectados a la flash.
- GPIO0, 2, 12, 15: pines de arranque; si tienen algo conectado la placa puede no arrancar.
- GPIO1, 3: UART0 (USB).
