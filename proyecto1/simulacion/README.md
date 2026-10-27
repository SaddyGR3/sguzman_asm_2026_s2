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

## Nota

El código marcado como "Origen: Tarea 1" se copió de `proyecto1/tarea1/`.
