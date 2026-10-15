# 2.1(d) Simetría conjugada de la DFT para señales reales

## Propiedad

Si \(x[n]\) es una señal real, su DFT cumple

\[
\boxed{
X[N-k]=X^*[k]
}
\]

para los índices correspondientes.

Esto implica que las componentes de frecuencia positiva y negativa aparecen en pares conjugados.

Para una DFT de longitud par también se cumple que los bins de DC y Nyquist son reales:

\[
X[0]\in\mathbb{R},
\qquad
X[N/2]\in\mathbb{R}.
\]

---

## Verificación numérica

Se utiliza:

\[
f_s=8000\ \text{Hz},
\qquad
N=1024
\]

y una señal real formada por tres tonos:

\[
x[n]
=
\cos\left(2\pi\frac{1000}{8000}n\right)
+
0.5\cos\left(2\pi\frac{625}{8000}n+0.3\right)
+
0.25\cos\left(2\pi\frac{1375}{8000}n-0.5\right).
\]

Después de calcular la FFT se evalúa

\[
\varepsilon_{\mathrm{sim}}
=
\max_k
\left|
X[N-k]-X^*[k]
\right|.
\]

En la ejecución de referencia se obtiene un error del orden de

\[
\varepsilon_{\mathrm{sim}}
\approx
1.4\times10^{-14},
\]

que corresponde únicamente a precisión numérica de punto flotante.

Por tanto, la simetría conjugada queda verificada.

---

## Por qué debe preservarse antes de la IFFT

La IFFT puede escribirse como

\[
x[n]
=
\frac{1}{N}
\sum_{k=0}^{N-1}
X[k]e^{j2\pi kn/N}.
\]

Para que la reconstrucción sea real, las contribuciones de frecuencia positiva y negativa deben combinarse como pares conjugados.

Si se modifica únicamente un miembro del par,

\[
X[k]\neq X^*[N-k],
\]

se rompe la simetría y la IFFT produce, en general, una señal compleja.

---

## Demostración modificando el espectro

En la señal anterior, el tono de 1000 Hz corresponde al bin

\[
k=128.
\]

Se realizan dos pruebas.

### Modificación asimétrica

Se anula únicamente:

\[
X[128]=0
\]

sin modificar su componente conjugada.

En la ejecución de referencia, la parte imaginaria de la IFFT alcanza aproximadamente

\[
\max|\Im\{x[n]\}|
\approx
0.5.
\]

La reconstrucción deja de ser real.

### Modificación simétrica

Se anulan ambos miembros del par:

\[
X[128]=0,
\qquad
X[N-128]=0.
\]

La parte imaginaria residual queda alrededor de

\[
10^{-16},
\]

es decir, únicamente error numérico.

Por lo tanto, cualquier método que modifique el espectro de una señal real antes de aplicar la IFFT debe mantener la simetría conjugada.

---

## Figuras

El script genera:

```text
resultados/figuras/2_1d_simetria_conjugada.png
resultados/figuras/2_1d_ifft_simetria.png
```

La primera muestra el espectro de magnitud en frecuencias positivas y negativas.

La segunda compara la parte imaginaria de la reconstrucción cuando se rompe la simetría y cuando se conserva.

---

## Reproducción

```bash
python3 seccion_2_1/src/analizar_2_1.py
```

## Referencias base

- A. V. Oppenheim, A. S. Willsky y S. H. Nawab, *Señales y Sistemas*.
- J. G. Proakis y D. G. Manolakis, *Digital Signal Processing*.
