# 2.3 Diseño de filtro temporal FIR/IIR

## Objetivo

El objetivo de esta sección es diseñar e implementar un filtro digital temporal capaz de reducir el ruido presente en una señal muestreada. El filtro recibirá una señal contaminada \(x[n]\) y producirá una salida \(y[n]\) que preserve, en la medida de lo posible, las componentes de la señal útil mientras atenúa las componentes asociadas al ruido.

La ruta de procesamiento puede representarse de forma general como:

\[
x[n] \longrightarrow H(z) \longrightarrow y[n]
\]

donde \(H(z)\) representa la función de transferencia del filtro digital.

El diseño definitivo del filtro se realizará posteriormente a partir de la caracterización espectral de los casos de prueba de la sección 2.2. Por lo tanto, en esta etapa se establece primero la base matemática y la estructura general necesaria para implementar filtros FIR e IIR.

---

## Base teórica

### Sistema LTI discreto

Un filtro digital puede modelarse como un sistema lineal e invariante en el tiempo (LTI). En un sistema LTI, la salida puede expresarse mediante la convolución entre la señal de entrada \(x[n]\) y la respuesta al impulso del sistema \(h[n]\):

\[
y[n] = x[n] * h[n]
\]

o de forma explícita:

\[
y[n]
=
\sum_{k=-\infty}^{\infty}
h[k]x[n-k]
\]

La respuesta al impulso \(h[n]\) caracteriza completamente a un sistema LTI. En el contexto del proyecto, el objetivo consiste en seleccionar una respuesta \(h[n]\), o equivalentemente una función de transferencia \(H(z)\), que permita conservar las frecuencias correspondientes a la señal útil y atenuar las asociadas al ruido.

En el dominio de la frecuencia, la convolución en el tiempo corresponde a una multiplicación:

\[
Y(e^{j\omega})
=
H(e^{j\omega})X(e^{j\omega})
\]

Por esta razón, la respuesta en frecuencia \(H(e^{j\omega})\) permite observar directamente qué componentes frecuenciales serán conservadas, atenuadas o modificadas por el filtro.

---

### Ecuación de diferencias

Los filtros digitales FIR e IIR pueden describirse mediante una ecuación de diferencias lineal con coeficientes constantes.

Una forma general es:

\[
y[n]
=
\sum_{k=0}^{M} b_kx[n-k]
-
\sum_{k=1}^{N} a_ky[n-k]
\]

donde:

- \(x[n]\) es la entrada actual;
- \(y[n]\) es la salida actual;
- \(b_k\) son los coeficientes asociados a la entrada;
- \(a_k\) son los coeficientes asociados a la realimentación;
- \(M\) corresponde al orden asociado al numerador;
- \(N\) corresponde al orden asociado al denominador.

Se considera en esta expresión que:

\[
a_0 = 1
\]

La ecuación de diferencias es especialmente importante desde el punto de vista de implementación, ya que representa las operaciones que deberá ejecutar el procesador digital para calcular cada nueva muestra de salida.

Estas operaciones se reducen principalmente a:

1. almacenar muestras anteriores;
2. multiplicarlas por coeficientes;
3. sumar los resultados;
4. en el caso de filtros recursivos, reutilizar salidas anteriores.

Por lo tanto, el orden del filtro influye directamente en la cantidad de operaciones y memoria necesarias para su implementación.

---

### Filtro FIR

Un filtro FIR, del inglés *Finite Impulse Response*, posee una respuesta al impulso de duración finita.

En un FIR no se utilizan muestras anteriores de la salida para calcular la nueva salida. Su ecuación de diferencias se reduce a:

\[
y[n]
=
\sum_{k=0}^{M} b_kx[n-k]
\]

y su función de transferencia es:

\[
H(z)
=
\sum_{k=0}^{M}b_kz^{-k}
\]

Por ejemplo, un FIR de orden 3 tendría la forma:

\[
y[n]
=
b_0x[n]
+
b_1x[n-1]
+
b_2x[n-2]
+
b_3x[n-3]
\]

Una ventaja importante de los filtros FIR es que pueden diseñarse con fase exactamente lineal. En ese caso, las diferentes componentes frecuenciales de la señal presentan un retardo uniforme, lo cual permite preservar mejor la forma temporal de la señal.

Como desventaja, para obtener una transición frecuencial estrecha o una alta selectividad normalmente se requiere un orden mayor que en un filtro IIR, lo que implica una mayor cantidad de coeficientes, operaciones y elementos de memoria.

---

### Filtro IIR

