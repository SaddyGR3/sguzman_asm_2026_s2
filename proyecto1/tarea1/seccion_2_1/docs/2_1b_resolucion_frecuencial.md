# 2.1(b) Resolución frecuencial, latencia y memoria

## Parámetros de referencia

Para mantener coherencia con los bloques utilizados posteriormente en el proyecto se toma como referencia:

\[
f_s = 8000\ \text{Hz}
\]

y un bloque principal de

\[
N = 1024\ \text{muestras}.
\]

La duración temporal observada por cada bloque es

\[
T=\frac{N}{f_s}
=
\frac{1024}{8000}
=
0.128\ \text{s}.
\]

La separación entre muestras espectrales de la DFT es

\[
\boxed{\Delta f=\frac{f_s}{N}}
\]

por lo que

\[
\Delta f
=
\frac{8000}{1024}
=
\boxed{7.8125\ \text{Hz}}.
\]

Como \(T=N/f_s\), también puede escribirse

\[
\boxed{\Delta f=\frac{1}{T}}.
\]

Esto muestra directamente que una observación temporal más larga produce una separación espectral menor.

---

## Comparación para distintos tamaños de bloque

Manteniendo \(f_s=8000\) Hz:

| \(N\) | Duración \(T\) | \(\Delta f\) | Entrada `float32` | Espectro `complex64` | Entrada + espectro |
|---:|---:|---:|---:|---:|---:|
| 256 | 32 ms | 31.25 Hz | 1 KiB | 2 KiB | 3 KiB |
| 512 | 64 ms | 15.625 Hz | 2 KiB | 4 KiB | 6 KiB |
| 1024 | 128 ms | 7.8125 Hz | 4 KiB | 8 KiB | 12 KiB |
| 2048 | 256 ms | 3.90625 Hz | 8 KiB | 16 KiB | 24 KiB |

Los valores de memoria anteriores corresponden únicamente al almacenamiento básico de un bloque real `float32` y de un espectro complejo `complex64`. Una biblioteca FFT puede requerir memoria adicional para buffers internos, tablas o estructuras auxiliares.

---

## Compromiso entre resolución, latencia y memoria

Aumentar \(N\) produce una menor separación entre bins:

\[
N\uparrow
\quad\Longrightarrow\quad
\Delta f=\frac{f_s}{N}\downarrow.
\]

Esto mejora la capacidad de distinguir componentes cercanas en frecuencia. Sin embargo, también aumenta la duración del bloque:

\[
T=\frac{N}{f_s},
\]

por lo que el sistema debe acumular muestras durante más tiempo antes de disponer del bloque completo. En una implementación por bloques, esto incrementa la latencia asociada con la adquisición y procesamiento.

Al mismo tiempo, la memoria necesaria crece aproximadamente de forma lineal con \(N\), pues deben almacenarse más muestras y más coeficientes espectrales.

Por lo tanto:

\[
\boxed{
\text{mejor resolución frecuencial}
\Longleftrightarrow
\text{mayor duración de bloque, latencia y memoria}
}
\]

Para \(N=1024\) y \(f_s=8000\) Hz se obtiene un punto de trabajo de 128 ms por bloque y una separación espectral de 7.8125 Hz.

---

## Reproducción numérica

El script

```text
seccion_2_1/src/analizar_2_1.py
```

genera automáticamente la tabla anterior y la guarda en:

```text
seccion_2_1/resultados/tablas/resolucion_frecuencial.csv
```

## Referencias base

- A. V. Oppenheim, A. S. Willsky y S. H. Nawab, *Señales y Sistemas*.
- J. G. Proakis y D. G. Manolakis, *Digital Signal Processing*.
