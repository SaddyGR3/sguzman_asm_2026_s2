# 2.1(a) Relación entre Serie de Fourier, Transformada de Fourier, DFT y FFT

## Idea general

El análisis de Fourier permite representar señales mediante combinaciones de exponenciales complejas o, de forma equivalente, mediante senos y cosenos. En este marco, la **Serie de Fourier**, la **Transformada de Fourier** y la **Transformada Discreta de Fourier (DFT)** son representaciones matemáticas en frecuencia, mientras que la **Fast Fourier Transform (FFT)** es un algoritmo eficiente para calcular la DFT.

La relación conceptual que se utilizará en este trabajo es:

\[
\boxed{\text{Serie de Fourier}}
\rightarrow
\boxed{\text{Transformada de Fourier}}
\rightarrow
\boxed{\text{DFT}}
\]

mientras que la FFT se ubica en un nivel computacional:

\[
\boxed{\text{DFT}}
\overset{\text{algoritmo de cálculo}}{\longleftarrow}
\boxed{\text{FFT}}
\]

---

## Serie de Fourier

Para una señal periódica continua \(x(t)\), con período fundamental \(T_0\), la representación compleja mediante Serie de Fourier puede escribirse como

\[
x(t)=\sum_{k=-\infty}^{\infty} C_k e^{jk\omega_0t},
\]

donde

\[
\omega_0=\frac{2\pi}{T_0}.
\]

Los coeficientes \(C_k\) determinan la contribución de cada componente armónica.

La característica principal es que, debido a la periodicidad temporal, las componentes espectrales aparecen únicamente en frecuencias discretas

\[
\omega=k\omega_0.
\]

Por tanto,

\[
\boxed{\text{periodicidad en tiempo}
\Rightarrow
\text{líneas discretas en frecuencia}}
\]

Oppenheim presenta la Serie de Fourier como una representación de señales periódicas basada en exponenciales complejas y posteriormente extiende el mismo marco al análisis de señales aperiódicas mediante la Transformada de Fourier.

Además, para una señal periódica, su Transformada de Fourier puede interpretarse como un tren de impulsos en las frecuencias armónicas, cuyos pesos están relacionados directamente con los coeficientes de la Serie de Fourier.

---

## Transformada de Fourier

La Transformada de Fourier extiende el análisis frecuencial a señales aperiódicas. Adoptando la convención

\[
X(\omega)=
\int_{-\infty}^{\infty}
x(t)e^{-j\omega t}\,dt,
\]

la transformada inversa es

\[
x(t)=
\frac{1}{2\pi}
\int_{-\infty}^{\infty}
X(\omega)e^{j\omega t}\,d\omega.
\]

Mientras que la Serie de Fourier produce componentes en frecuencias armónicas discretas, la Transformada de Fourier permite una representación continua en frecuencia.

La diferencia conceptual puede resumirse así:

| Serie de Fourier | Transformada de Fourier |
|---|---|
| Señales periódicas | Señales aperiódicas |
| Frecuencias discretas | Frecuencia continua |
| Suma de armónicos | Integral sobre frecuencia |

Oppenheim también muestra una relación inversa entre extensión temporal y separación frecuencial: al aumentar el período de una señal periódica, disminuye la separación entre sus líneas espectrales. Esto permite interpretar intuitivamente la transición entre una representación discreta en frecuencia y una representación continua.

Kreyszig presenta esta misma transición dentro del desarrollo matemático de las series, integrales y transformadas de Fourier.

---

## Del tiempo continuo al tiempo discreto

En procesamiento digital, la señal continua \(x(t)\) se observa mediante muestras

\[
x[n]=x(nT_s),
\]

donde

\[
T_s=\frac{1}{f_s}
\]

es el período de muestreo y \(f_s\) es la frecuencia de muestreo.

En una computadora o microcontrolador normalmente no se dispone de una secuencia infinita, sino de un bloque finito de \(N\) muestras:

\[
x[0],x[1],\ldots,x[N-1].
\]

En este escenario se utiliza la DFT.

---

## Transformada Discreta de Fourier (DFT)

Para un bloque de \(N\) muestras, la DFT se define como

\[
X[k]=
\sum_{n=0}^{N-1}
x[n]e^{-j2\pi kn/N},
\qquad
k=0,1,\ldots,N-1.
\]

La transformada inversa es

\[
x[n]=
\frac{1}{N}
\sum_{k=0}^{N-1}
X[k]e^{j2\pi kn/N}.
\]

De esta forma,

\[
\boxed{
x[n]
\overset{\mathrm{DFT}}{\longleftrightarrow}
X[k]
}
\]

Cada coeficiente \(X[k]\) es complejo y puede escribirse como

\[
X[k]=|X[k]|e^{j\phi[k]},
\]

donde \(|X[k]|\) representa la magnitud y

\[
\phi[k]=\arg\{X[k]\}
\]

representa la fase.

Proakis y Manolakis muestran que los coeficientes de la Serie de Fourier de una secuencia periódica de período \(N\) presentan la misma estructura matemática de una DFT. También relacionan los coeficientes de la DFT con muestras igualmente espaciadas de la representación en frecuencia.

Para un bloque muestreado a frecuencia \(f_s\), las frecuencias asociadas con los bins de la DFT son

