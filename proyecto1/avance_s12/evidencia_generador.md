# Evidencia: generador de tonos del nodo 1

## Método

Síntesis por acumulador de fase de 32 bits. Se compararon dos métodos para calcular el seno:
tabla de 1024 valores (TABLA) y `sinf()` (SINF).

Parámetros: fs = 8 kHz, bloque de 512 muestras (64 ms), tonos de 300, 700 y 1100 Hz
(amplitudes 1, 0.55 y 0.30) e interferencia de 2150 Hz (1.18, SNR = 0 dB), escala común de 0.26.

## Resultados medidos en la placa

| Método | Tiempo por bloque | Carga (de 64 ms) | Espuria máxima |
|---|---|---|---|
| TABLA | 501 µs | 0.8 % | −59.4 dB en 3750 Hz |
| SINF | 3551 µs | 5.6 % | −77.7 dB (límite de la medición) |

Error máximo entre ambos métodos: 0.0048. La FFT con ESP-DSP ubica los picos en las frecuencias correctas.

## Decisión

TABLA. Es 7 veces más rápida y deja tiempo para la FFT y el diagnóstico. Su espuria de −59 dB
queda por debajo del ruido de cuantización del DAC de 8 bits (~−48 dB) y del ruido que se suma
en las pruebas.

## Reproducibilidad

El código de la comparación está en el commit `5290add` de la rama `nodo1-emisor`.
