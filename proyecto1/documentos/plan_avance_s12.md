# Plan del avance de la semana 12 — Proyecto Grupal 1

**Entrega: viernes 30 oct, 11:59 pm** (meta interna: todo entregado a las 8 pm). Para este avance no hay defensa: se entrega todo lo que se pide.

Este plan reparte lo que falta en **cuatro frentes que arrancan en paralelo** el jueves 29. El contexto (qué está hecho y cómo se usa) está en `estado_proyecto.md`; los valores técnicos, en `plan_frecuencias.md` y `contrato_nodos.md`.

---

## 1. Qué se entrega

1. **Parte 1 — sistema completo en Python con el plan de frecuencias** (`proyecto1/simulacion/`): falta el nodo 3, la DFT contra FFT, la tabla de costo y el script de figuras.
2. **Parte 2 — emisor en el microcontrolador:** **terminada** (`proyecto1/firmware/nodo1/`, validada con `proyecto1/herramientas_pc/`).
3. **Diagramas de validación en el receptor:** por hacer, con el receptor de la PC y las capturas que ya existen.
4. **PDF del avance** (proceso de diseño, criterios y discusión) + código, en un zip en TEC-Digital.

---

## 2. Frentes

| Frente | Responsable | Rama | Carpeta |
|---|---|---|---|
| 1. Simulación: nodo 3 y figuras (**ruta crítica**) | A | `simulacion-nodo3`, luego `simulacion-figuras` | `proyecto1/simulacion/` |
| 2. Simulación: DFT contra FFT y tabla de costo | B | `simulacion-dft` | `proyecto1/simulacion/` |
| 3. Diagramas del receptor | B (al terminar el frente 2) o C | `avance-diagramas` | `proyecto1/avance_s12/diagramas/` |
| 4. PDF del avance | C | `avance-pdf` | `proyecto1/avance_s12/` |

Asignar un nombre a cada letra antes de empezar. Cada uno hace sus propios commits: el profesor revisa las estadísticas de todo el equipo.

### Frente 1 — Nodo 3 (paso 4) y figuras (paso 6)

**Paso 4.** La especificación para el agente (`fase1_paso4_nodo3.md`) ya está escrita y revisada; pedirla a Luis. Antes de pasarla al agente, aplicar estos dos cambios:

1. En la tabla de retardos (sección 2), fila del notch, agregar: *"El notch desfasa unos 2.5° el tono de 700 Hz (Q = 8.5). No es retardo sino desfase real del IIR; pone un piso de unos −27 dB al error de P1. Se explica en el PDF como diferencia entre el IIR y el FIR de fase lineal."*
2. En la prueba 15 (P2, nodo 3), cambiar `ΔSNR ≥ 10 dB` por `ΔSNR > 0`. El valor real se informa en las tablas del paso 6; un umbral sin calcular no debe hacer fallar pytest.

Lo demás queda tal cual: las pruebas 3 y 12 ya verifican los retardos de 512 y 18 muestras. Antes de correr las pruebas: `pip install -r requirements.txt` (agrega matplotlib 3.11.2). Si una prueba de integración falla, no se cambia el criterio: se analiza.

**Listo cuando:** `python -m pytest pruebas` pasa completo, `python -m sim.comparacion` genera `resultados/comparacion.csv`, `comparacion_resumen.csv` y las figuras P1–P5, y el PR está fusionado en `development`.

**Paso 6** (empieza cuando los pasos 4 y 5 estén en `development`). Un solo punto de entrada que regenera **todas** las figuras y tablas del PDF en `resultados/`:

- espectros y señales en el tiempo de P1–P5 (del paso 4) y tabla de métricas con media y desviación;
- nodo 2: diagrama de polos y ceros con el círculo unitario (FIR de 100–1200 Hz y notch de P1) y respuestas en frecuencia (FIR de 1200 y 3000 Hz, notch con Q = 8.5, 10, 2.75 y 1);
- cadena analógica: respuesta del Sallen-Key, del FIR de decimación y de la retención del DAC;
- DFT contra FFT y tabla de costo (del paso 5).

Usa las funciones que ya existen (`sim/analogico.py`, `sim/nodo2.py`, `sim/nodo3.py`); no recalcula nada a mano.

