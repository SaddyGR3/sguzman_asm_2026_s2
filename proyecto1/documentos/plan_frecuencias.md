# Plan de frecuencias y pruebas — Proyecto Grupal 1

**CE1110 Análisis de Señales Mixtas — Sistema distribuido de reducción adaptativa de ruido en tiempo real**

**Estado:** aprobado (25 oct). Actualizado el 28 oct: rechazo del FIR pasa bajas de la banda protegida a ≥ 45 dB (sección 5) y Q del notch de P1 = 8.5 (sección 4.3). Recoge las decisiones aprobadas del plan de frecuencias y pruebas. Los detalles del protocolo están en el *Contrato entre nodos* (versión 3.1) y los del montaje, en la *Guía de conexiones de hardware*.

---

## 1. Parámetros base [Tarea 1]

| Parámetro | Valor |
|---|---|
| Frecuencia de muestreo fs | 8000 Hz (Nyquist en 4000 Hz) |
| Tamaño de FFT N | 1024 muestras (Δf = 7.8125 Hz, ventana de 128 ms) |
| Avance H | 512 muestras (50 % de solape), un bloque cada 64 ms |
| Ventana | raíz de Hann periódica, en análisis y en síntesis |
| Formato | float32, señal normalizada en [−1, 1) |
| Retardo de reproducción | 256 ms (cuatro avances) |

---

## 2. Banda del sistema y banda protegida

- **Banda del sistema: 100–3000 Hz.** Es donde puede estar la señal útil en cualquier prueba.
  - **3000 Hz arriba:** deja 1000 Hz de transición hasta Nyquist, lo mínimo que permite un filtro analógico de 2.º orden sin atenuar la propia banda. Además cubre audio a 8 kHz con buena inteligibilidad.
  - **100 Hz abajo:** deja fuera los 60 Hz (sus armónicos de 120 y 180 Hz quedan dentro) y da margen al acople de entrada y a la eliminación de DC.
- **Banda protegida:** es dónde está la señal útil en cada prueba. Es distinta de la banda del sistema y se configura por prueba.
  - Por defecto: 100–3000 Hz.
  - Se configura en la consola del nodo 1, que la reenvía a los nodos 2 y 3 en CONTROL CONFIG.
  - La usan el clasificador del nodo 1, el FIR del nodo 2 y los métodos de picos y de resta del nodo 3.
- **Ruido de las pruebas:** siempre dentro de 100–3000 Hz. Entre 3 y 4 kHz lo atenuarían el filtro analógico y el FIR de decimación, y esa mejora la haría el hardware, no los filtros que se evalúan.

---

## 3. Cadena analógica y muestreo

### 3.1 Filtro analógico (anti-aliasing y reconstrucción)

Es el mismo diseño en la entrada del nodo 1 y en las salidas de los nodos 2 y 3: Sallen-Key de ganancia unitaria con LM358 a 5 V, tipo Butterworth.

| Componente | Valor |
|---|---|
| R1 = R2 | 6.8 kΩ |
| C1 (realimentación a la salida) | 10 nF |
| C2 (a tierra) | 4.7 nF |
| Resultado | fc ≈ 3.41 kHz, Q ≈ 0.73 |

| Frecuencia | Atenuación del filtro |
|---|---|
| 2150 Hz | ≈ −0.6 dB |
| 3000 Hz | ≈ −2 dB |
| 5000 Hz | ≈ −7.5 dB |
| ≥ 21 kHz | ≈ −32 dB o más |

En la entrada, R1 se mantiene en 6.8 kΩ. A frecuencias de audio, la baja impedancia de salida de la PC (más los 10 µF del acople) domina sobre el divisor, así que este no se suma a R1.

### 3.2 Entrada y ADC (nodo 1)

- Acople de 10 µF y divisor de 1.5 kΩ (hacia 3.3 V) + 1 kΩ (hacia GND): centro en **1.32 V**. Con el divisor forman un pasa altas de unos 27 Hz, por debajo de la banda del sistema.
- ADC de 12 bits con atenuación de 12 dB: mide de 150 a 2450 mV. La señal debe quedar entre **0.3 y 2.3 V** (2 Vpp).
- Conversión: voltaje con la calibración de ESP-IDF y luego `x = (v − 1.32 V) / 1.25 V`. Un pico de 0.8 normalizado corresponde a 0.32–2.32 V. Antes de normalizar se resta el nivel DC estimado.

