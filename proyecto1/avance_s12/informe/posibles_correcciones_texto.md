# Posibles correcciones de consistencia del informe

Revisión del 30 de octubre de 2026 de `informe.tex`. Las siguientes propuestas no se han aplicado al LaTeX. Los números de línea corresponden a la versión revisada y pueden cambiar al editar el documento.

## 1. Banda del sistema y banda protegida

**Ubicación:** discusión, línea 235.

**Texto actual:** «Con ruido fuera de la banda útil (P1, P2) las dos rutas mejoran la SNR».

**Problema:** las interferencias de P1 (2150 Hz) y P2 (2000–2800 Hz) están dentro de la banda del sistema de 100–3000 Hz, pero fuera de las respectivas bandas protegidas.

**Propuesta:**

> Con ruido fuera de la banda protegida (P1, P2), las dos rutas mejoran la SNR.

## 2. Definición de la señal útil filtrada

**Ubicación:** comparación de las rutas, línea 159.

**Texto actual:** «Con $y$ la salida de una ruta, $y_s$ la misma ruta aplicada solo a $s_8$ y $r = x_8 - s_8$».

**Problema:** en el nodo 3, el código aplica a la referencia limpia las ganancias calculadas con la mezcla contaminada. La descripción actual puede interpretarse como una ejecución independiente del estimador sobre la señal limpia, que produciría ganancias diferentes.

**Propuesta para el LaTeX:**

```latex
Con $y$ la salida de una ruta y $r = x_8 - s_8$, se define $y_s$ como
la salida del mismo filtro aplicado a $s_8$. En el nodo 3 se reutilizan
las ganancias por trama y bin calculadas a partir de $x_8$, sin volver
a estimarlas con la referencia limpia.
```

**Base de la revisión:** `simulacion/sim/comparacion.py`, función `correr_caso`, y `simulacion/sim/nodo3.py`, función `aplicar_ganancias`.

## 3. Alcance de los resultados de simulación

**Ubicación:** discusión, línea 241.

**Texto actual:** «Los resultados son de simulación: la calibración del ADC se supone ideal…».

**Problema:** el informe también presenta mediciones físicas del emisor. La frase generaliza el origen de todos los resultados.

**Propuesta:**

> Los resultados de comparación de las rutas son de simulación: la calibración del ADC se supone ideal…

El resto del párrafo puede mantenerse.

## 4. Ausencia de errores e incidencia durante el reinicio

**Ubicación:** resumen, línea 33, y conclusiones, línea 247; contrastar con la tabla de validación y su explicación en las líneas 222–230.

**Texto actual de la conclusión:** «El emisor funciona en la placa y transmite por los dos enlaces sin errores ni pérdidas, incluso tras un reinicio».

**Problema:** la tabla registra una incidencia de transición durante el reinicio. Aunque el texto explica que se excluye del veredicto, la afirmación absoluta puede parecer contradictoria.

**Propuesta para la conclusión:**

> El emisor funciona en la placa y transmite por los dos enlaces sin errores computables en el veredicto ni pérdidas de secuencia. Durante el reinicio se registró una incidencia de transición de sesión, tras la cual se recuperó la recepción desde el primer paquete de la nueva sesión.

**Propuesta para el cierre del resumen:**

> El emisor funciona en un ESP32 y un receptor independiente en la PC verifica los enlaces sin errores computables en el veredicto ni pérdidas de secuencia; la incidencia de transición durante el reinicio se contabiliza por separado.

## 5. Configuraciones del barrido de P5

**Ubicación:** plan de frecuencias, línea 86.

**Texto actual:** «P5 barre 4 niveles de agresividad para mostrar el compromiso entre quitar ruido y distorsionar la señal».

**Problema:** hay tres niveles de agresividad y una configuración de referencia. Esta última repite los parámetros del nivel medio y activa la protección de tonos en el nodo 3.

**Propuesta para el LaTeX:**

```latex
P5 compara tres niveles de agresividad y una configuración de referencia
para mostrar el compromiso entre quitar ruido y distorsionar la señal.
La referencia mantiene $Q=2.75$ y $\alpha=3$, como el nivel medio,
y activa la protección de tonos en el nodo 3.
```

**Base de la revisión:** `simulacion/config/pruebas.json`, barrido de P5.

## 6. Frecuencias indicadas en la tabla de filtros

**Ubicación:** tabla de pruebas P1–P5, líneas 90–92; contrastar con el diseño FIR de la línea 134.

**Texto actual:** «FIR pasa bajas 1200 Hz» en P2 y P4, y «FIR pasa bajas 3000 Hz» en P3.

**Problema:** las frecuencias pueden interpretarse como cortes del filtro. En el diseño implementado corresponden a los bordes superiores de las bandas protegidas. Con una transición de 600 Hz, los cortes de la sinc están 300 Hz por encima: 1500 y 3300 Hz, respectivamente.

**Propuesta para las celdas de la tabla:**

- P2 y P4: «FIR (banda protegida 100–1200 Hz)».
- P3: «FIR (banda protegida 100–3000 Hz)».

**Propuesta de aclaración en el texto del diseño FIR:**

> Para las bandas protegidas de 100–1200 Hz y 100–3000 Hz, los cortes de la sinc son 1500 Hz y 3300 Hz, respectivamente; estos valores corresponden al centro de la transición superior.

**Base de la revisión:** `simulacion/sim/nodo2.py`, función `fir_banda_protegida`, y `simulacion/config/nodo2.json`.

## 7. Atenuaciones y retardos del modelo

**Ubicación:** cadena analógica, línea 97.

**Texto actual:** «La simulación incluye el hardware de entrada y salida para trabajar con las atenuaciones y retardos reales».

**Problema:** se simulan modelos de los circuitos; sus resultados todavía no equivalen a mediciones del hardware físico.

**Propuesta:**

> La simulación incluye modelos de los circuitos de entrada y salida para considerar las atenuaciones y los retardos previstos por el diseño.