**Listo cuando:** un comando, desde `proyecto1/simulacion/`, genera todo lo anterior sin errores, y está fusionado en `development`.

### Frente 2 — DFT contra FFT y tabla de costo (paso 5)

Arranca ya: no depende del nodo 3. Rama nueva desde `development`.

- **DFT directa** a partir de su definición, X[k] = Σ x[n]·e^(−j2πkn/N), con N = 1024, comparada con `numpy.fft.fft`: error máximo relativo (debe ser del orden de 1e-12) y tiempo de cada una (`time.perf_counter`, varias repeticiones). Con una señal de P1 y con una aleatoria.
- **Tabla de costo, memoria y latencia** de cada método, como estimación justificada:

| Método | Operaciones | Memoria (float32) | Latencia |
|---|---|---|---|
| FIR de decimación (nodo 1) | 37 MAC cada 3 muestras a 24 kHz ≈ 296 000 MAC/s | 37 coef. + 37 de línea de retardo | 18 muestras a 24 kHz = 0.75 ms |
| FIR de la banda protegida (nodo 2) | 37 MAC por muestra ≈ 296 000 MAC/s | 37 coef. + 36 de estado | 18 muestras = 2.25 ms |
| Notch IIR (nodo 2) | 5 mult. por muestra ≈ 40 000/s | 5 coef. + 2 de estado | ≈ 0 (desfase, no retardo) |
| Espectral (nodo 3) | por trama de 64 ms: FFT + IFFT de 1024 (≈ 2·(N/2)·log2 N mult. complejas), ventana, ganancias | trama de 1024, historial de 8 × 513 magnitudes (≈ 16 KB), salida | 512 muestras = 64 ms + procesamiento |

  Completar y corregir los números con el código real; DFT directa: N² = 1 048 576 mult. complejas por trama, para mostrar por qué se usa la FFT.
- Código en `sim/` con su prueba en `pruebas/`, mismo estilo que `sim/nodo2.py` (valores desde `config/`, sin código sin uso).

**Listo cuando:** la prueba pasa, la tabla se genera como CSV en `resultados/` y el PR está fusionado. Si el frente 1 fusiona antes, traer `development` a la rama (`git merge development`) antes del PR: los dos tocan `README.md`.

### Frente 3 — Diagramas de validación del receptor

Base: `proyecto1/herramientas_pc/receptor_nodo1.py`, su README y las capturas de `proyecto1/herramientas_pc/capturas/`. Formato: Mermaid dentro de un `.md` (se ve en GitHub) y exportado a PNG para el PDF.

1. **Flujo de recepción:** bytes del puerto → búfer → corte en 0x00 (fragmento inicial descartado, tramas vacías ignoradas, búfer de más de 4150 B sin 0x00 = error de trama y resincronización) → COBS → CRC-32 → cabecera (magic, versión, tipo, origen, destino, tamaños) → sesión (cambio de `session_id`, bandera 0x0004, errores de transición) → secuencia (pérdidas, retroceso) → paridad datos/DIAG → DIAG (valores, energía) → contadores y veredicto.
2. **Validación del contenido:** tramo continuo más largo → recorte a segundos enteros → ventana de Hann → FFT → 4 picos (300, 700, 1100 y 2150 Hz ± 1 Hz, niveles relativos ± 0.5 dB) → SNR en N3 (0 ± 0.2 dB) → comparación contra lo esperado del diseño en Python.
3. **Montaje de prueba:** ESP32 (nodo 1) por USB a la PC (consola, `/dev/ttyUSB0`); TX de GPIO18 o GPIO17 al RX del YP-05 (jumper en 3.3 V, GND común, TX sin conectar) por USB a la PC (`/dev/ttyUSB1`).
4. **Tabla de resultados reales** del 28 oct: N3 con EN a los 30 s (1855 paquetes, 0 errores, 0 perdidos, 1 error de transición, picos exactos, SNR +0.000 dB) y N2 (1875 paquetes, 0 errores). Volver a correr `--archivo` sobre las dos capturas para copiar la salida exacta.

**Listo cuando:** los tres diagramas y la tabla están en `proyecto1/avance_s12/diagramas/`, en PNG, entregados a C y fusionados.

### Frente 4 — PDF del avance