### 3.3 Muestreo a 24 kHz y decimación ÷3

- El modo continuo del ADC del ESP32 no baja de 20 kHz, así que el nodo 1 muestrea a **24 kHz**.
- **Aliasing del muestreo a 24 kHz:** lo que se doblaría a la banda útil está por encima de 21 kHz, donde el filtro analógico atenúa unos 32 dB.
- **Aliasing de la bajada a 8 kHz:** lo que hay entre 5 y 12 kHz se doblaría a 0–3 kHz. Lo evita un **FIR de decimación** a 24 kHz:
  - paso hasta 3 kHz y rechazo desde 5 kHz, con 40–50 dB;
  - unos 35 coeficientes, calculado solo cada 3 muestras (unas 280 000 MAC/s);
  - después se toma 1 de cada 3 muestras.
- Los coeficientes y la respuesta del FIR de decimación se proponen en la fase 1, con el modelo del ADC.
- La señal de la PC se genera a 8 kHz, así que su contenido por encima de 4 kHz es prácticamente nulo. Los filtros protegen contra lo que no se controla, como el ruido de la PC y del USB.

### 3.4 Salida y DAC (nodos 2 y 3)

- DAC de 8 bits: `código = redondear(127.5 + 127.5·y)`, limitado a 0–255. Cada vez que se limita se suma 1 al contador de saturaciones. Con |y| ≤ 0.8, la salida queda entre 0.33 y 2.97 V.
- Cadena: DAC → seguidor de voltaje → Sallen-Key de reconstrucción → acople de 10 µF → potenciómetro atenuador → PAM8403.
- **Imágenes del DAC:** la retención (ZOH) más el filtro dejan la imagen del tono de 300 Hz (en 7.7 kHz) unos 42 dB abajo. El peor caso es una señal en 3 kHz, cuya imagen en 5 kHz queda unos 9 dB abajo.
- **Caída en banda:** a 3 kHz, la salida cae unos −4 dB en total (−2 dB del filtro y −2.1 dB del ZOH). Se declara en los criterios de aceptación.
- El DAC de 8 bits limita la SNR de salida a unos 48 dB.

---

## 4. Pruebas P1–P5

### 4.1 Reglas comunes

- **Nivel:** pico de x ≤ 0.8 normalizado. La SNR se fija primero por potencia; después, s y el ruido se escalan con el mismo factor hasta que el pico de la mezcla completa sea 0.8. Con ruido aleatorio, el factor cambia un poco con cada semilla.
- **Duración:** 10 s por WAV, con rampas de 20 ms al inicio y al final. Son unos 156 bloques, suficientes para pasar el calentamiento de 576 ms.
- **Formato:** WAV estéreo a 8 kHz, con el canal izquierdo = x (señal contaminada) y el derecho = s (referencia limpia).
- **Repeticiones:** 3 semillas por condición.
- Los tonos de 300, 700, 1100 y 2150 Hz caen entre bins (38.4, 89.6, 140.8 y 275.2), así que muestran fuga espectral real.

### 4.2 Resumen

| Prueba | Señal útil s | Ruido | SNR | Banda protegida | Nodo 2 | Nodo 3 |
|---|---|---|---|---|---|---|
| P1 | tono de 700 Hz, amplitud 0.4 | tono de 2150 Hz, amplitud 0.4 | 0 dB | 100–1200 Hz | notch IIR en `pico_Hz`, Q = 8.5 | picos |
| P2 | 300, 700 y 1100 Hz | gaussiano en 2000–2800 Hz | 0 dB | 100–1200 Hz | FIR de la banda protegida (pasa bajas de 1200 Hz) | resta con protección de tonos |
| P3 | audio sintético sin voz | blanco limitado a 100–3000 Hz | 5 dB | 100–3000 Hz | FIR de la banda protegida (pasa bajas de 3000 Hz) | resta (α = 3, ganancia mínima 0.05) |
| P4 | ráfagas de 700 Hz | impulsos limitados a 100–3000 Hz | 15 dB | 100–1200 Hz | FIR de la banda protegida (pasa bajas de 1200 Hz) | resta |
| P5 | 300, 700 y 1100 Hz | gaussiano en 900–1300 Hz | 3 dB | 100–1200 Hz | notch IIR en 1100 Hz (barrido de Q) | resta (barrido de α) |

