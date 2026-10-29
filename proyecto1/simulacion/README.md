# Simulación del sistema de reducción de ruido

## Propósito

Simulación en Python del sistema de tres ESP32 conectados por UART (CE1110, Análisis de Señales Mixtas). Esta base contiene:

- el **protocolo** binario entre nodos (`sim/protocolo.py`);
- el **banco de señales** de las pruebas P1–P5 (`sim/senales.py`), que genera WAV estéreo (canal izquierdo = x, canal derecho = s) para que la PC los reproduzca hacia el nodo 1;
- la **configuración** de las pruebas (`config/pruebas.json`).

Parámetros: fs = 8000 Hz, N = 1024, H = 512, float32 en transporte, señal normalizada en [−1, 1).

## Estructura

```
config/pruebas.json     configuración de las pruebas (único lugar con valores numéricos)
sim/protocolo.py        paquetes, COBS, CRC-32, DIAG y CONTROL
sim/senales.py          generación de las señales de P1–P5
pruebas/                pruebas con pytest
senales/                salida de la generación (valor por defecto de global.carpeta_salida)
config/cadena_analogica.json  parámetros de hardware de la cadena analógica (único lugar con esos valores)
sim/analogico.py        modelo de la cadena analógica de entrada (nodo 1) y de salida (nodos 2 y 3)
resultados/decimacion.json  coeficientes del FIR de decimación y sus métricas, generados por sim/analogico.py
```

## Generar las señales

Desde esta carpeta:

```
python -m sim.senales
```

Crea `senales/P<p>/<semilla>/` con `entrada_estereo.wav`, `muestras.npz` y `metadatos.json`. Los WAV se suben al repositorio; los `.npz` no, porque se regeneran.

## Correr las pruebas

Desde esta carpeta:

```
python -m pytest pruebas
```

## Cadena analógica

`sim/analogico.py` modela el hardware entre la PC y las muestras a 8 kHz, y entre las muestras y el parlante:

- **Entrada (nodo 1):** PC → acople → Sallen-Key → ADC a 24 kHz (12 bits, 0.15–2.45 V) → FIR de decimación ÷3 → 8 kHz.
- **Salida (nodos 2 y 3):** DAC de 8 bits → retención de orden cero → Sallen-Key.
- **x y s pasan por la misma cadena** de entrada, con el mismo retardo y la misma atenuación.

Los parámetros están en `config/cadena_analogica.json`. Para generar los coeficientes del FIR de decimación (fuente para el firmware del nodo 1), desde esta carpeta:

```
python -m sim.analogico
```

Crea `resultados/decimacion.json`, que sí se sube al repositorio.

## Limitaciones del modelo

La calibración del ADC se supone ideal e ignora la alinealidad real del ADC del ESP32, y el paso de cuantización de 3.3 V/4096 es un supuesto levemente pesimista. Ambos se verifican en la placa en la fase 4.

## Nota

El código marcado como "Origen: Tarea 1" se copió de `proyecto1/tarea1/`.
