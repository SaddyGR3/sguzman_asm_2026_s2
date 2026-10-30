# Estado del proyecto — Proyecto Grupal 1

**CE1110 Análisis de Señales Mixtas — Sistema distribuido de reducción adaptativa de ruido en tiempo real**

Resumen para el equipo: qué está hecho, cómo se usa y qué falta. Actualizado: 29 oct.

Documentos de referencia en esta carpeta:

| Documento | Para qué |
|---|---|
| `contrato_nodos.md` (v3.1) | Protocolo entre nodos: pines, paquetes, cabecera, DIAG, CONTROL, errores. Todo nodo o script lo respeta |
| `plan_frecuencias.md` | fs, N, bandas, cadena analógica, pruebas P1–P6 y diseño de los filtros |
| `guia_conexiones_hardware.md` | Cómo se conecta cada componente |
| `guia_git.md` | Flujo de ramas, PR y commits |
| `plan_avance_s12.md` | Reparto de lo que falta para el avance del 30 oct, en frentes paralelos |

---

## 1. Entregas

| Entrega | Fecha | Contenido |
|---|---|---|
| Avance semana 12 | **vie 30 oct, 11:59 pm** | Parte 1: sistema completo en Python con el plan de frecuencias. Parte 2: emisor en el microcontrolador. Diagramas de validación en el receptor. PDF del avance + código, sin defensa. Plan de trabajo: `plan_avance_s12.md` |
| Proyecto 1 | **vie 6 nov, 11:50 pm** | Sistema funcionando en hardware, paper IEEE (4 págs.), documento de herramientas (2 págs.) y defensa de 15 min con sonido |

---

## 2. Lo que ya está hecho

### Parte 2 del avance — emisor en el nodo 1 (terminada)

Código en `proyecto1/firmware/nodo1/` (PlatformIO, `framework = espidf`, C++, ESP-DSP).

El profesor aprobó que, para el avance, el emisor genere los tonos internamente en lugar de adquirirlos por el ADC.

- Genera cada 64 ms un bloque de 512 muestras a 8 kHz: tonos de 300, 700 y 1100 Hz (señal útil s) más interferencia en 2150 Hz (x = s + interferencia, SNR 0 dB).
- FFT de arranque en la placa para verificar los picos.
- Empaqueta según el contrato (cabecera de 32 B, datos float32, CRC-32, COBS, delimitador 0x00) y envía:
  - UART1 (GPIO18) → nodo 2: INPUT + DIAG;
  - UART2 (GPIO17) → nodo 3: INPUT_REF (x y s intercalados) + DIAG;
  - 921 600 baudios, 8N1.
- Al arrancar escribe un 0x00 en cada UART para que el receptor se resincronice si el emisor se reinicia a mitad de un paquete.
- **Verificado en placa:** 0 overruns, periodo de 64 000 µs, prueba de lazo sin diferencias.

**Validación con la PC** (`proyecto1/herramientas_pc/receptor_nodo1.py`): un receptor independiente lee cada enlace con el adaptador YP-05 y valida CRC, COBS, secuencia, banderas, DIAG y energía, y confirma los picos de la FFT y la SNR.

- Resultado: `RESULTADO: OK` en los dos enlaces, 0 errores y 0 paquetes perdidos en 60 s; el reinicio con EN se recupera desde el primer paquete de la sesión nueva.
- Capturas guardadas en `proyecto1/herramientas_pc/capturas/` (`captura_n2.bin`, `captura_n3.bin`); se reprocesan con `--archivo` sin la placa.
- Uso y conexión: `guia_conexiones_hardware.md`, sección 6.

### Parte 1 del avance — simulación en Python (4 de 6 pasos)

Código en `proyecto1/simulacion/`. Todo valor de diseño sale de `config/*.json`; cada módulo tiene sus pruebas en `pruebas/`.

| Paso | Archivos | Qué hace |
|---|---|---|
| 1. Protocolo y señales | `sim/protocolo.py`, `sim/senales.py`, `config/pruebas.json` | Paquetes del contrato (el mismo módulo lo usa el receptor de la PC). Banco de señales P1–P5 con 3 semillas cada una y WAV estéreo (izquierdo = x, derecho = s) |
| 2. Cadena analógica | `sim/analogico.py`, `config/cadena_analogica.json`, `resultados/decimacion.json` | Acople de entrada, Sallen-Key (fc 3.41 kHz, Q 0.73), ADC de 12 bits a 24 kHz (0.15–2.45 V), FIR de decimación de 37 coeficientes y ÷3, DAC de 8 bits con retención. x y s pasan por la misma cadena. `decimacion.json` tiene los coeficientes para el firmware del nodo 1 |
| 3. Nodo 2 | `sim/nodo2.py`, `config/nodo2.json` | FIR de la banda protegida (Kaiser, 37 coeficientes, fórmula explícita como en la placa, validado contra `firwin` y contra la Tarea 1) y notch IIR de 2.º orden. Polos, ceros, ROC y estabilidad. Filtrado por bloques con estado |
| 4. Nodo 3 y comparación | `sim/nodo3.py`, `sim/metricas.py`, `sim/comparacion.py`, `config/nodo3.json` | FFT/IFFT causal con raíz de Hann y suma con solape; detección de picos o resta espectral con protección opcional de tonos. Compara entrada, nodo 2 y nodo 3 contra la referencia limpia tras la misma cadena analógica; genera tablas y figuras |