Un filtro IIR, del inglés *Infinite Impulse Response*, utiliza realimentación. Esto significa que la salida actual depende tanto de muestras de entrada anteriores como de muestras anteriores de la propia salida.

Su ecuación general es:

\[
y[n]
=
\sum_{k=0}^{M} b_kx[n-k]
-
\sum_{k=1}^{N} a_ky[n-k]
\]

Por ejemplo, un sistema de segundo orden puede expresarse como:

\[
y[n]
=
b_0x[n]
+
b_1x[n-1]
+
b_2x[n-2]
-
a_1y[n-1]
-
a_2y[n-2]
\]

La presencia de realimentación permite obtener respuestas frecuenciales selectivas utilizando órdenes relativamente pequeños.

Sin embargo, la realimentación introduce consideraciones adicionales de estabilidad. A diferencia de un FIR no recursivo, en un IIR la ubicación de los polos de la función de transferencia debe analizarse cuidadosamente.

Además, un filtro IIR causal no puede obtener, en general, una fase exactamente lineal de la misma manera que determinados filtros FIR.

Por lo tanto, existe un compromiso entre ambos tipos:

\[
\text{FIR}
\rightarrow
\text{mayor orden, posible fase lineal}
\]

\[
\text{IIR}
\rightarrow
\text{menor orden, realimentación y análisis de estabilidad}
\]

La elección entre FIR e IIR se realizará posteriormente a partir de los requerimientos frecuenciales y de implementación del proyecto.

---

### Función de transferencia \(H(z)\)

La transformada \(z\) permite convertir la ecuación de diferencias de un sistema LTI discreto en una relación algebraica.

Partiendo de:

\[
y[n]
=
\sum_{k=0}^{M} b_kx[n-k]
-
\sum_{k=1}^{N} a_ky[n-k]
\]

y aplicando transformada \(z\), bajo condiciones iniciales nulas:

\[
Y(z)
=
\left(
\sum_{k=0}^{M}b_kz^{-k}
\right)X(z)
-
\left(
\sum_{k=1}^{N}a_kz^{-k}
\right)Y(z)
\]

Agrupando los términos asociados a \(Y(z)\):

\[
Y(z)
\left(
1+\sum_{k=1}^{N}a_kz^{-k}
\right)
=
X(z)
\left(
\sum_{k=0}^{M}b_kz^{-k}
\right)
\]

La función de transferencia se define como:

\[
H(z)
=
\frac{Y(z)}{X(z)}
\]

por lo que finalmente:

\[
\boxed{
H(z)
=
\frac{
\displaystyle\sum_{k=0}^{M}b_kz^{-k}
}{
\displaystyle1+\sum_{k=1}^{N}a_kz^{-k}
}
}
\]

Esta relación conecta directamente los coeficientes utilizados en la implementación con la descripción matemática del filtro.

Por lo tanto:

\[
\text{coeficientes } a_k,b_k
\longleftrightarrow
\text{ecuación de diferencias}
\longleftrightarrow
H(z)
\]

A partir de \(H(z)\) se pueden determinar posteriormente:

- polos;
- ceros;
- región de convergencia;
- estabilidad;
- respuesta en magnitud;
- respuesta en fase;
- retardo de grupo.

Estas propiedades permitirán verificar que el filtro diseñado cumple tanto con los requerimientos frecuenciales como con las condiciones necesarias para su implementación en el sistema embebido.

---

### Relación con la implementación del proyecto

Aunque el diseño del filtro puede realizarse inicialmente mediante herramientas de software, el filtro temporal finalmente deberá ejecutarse muestra por muestra en el sistema embebido.

El flujo general será:

\[
x[n]
\rightarrow
\text{ecuación de diferencias}
\rightarrow
y[n]
\]

Los coeficientes \(a_k\) y \(b_k\) obtenidos durante el diseño serán almacenados en el microcontrolador. Además, será necesario almacenar las muestras anteriores requeridas por la ecuación de diferencias.

En un FIR será necesario conservar principalmente muestras anteriores de la entrada:

\[
x[n-1],x[n-2],\ldots,x[n-M]
\]

mientras que un IIR requiere además conservar estados relacionados con las salidas anteriores:

\[
y[n-1],y[n-2],\ldots,y[n-N]
\]

Por esta razón, además del comportamiento frecuencial, la selección final deberá considerar orden del filtro, cantidad de coeficientes, memoria, número de operaciones, precisión numérica y posibles efectos de cuantización.

La elección definitiva entre FIR e IIR, así como el tipo de respuesta requerida —pasa bajas, pasa altas, pasa banda o rechazo de banda— se realizará a partir de los espectros obtenidos en la sección 2.2.