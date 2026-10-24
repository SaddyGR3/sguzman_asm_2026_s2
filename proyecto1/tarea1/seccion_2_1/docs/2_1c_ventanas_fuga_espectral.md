# 2.1(c) Bin exacto, fuga espectral y ventanas

## Configuración

Se utilizan:

\[
f_s=8000\ \text{Hz},
\qquad
N=1024,
\qquad
\Delta f=\frac{8000}{1024}=7.8125\ \text{Hz}.
\]

Se comparan dos tonos de amplitud unitaria.

### Tono alineado con un bin

Se selecciona

\[
k_0=128.
\]

Por lo tanto,

\[
f_0=k_0\Delta f
=128(7.8125)
=\boxed{1000\ \text{Hz}}.
\]

Este tono coincide exactamente con un bin de la DFT.

### Tono entre dos bins

Para ubicar el segundo tono exactamente a mitad de camino entre los bins 128 y 129 se utiliza

\[
k=128.5,
\]

de donde

\[
f_{\mathrm{off}}
=
128.5(7.8125)
=
\boxed{1003.90625\ \text{Hz}}.
\]

---

## Ventanas utilizadas

### Ventana rectangular

\[
w_R[n]=1.
\]

Equivale a observar directamente el bloque de \(N\) muestras.

La ventana rectangular presenta un lóbulo principal estrecho, pero lóbulos laterales relativamente altos. Su primer lóbulo lateral se encuentra aproximadamente 13 dB por debajo del máximo.

Para un tono centrado en un bin, la DFT puede concentrar idealmente la energía en el bin correspondiente. Cuando el tono queda entre bins, la discontinuidad entre extremos del bloque provoca que la energía se distribuya sobre numerosos bins.

### Ventana Hann

La ventana Hann utilizada se expresa como

\[
w_H[n]
=
\frac{1}{2}
\left(
1-\cos\left(\frac{2\pi n}{N-1}\right)
\right).
\]

La Hann reduce progresivamente los extremos del bloque y disminuye los lóbulos laterales. Su primer lóbulo lateral se encuentra aproximadamente 31 dB por debajo del máximo.

El costo es un lóbulo principal más ancho.

---

## Comparación del ancho del lóbulo principal

En términos aproximados de distancia entre los primeros nulos:

### Rectangular

\[
B_R\approx 2\Delta f
=
15.625\ \text{Hz}.
\]

### Hann

\[
B_H\approx 4\Delta f
=
31.25\ \text{Hz}.
\]

Por lo tanto, la Hann reduce la fuga lejana pero disminuye la capacidad de separar componentes extremadamente próximas debido a su lóbulo principal más ancho.

---

## Interpretación del tono alineado

Para \(f_0=1000\) Hz con ventana rectangular, el tono completa un número entero de ciclos dentro del bloque. La periodicidad implícita de la DFT no introduce una discontinuidad importante entre el final y el comienzo de la extensión periódica, y la energía queda concentrada en el bin correspondiente.

Con Hann, aun cuando el tono esté centrado en un bin, la multiplicación por la ventana modifica el espectro: el lóbulo principal se ensancha y aparece energía en bins vecinos, pero los lóbulos laterales se reducen notablemente.

---

## Interpretación del tono entre bins

Para \(f_{\mathrm{off}}=1003.90625\) Hz el bloque ya no contiene un número entero de ciclos. Al interpretarse periódicamente el bloque, existe una discontinuidad entre sus extremos.

Con ventana rectangular esto produce una fuga espectral marcada: la energía del tono se distribuye sobre muchos bins.

La ventana Hann reduce la discontinuidad en los extremos y, por tanto, reduce los lóbulos laterales. La energía queda más concentrada alrededor de la frecuencia del tono, aunque el lóbulo principal sea más ancho.

Esto muestra el compromiso:

\[
\boxed{
\text{Rectangular}
\rightarrow
\text{lóbulo principal estrecho, lóbulos laterales altos}
}
\]

\[
\boxed{
\text{Hann}
\rightarrow
\text{lóbulo principal más ancho, lóbulos laterales menores}
}
\]

---

## Magnitud y fase

El script genera las gráficas:

```text
resultados/figuras/2_1c_magnitud.png
resultados/figuras/2_1c_fase.png
```

En la gráfica de magnitud se normaliza cada espectro respecto a su máximo para comparar directamente la fuga espectral.

La fase solamente se muestra en bins cuya magnitud supera un umbral, ya que en bins con energía prácticamente nula la fase deja de tener una interpretación útil y se vuelve numéricamente sensible.

---

## Reproducción

Ejecutar:

```bash
python3 seccion_2_1/src/analizar_2_1.py
```

## Referencias base

- A. V. Oppenheim, A. S. Willsky y S. H. Nawab, *Señales y Sistemas*.
- J. G. Proakis y D. G. Manolakis, *Digital Signal Processing*.
