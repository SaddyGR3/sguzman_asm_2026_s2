# Sección 2.1 — Fundamentos, muestreo y FFT

Esta carpeta reúne el desarrollo completo de la sección 2.1.

## Contenido

```text
seccion_2_1/
├── README.md
├── docs/
│   ├── 2_1a_fundamentos_fourier_dft_fft.md
│   ├── 2_1b_resolucion_frecuencial.md
│   ├── 2_1c_ventanas_fuga_espectral.md
│   └── 2_1d_simetria_conjugada.md
├── src/
│   └── analizar_2_1.py
└── resultados/
    ├── figuras/
    ├── tablas/
    └── resultados_2_1.json
```

## Parámetros principales

Para los incisos 2.1(b), 2.1(c) y 2.1(d) se utiliza como referencia:

```text
fs = 8000 Hz
N = 1024
T = 0.128 s
Δf = 7.8125 Hz
```

Esto mantiene coherencia con los bloques usados posteriormente en las señales del proyecto.

## Ejecución

Desde la raíz del repositorio:

```bash
python3 seccion_2_1/src/analizar_2_1.py
```

El script:

1. implementa una DFT directamente y la compara con `numpy.fft.fft`;
2. genera la tabla de resolución, duración y memoria;
3. compara un tono centrado en un bin y otro entre bins con ventanas rectangular y Hann;
4. genera gráficas de magnitud y fase;
5. verifica la simetría conjugada;
6. demuestra el efecto de romperla antes de ejecutar la IFFT;
7. guarda los resultados numéricos en JSON.

## Dependencias

```text
numpy
matplotlib
```

## Resultados esperados de referencia

La ejecución debe producir valores próximos a:

```text
DFT directa vs FFT:
error máximo ~ 6e-14

N = 1024:
T = 128 ms
Δf = 7.8125 Hz

Simetría conjugada:
error máximo ~ 1e-14

IFFT tras modificación asimétrica:
parte imaginaria máxima ~ 0.5

IFFT preservando simetría:
parte imaginaria máxima ~ 1e-16
```

Las pequeñas diferencias entre plataformas son normales por precisión numérica.