### 4.3 Detalle por prueba

**P1 — tono con interferencia sinusoidal separada.**

- Es el caso 1 de la Tarea 1 con un solo tono útil.
- La frecuencia del notch sale de la detección del nodo 1; no está fija en el código.
- **Q del notch = 8.5** (valor del modo automático, decidido el 28 oct). Es la Q más alta, redondeada a 0.5, que da ≥ 30 dB en 2150 Hz con el error máximo de `pico_Hz` (Δf/2 = 3.9 Hz, sin interpolación) y pierde ≤ 0.1 dB en 700 Hz. Valores: −30.2 dB en el peor caso, −38.2 dB con el error real de P1 (1.56 Hz), 0.013 dB de pérdida en 700 Hz y polos con radio 0.905.
- Las semillas cambian solo las fases iniciales.
- Atenuación medida en 2130–2170 Hz.
- Evidencia: espectros y atenuación.

**P2 — tres tonos con ruido de alta frecuencia.**

- Tonos con amplitudes relativas 1, 0.55 y 0.30, y fases 0°, 35° y −50° (los de la Tarea 1).
- El ruido queda fuera de la banda protegida, dentro de la banda de rechazo del pasa bajas de 1200 Hz (desde 1800 Hz) y por debajo de 3 kHz.
- Las semillas cambian la realización del ruido.
- Atenuación medida en 2000–2800 Hz.
- Evidencia: reconstrucción y ΔSNR.

**P3 — audio con ruido de banda ancha.**

- Señal útil: audio sintético o material propio sin voz; por ejemplo, una melodía sintetizada con varios tonos, armónicos y envolvente, llevada a 8 kHz y a 100–3000 Hz.
- Se espera que la resta espectral gane con claridad, con "ruido musical" audible.
- Del FIR se espera una mejora prácticamente nula, porque el ruido está dentro de la banda de la señal: es la falla del filtro temporal que se quiere mostrar.
- Las semillas cambian la realización del ruido.
- Evidencia: MSE, energía y prueba auditiva.

**P4 — señal transitoria con ruido impulsivo.**

- Ráfagas de 700 Hz de 200 ms cada 1 s, con rampas de coseno de 5 ms y amplitud nominal de 0.4.
  - 200 ms es más que la ventana de la FFT (128 ms), así que la ruta espectral llega al régimen dentro de cada ráfaga.
  - Es menos que el historial del estimador (576 ms), así que para el estimador la señal es transitoria.
- Impulsos Poisson, unos 20 por segundo, con signo aleatorio y amplitud fija, filtrados a 100–3000 Hz.
- Las semillas cambian los instantes y los signos de los impulsos.
- Evidencia: respuesta temporal de cada ruta y latencia, medida con el arranque de cada ráfaga (por índice en la simulación, con osciloscopio en la placa).

**P5 — superposición parcial entre señal y ruido.**

- Es el caso 3 de la Tarea 1: el ruido tapa el tono de 1100 Hz y deja libres los de 300 y 700 Hz.
- Métricas propias: atenuación en 900–1300 Hz y ganancia del tono de 1100 Hz.
- Barrido de agresividad en ambas rutas a la vez (4 niveles × 3 semillas = 12 corridas):

| Nivel | Nodo 2: Q del notch en 1100 Hz | Nodo 3: α de la resta |
|---|---|---|
| Suave | Q = 10 | α = 2, sin protección |
| Medio | Q = 2.75 | α = 3, sin protección |
| Agresivo | Q = 1 | α = 8, sin protección |
| Referencia | Q = 2.75 | α = 3, con protección de tonos |