Cómo correrlo (desde `proyecto1/simulacion/`, con el entorno virtual activo):

```
pip install -r requirements.txt
python -m pytest pruebas        # 187 pruebas en la verificación del 29 oct
python -m sim.analogico          # genera resultados/decimacion.json
python -m sim.nodo2              # resumen de filtros de P1–P5
python -m sim.comparacion        # genera tablas de métricas y figuras P1–P5
```

Valores clave que salieron de la simulación:

- FIR de decimación: ondulación 0.036 dB hasta 3 kHz, rechazo 49.8 dB desde 5 kHz, retardo de 6 muestras a 8 kHz.
- Caída de la salida a 3 kHz: unos −3.9 dB (filtro + retención del DAC). Imagen del DAC de 300 Hz: unos 42 dB abajo.
- FIR de la banda protegida: rechazo ≥ 45 dB (pasa bajas), retardo fijo de 18 muestras.
- Notch de P1: Q = 8.5 (≥ 30 dB aunque la detección del pico se equivoque 3.9 Hz; pierde 0.013 dB en 700 Hz).
- Compromiso de P5: bajar la Q del notch de 10 a 1 lleva la pérdida en 700 Hz de −0.05 a −3.8 dB.
- Nodo 3: ventana N = 1024, avance H = 512, historial causal de 8 tramas y retardo algorítmico de 64 ms. El tramo de evaluación es de 1 a 9 s, con 3 semillas por condición; P5 tiene 4 niveles.
- Comparación del 29 oct: se verificó que `python -m sim.comparacion` genera 72 filas de resultados, 24 grupos de medias y desviaciones y cinco figuras. Son archivos regenerables; las pruebas no los escriben. ΔSNR medio del nodo 3: P1 +51.32, P2 +25.66, P3 +5.94 y P4 +6.49 dB; P5 +10.33, +9.53, +9.21 y +10.80 dB (suave, medio, agresivo, referencia). Son resultados de la simulación, no mediciones de la placa.
- Verificación local: 188 pruebas pasando con Python 3.11.9, NumPy 2.4.6, SciPy 1.16.3, pytest 9.1.1 y matplotlib 3.11.1. Repetir en el entorno objetivo de Python 3.14 y versiones fijadas por `requirements.txt` antes de entregar.

---

## 3. Lo que falta para el viernes 30

| Qué | Estado |
|---|---|
| Paso 4 — nodo 3: método espectral causal, métricas y comparación P1–P5 | Implementado y verificado localmente en `simulacion-nodo3`; falta revisión del equipo y fusión a `development` |
| Paso 5 — DFT directa contra FFT (N = 1024) y tabla de costo computacional, memoria y latencia de cada método | Implementado y verificado en `simulacion-dft`: 207 pruebas pasan y resultados generados; cambios locales revisados, pendientes de commit, push y PR |
| Paso 6 — un solo script que genera todas las figuras y tablas (incluye polos y ceros y la respuesta en frecuencia del nodo 2) | Pendiente |
| PDF del avance: proceso de diseño, criterios y discusión | **Sin responsable** |
| Diagramas de validación del receptor: flujo de recepción, validación del contenido y montaje a partir de las capturas guardadas | Completado en `avance-diagramas`: cuatro diagramas Mermaid, tabla y salidas completas de N2 y N3. Se ejecutaron `python proyecto1/herramientas_pc/receptor_nodo1.py --archivo proyecto1/herramientas_pc/capturas/captura_n3.bin --enlace n3` y el comando equivalente con `captura_n2.bin --enlace n2`; ambas capturas terminaron en `RESULTADO: OK` |
| Entrega: zip en TEC-Digital, PR `development` → `main` y tag `avance_s12` (ver `guia_git.md`) | Pendiente |

Material para el PDF que ya existe: el plan de frecuencias (justificación de fs, N, bandas y filtros), los resultados de la cadena analógica y del nodo 2 de arriba, y la salida del receptor de la PC como evidencia del emisor.

---

### Verificación del paso 5 — 29 oct 2026