Empieza ya con lo que no necesita figuras. Formato: el mismo del informe de la Tarea 1 (`proyecto1/tarea1/informe/`), o el que el grupo acuerde. Estructura sugerida:

1. **Objetivo y arquitectura:** tres nodos, qué hace cada uno, el emisor del avance (el profesor aprobó que genere los tonos internamente).
2. **Plan de frecuencias:** fs, N, H, banda del sistema y banda protegida, P1–P5. **Justificar juntos fs, N, formato numérico y tasa de comunicación** (lo exige el enunciado): 8 kHz, N = 1024 (Δf = 7.8 Hz), float32 y 921 600 baudios; el enlace N3 lleva unos 4252 B cada 64 ms ≈ 66 KB/s, cerca del 72 % de la capacidad.
3. **Cadena analógica:** Sallen-Key, ADC a 24 kHz con decimación, DAC con retención y sus números (`estado_proyecto.md`).
4. **Simulación:** señales con SNR controlada, DFT contra FFT, nodo 2 (FIR e IIR, H(z), polos, ceros, ROC, estabilidad), nodo 3 (método espectral causal), comparación y métricas, costo, memoria y latencia.
5. **Emisor:** generador por tabla (medición: 501 µs por bloque, 0.8 % de carga, espuria −59.4 dB, en `proyecto1/avance_s12/evidencia_generador.md`), protocolo y verificación.
6. **Validación en el receptor:** diagramas y resultados del frente 3.
7. **Discusión:** compromisos (P3: el FIR no mejora con ruido dentro de la banda; P5: bajar Q o subir α quita más ruido pero distorsiona la señal), limitaciones del modelo y próximos pasos hacia el 6 nov.

**Listo cuando:** el PDF tiene todas las figuras y diagramas, y lo revisó al menos otro integrante.

---

## 3. Calendario

| Cuándo | A | B | C |
|---|---|---|---|
| **Jueves 29** | Paso 4: aplicar los 2 cambios, agente, pruebas, PR | Paso 5, PR; luego diagramas | Estructura del PDF y secciones 1–3 y 5 |
| **Viernes 30, mañana** | Paso 6: figuras y tablas, PR | Diagramas terminados, entregados a C | Secciones 4, 6 y 7 |
| **Viernes 30, tarde** | Revisar que todo esté en `development` | Revisar el PDF completo | Integrar figuras y diagramas en el PDF |
| **Viernes 30, 8 pm** | Entrega (abajo) | | |

---

## 4. Entrega

1. Todos los PR fusionados en `development`; `python -m pytest pruebas` pasa completo desde `proyecto1/simulacion/`.
2. PDF final en `proyecto1/avance_s12/`.
3. PR de `development` a `main`, merge, tag `avance_s12` y push del tag (comandos en `guia_git.md`, "Cerrar una entrega").
4. Zip con el PDF y el código (`proyecto1/simulacion/`, `proyecto1/firmware/nodo1/` sin `.pio/`, `proyecto1/herramientas_pc/`) subido a TEC-Digital.

---

## 5. Reglas para que los frentes no choquen

- Cada frente en su rama y su carpeta (tabla de la sección 2). Rama nueva siempre desde `development` actualizado (`git checkout development`, `git pull`).
- Los frentes 1 y 2 tocan los dos `proyecto1/simulacion/README.md` y quizá `requirements.txt`: el segundo en fusionar trae antes `development` a su rama y resuelve ahí el conflicto (una o dos líneas).
- No se cambian `contrato_nodos.md`, `plan_frecuencias.md` ni los archivos de `config/` existentes sin avisar al grupo.
- No se suben entornos virtuales, `.vscode/` de la raíz, `.pio/` ni `__pycache__/`.
- Si se usa un agente de IA para el código: darle una especificación completa en un `.md` (qué archivos crea, qué no toca, criterios de las pruebas), pedirle primero un análisis sin modificar nada y solo después la implementación; no dejar que haga commit. El código debe poder explicarse línea por línea: en la defensa del 6 nov el profesor puede borrar cualquier línea que no se justifique.

**Riesgo principal:** el paso 6 depende de los pasos 4 y 5 y queda para el viernes en la mañana. Si el paso 4 se atrasa, el PDF sale sin las figuras del nodo 3. Por eso el frente 1 no toma nada más.