- El notch anula el tono de 1100 Hz en todos los niveles. Bajar la Q quita más ruido, pero empieza a llevarse el tono de 700 Hz: el filtro temporal no puede separar ruido y señal que se superponen. Valores calculados en 700 Hz: −0.05 dB con Q = 10, −0.67 dB con Q = 2.75 y −3.81 dB con Q = 1.
- Sin protección, subir α quita más ruido, pero también atenúa el tono de 1100 Hz.
- Evidencia: análisis del compromiso entre quitar ruido y distorsionar la señal.

---

## 5. FIR de la banda protegida (nodo 2)

El nodo 2 calcula los coeficientes en la placa cada vez que cambia la banda protegida.

- Ventana de Kaiser con **37 coeficientes siempre**. Así el retardo queda fijo en **18 muestras** (2.25 ms) con cualquier banda, y la compensación del nodo 3 no cambia.
- Atenuación de diseño de 45 dB (β ≈ 3.975), igual que la Tarea 1: con la banda 100–1200 Hz, los coeficientes coinciden exactamente con los de la Tarea 1.
- Transición fija de 600 Hz, como en la Tarea 1. Los cortes van en cada borde de la banda ± 300 Hz.
- **Pasa banda** entre los bordes inferior y superior de la banda protegida, calculado como la diferencia de dos pasa bajas.
- Si el borde inferior es menor que 600 Hz, se usa **solo el pasa bajas**. Esto incluye P1–P5, cuyo borde inferior es 100 Hz.
- Rechazo: **≥ 45 dB** en el caso solo pasa bajas (la atenuación de diseño; calculado: 46.1 dB para 100–1200 Hz y 45.3 dB para 100–3000 Hz) y ≥ 40 dB en el pasa banda, porque restar dos pasa bajas puede sumar sus errores (calculado: 44.2 dB para 800–2000 Hz y 45.7 dB para 1000–3000 Hz).
- Validación en la fase 1 contra `scipy.signal.firwin`, con tolerancia de 10⁻⁶.

---

## 6. Límites de P6

Estos son los límites que se le comunicarán al profesor. La comunicación está en espera.

| Qué puede cambiar el profesor | Límite |
|---|---|
| Señal útil | cualquier señal con contenido en 100–3000 Hz: tonos, multitono, audio o transitorios |
| Formato del archivo | WAV a 8 kHz, mono o estéreo. Si viene a otra tasa, la PC lo remuestrea a 8 kHz antes de reproducirlo |
| Nivel | pico de la mezcla ≤ 0.8 (0.3–2.3 V en el ADC), con el volumen calibrado. Si se pasa, el contador de saturaciones lo indica |
| Tipo de ruido | uno dominante a la vez: tonal, 50 o 60 Hz con armónicos, banda ancha, banda limitada o impulsivo |
| Frecuencia del ruido | 100–3000 Hz; el peine admite una base de 50 o 60 Hz |
| Amplitud relativa | SNR de entrada de −5 a 20 dB. Por debajo de −5 dB, la señal útil queda tan baja que el DAC de 8 bits limita la salida |
| Tamaño de bloque | N = 256, 512 o 1024, con avance de N/2 |
| Duración | ≥ 2 s (el estimador calienta 576 ms con N = 1024) |
| Referencia limpia | opcional. Sin ella, las métricas que necesitan s se muestran como N/D |

- **Tamaño de bloque:** el transporte sigue en 512 muestras por paquete. El nodo 3 y el diagnóstico del nodo 1 parten cada lote en sub-bloques de N/2, así que no cambian los paquetes, el retardo de 256 ms ni el FIR. N = 1024 es el máximo configurado en ESP-DSP.
- **Banda protegida en P6:** por defecto es 100–3000 Hz, porque la señal es desconocida. El operador puede ajustarla desde la consola del nodo 1 después de ver su diagnóstico.

---

## 7. Pendientes

- Parámetros concretos del audio sintético de P3 (fase 1, banco de señales).
- Criterios de aceptación cuantitativos por prueba, antes de las pruebas finales.
- Comunicar los límites de P6 al profesor (en espera).