Se agregaron `sim/dft.py`, `sim/costo.py`, sus pruebas y la sección **DFT y
costo** del README de simulación. Verificación con Python 3.14.8, NumPy 2.5.4,
SciPy 1.18.1, pytest 9.1.1 y matplotlib 3.11.2: **207 pruebas pasaron**,
incluidas 19 nuevas. Se usó un entorno virtual temporal fuera del repositorio
(`/tmp/asm-dft-validacion`), sin cambiar las dependencias declaradas.

Desde `proyecto1/simulacion/`, con el entorno activo:

```
python -m pytest pruebas
python -m sim.dft
python -m sim.costo
```

Ambos módulos terminaron correctamente y generaron `resultados/dft_fft.json`
y `resultados/costo.csv`. DFT contra FFT con N = 1024:

| Señal | Error máximo relativo | DFT (ms) | FFT (ms) | Aceleración medida |
|---|---:|---:|---:|---:|
| P1 | 2.562e-13 | 16.0855 | 0.021558 | 746.15 |
| Aleatoria | 3.093e-13 | 16.0307 | 0.019057 | 841.20 |

Las mediciones son medianas de cinco ejecuciones en PC, no en el ESP32.
Incluyen el bucle Python y las llamadas a NumPy: no aíslan únicamente la
complejidad de los algoritmos.
El cociente teórico de multiplicaciones complejas es 204.8 para ambas señales.
Las cuatro filas de costo coinciden con 296 000, 296 000, 40 000 y
65 536 000 multiplicaciones reales por segundo. Se corrigió la memoria de
la DFT por frecuencia a **57 344 B (56 KiB)**: entrada, salida y términos
`complex128`, e índices `float64`. El vector de términos se reutiliza; no se
construye una matriz N×N. Se excluyen objetos Python y trabajo interno de
NumPy; la justificación está en `plan_frecuencias.md`.
La función `costo_espectral` queda disponible para el paso 6; su fila no está
en el CSV inicial. No se cambió el contrato entre nodos ni las configuraciones.

## 4. Lo que falta para el 6 de noviembre (hardware)

1. **Circuitos analógicos** (`guia_conexiones_hardware.md`): entrada del nodo 1 (acople, divisor a 1.32 V, Sallen-Key, protección) y salidas de los nodos 2 y 3 (seguidor, Sallen-Key, acople, potenciómetro, PAM8403). Verificar con osciloscopio. Confirmar que las compras (LM358 DIP-8, jack PJ-307, cable auxiliar) estén hechas.
2. **Firmware de los tres nodos:**
   - nodo 1: ADC en modo continuo a 24 kHz con el FIR de `resultados/decimacion.json`, quitar DC, FFT, diagnóstico y clasificador de ruido, consola para cambiar parámetros;
   - nodo 2: recepción, FIR calculado en la placa y notch (mismos valores que `sim/nodo2.py`), salida por DAC;
   - nodo 3: recepción, FFT/IFFT con los métodos del paso 4, métricas en la LCD, LED de error, botones.
3. **Integración y pruebas:** por pares (1–2, 1–3) y luego los tres; P1–P5 con 3 repeticiones; respuesta en frecuencia medida contra la calculada; latencia y memoria; ensayo de P6. Antes, escribir los criterios de aceptación.
4. **Documentación:** paper IEEE (máx. 4 págs., abstract en inglés de 150–250 palabras), documento de herramientas (máx. 2 págs.), merge a `main`, tag `proyecto1`, ensayo de la defensa de 15 min.

Pendientes de decisión: parámetros finales del audio sintético de P3, criterios de aceptación por prueba y comunicar al profesor los límites de P6 (`plan_frecuencias.md`, sección 6).

---

## 5. Reglas de trabajo

- **Git:** cada tarea en una rama nueva desde `development` actualizado, PR a `development` con `--merge`. Commits pequeños y de todos los integrantes: el profesor revisa las estadísticas semanales.
- **Carpetas:** la simulación solo en `proyecto1/simulacion/`; el firmware de cada nodo en `proyecto1/firmware/nodoX/`; las herramientas de PC en `proyecto1/herramientas_pc/`.
- **Contrato y plan de frecuencias:** si algo debe cambiar, se cambia primero en el documento y se avisa al grupo.
- **Todo resultado del firmware se compara contra la simulación** (mismos valores de `config/`).
- **Código justificable:** en la defensa, el profesor puede borrar cualquier línea que no se sepa explicar. Nada de código sin uso.
- **Entorno de Python:** Python 3.14, numpy 2.5.4, scipy 1.18.1, pytest 9.1.1, pyserial 3.5 (y matplotlib 3.11.2 desde el paso 4), en un entorno virtual fuera del repositorio. No subir `.vscode/` ni entornos virtuales.