\[
f_k=k\frac{f_s}{N}.
\]

Por tanto, la separación entre bins es

\[
\Delta f=\frac{f_s}{N}.
\]

Esta relación será desarrollada con mayor detalle en el inciso 2.1(b).

---

## DFT y representación espectral de un bloque

La DFT no implica que la señal física solamente pueda contener frecuencias iguales a los bins \(f_k\). La DFT proporciona una representación discreta del contenido frecuencial del bloque observado.

Esto será importante cuando se comparen:

- un tono cuya frecuencia coincida exactamente con un bin de la DFT;
- un tono cuya frecuencia quede entre dos bins.

La diferencia entre ambos casos permitirá estudiar posteriormente la fuga espectral.

---

## Fast Fourier Transform (FFT)

La FFT no es una transformación matemática distinta de la DFT.

La transformación que se desea calcular sigue siendo

\[
X[k]=
\sum_{n=0}^{N-1}
x[n]e^{-j2\pi kn/N}.
\]

La diferencia se encuentra únicamente en la estrategia de cálculo.

Si la DFT se evalúa directamente, deben calcularse \(N\) coeficientes y cada uno requiere operaciones sobre \(N\) muestras. Por ello, el costo computacional crece aproximadamente como

\[
O(N^2).
\]

Oppenheim utiliza la evaluación directa de la DFT para introducir el principio en el que se basa la FFT, mostrando que una DFT de longitud \(N\) puede descomponerse en DFT de menor longitud.

Los algoritmos FFT explotan simetrías y periodicidades de las exponenciales complejas para reducir la cantidad de operaciones. En términos generales,

\[
\text{DFT directa}\sim O(N^2)
\]

mientras que una FFT típica presenta un costo aproximado de

\[
\text{FFT}\sim O(N\log_2N).
\]

Proakis y Manolakis describen explícitamente los algoritmos FFT como métodos computacionalmente eficientes para calcular la DFT y la IDFT.

Por lo tanto,

\[
\boxed{\text{DFT}=\text{transformación matemática}}
\]

mientras que

\[
\boxed{\text{FFT}=\text{algoritmo eficiente para calcular la DFT}}
\]

Una FFT aplicada correctamente al mismo bloque debe producir los mismos coeficientes \(X[k]\) que el cálculo directo de la DFT, salvo pequeñas diferencias asociadas a la precisión numérica.

---

## Ejemplo numérico: DFT directa frente a FFT

Para complementar la relación teórica entre DFT y FFT se utiliza un bloque pequeño de \(N=32\) muestras. La señal de prueba es

\[
x[n]
=
\cos\left(2\pi\frac{3}{32}n\right)
+
0.5\cos\left(2\pi\frac{7}{32}n+0.4\right).
\]

La DFT se calcula directamente a partir de su definición:

\[
X[k]
=
\sum_{n=0}^{N-1}
x[n]e^{-j2\pi kn/N},
\]

y se compara con `numpy.fft.fft`, que utiliza un algoritmo FFT.

El script `../src/analizar_2_1.py` realiza ambas operaciones y calcula

\[
\varepsilon_{\max}
=
\max_k
\left|
X_{\mathrm{DFT}}[k]
-
X_{\mathrm{FFT}}[k]
\right|.
\]

En la ejecución de referencia se obtuvo un error máximo del orden de

\[
\varepsilon_{\max}\approx 6\times10^{-14},
\]

por lo que ambas implementaciones producen, dentro de la precisión numérica de punto flotante, los mismos coeficientes espectrales.

Este resultado demuestra numéricamente la diferencia conceptual indicada anteriormente: la DFT es la transformación matemática que se desea calcular, mientras que la FFT es un algoritmo eficiente para obtener esa misma DFT.


---

## Relación completa

La relación entre los conceptos puede resumirse como

\[
\text{Serie de Fourier}
\rightarrow
\text{Transformada de Fourier}
\rightarrow
\text{representación de señales muestreadas}
\rightarrow
\text{DFT}.
\]

Desde el punto de vista computacional,

\[
\text{señal}
\overset{\text{DFT}}{\longrightarrow}
X[k]
\]

y el mismo resultado puede calcularse eficientemente mediante

\[
\text{señal}
\overset{\text{FFT}}{\longrightarrow}
X[k].
\]

En consecuencia, la Serie de Fourier, la Transformada de Fourier y la DFT describen representaciones frecuenciales, mientras que la FFT describe una estrategia eficiente de cálculo de la DFT.

---

## Referencias base

- A. V. Oppenheim, A. S. Willsky y S. H. Nawab, *Señales y Sistemas*, 2.ª ed. Capítulos 3, 4 y 5.
- J. G. Proakis y D. G. Manolakis, *Digital Signal Processing*. Secciones sobre DFT, relación con otras transformadas y algoritmos FFT.
- E. Kreyszig, *Advanced Engineering Mathematics*, 6.ª ed. Capítulo sobre series, integrales y Transformada de Fourier.

> **Nota:** este documento corresponde al inciso 2.1(a). La demostración numérica se reproduce con `../src/analizar_2_1.py`; los incisos 2.1(b), 2.1(c) y 2.1(d) se documentan en archivos separados dentro de esta misma carpeta.
