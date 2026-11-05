# Tarea 1 · 2.4 Reducción espectral mediante FFT/IFFT

Esta sección documenta la entrega del apartado 2.4 de la **Tarea 1**. Los datos de 2.2 se usan como casos de prueba comunes con 2.3; aquí no se implementa el sistema del proyecto grupal.

## Objetivo y datos

La entrada de cada caso es `contaminada` y la referencia de evaluación es `limpia`, ambas tomadas de `seccion_2_2/2_2_generacionsenales/pruebas/caso_*/muestras_exactas.npz`. Los arreglos contienen 8192 muestras exactas, sin cuantización WAV. La frecuencia de muestreo es 8000 Hz. El método no consulta `limpia` para calcular ganancias; el tipo de ruido de los metadatos de 2.2 decide qué método se usa en el informe.

Se usa `N=1024` y `hop=512`, por lo que la separación entre bins es 7.8125 Hz, la duración de un bloque es 128 ms y el solape es 50 %. Los tonos útiles nominales son 300, 700 y 1100 Hz. La banda de 0 a 1200 Hz se usa como referencia para protegerlos, conforme al borde de paso elegido en 2.3. El inicio de rechazo de 1800 Hz y el FIR Kaiser de orden 36 de 2.3 no se imponen al filtro espectral.

## Cadena de procesamiento

```text
contaminada → quitar DC → bloques solapados → ventana √Hann → rFFT
            → estimar piso y aplicar ganancias reales → irFFT → ventana √Hann
            → suma con solapamiento → restaurar DC → salida
```

La ventana √Hann periódica se aplica tanto al análisis como a la síntesis. Su producto es Hann periódica y cumple la suma constante con un salto de `N/2`. Se añade relleno a los extremos y se recorta al tamaño original. Si todas las ganancias son uno, la reconstrucción del caso oficial difiere de la entrada en menos de `4e-16` por muestra.

`rfft/irfft` y las ganancias reales preservan la simetría conjugada. Una comprobación con FFT completa e IFFT dio una parte imaginaria máxima inferior a `3e-16`.

**Requisito de no anular un bin conocido:** `picos` calcula el piso y busca máximos locales en cada bloque de la *entrada contaminada*. El código no recibe 2150 Hz ni contiene el índice de ese bin. Como prueba adicional, se generó una interferencia a 2350 Hz con la misma potencia que la del caso 1 y se ejecutó exactamente la misma configuración: se midieron 59.33 dB de atenuación alrededor de 2350 Hz, frente a 59.33 dB alrededor de 2150 Hz. Esta prueba desplazada valida la adaptación; los resultados principales siguen usando los tres archivos oficiales de 2.2.

## Métodos y selección

| Método | Regla de ganancia | Uso en los casos |
|---|---|---|
| `picos` | Detecta máximos locales que superan seis veces el piso estimado, fuera de 0–1200 Hz; atenúa seis bins a cada lado. | Caso 1, interferencia tonal. |
| `resta` | Aplica `G = clip(1 - 3·piso/abs(X), 0.05, 1)`; protege tonos persistentes detectados en 0–1200 Hz. | Casos 2 y 3, ruido distribuido. |
| `top_k` | Conserva los 12 bins de mayor magnitud por bloque. | Comparación, no elegido. |

El piso se obtiene con la mediana temporal de la magnitud en cada bin y una mediana en frecuencia de 31 bins. Esta última evita que un pico tonal estrecho eleve todo el piso local. Para `resta`, los tonos protegidos deben ser máximos locales al menos 2.5 veces mayores que ese piso y tener una variación relativa entre bloques menor que 0.55; se protege un bin vecino a cada lado. En el caso 3 se detectaron centros en 296.875, 703.125 y 1101.5625 Hz. La detección utiliza únicamente la entrada contaminada.

Los parámetros se fijaron para la evaluación con los tres casos disponibles. El script también ejecuta los tres métodos en cada caso para mostrar sus ventajas y fallos. La selección depende del *tipo* de ruido de 2.2, no de la referencia limpia ni de la posición exacta del bin interferente.

## Resultados de los casos oficiales

| Caso | Ruido de 2.2 | Método elegido | SNR entrada | SNR salida | ΔSNR | MSE | Cambio estimado del tono 1100 Hz |
|---|---|---|---:|---:|---:|---:|---:|
| 1 | Sinusoidal 2150 Hz, 0 dB | `picos` | 0.00 dB | 30.31 dB | +30.31 dB | 0.0000523 | −0.004 dB |
| 2 | Blanco gaussiano, 5 dB | `resta` | 5.00 dB | 20.73 dB | +15.73 dB | 0.0002938 | −0.086 dB |
| 3 | Banda 900–1300 Hz, 3 dB | `resta` | 3.00 dB | 14.67 dB | +11.67 dB | 0.0012516 | +1.033 dB |

En el caso 1, la atenuación medida alrededor de 2150 Hz es 59.33 dB. En el caso 3, la potencia del **error respecto a `limpia`** dentro de 900–1300 Hz se reduce 11.26 dB. El tono de 1100 Hz queda dentro de la misma banda que el ruido: la protección evita atenuarlo fuertemente, pero no permite separar exactamente sus contribuciones. Su ganancia estimada de +1.03 dB incluye el efecto del ruido residual que se proyecta sobre ese tono.

Con la misma configuración, `picos` deja el caso 2 prácticamente igual (5.00 dB) y el caso 3 en 3.00 dB, porque el ruido no es un pico aislado fuera de la banda útil. `resta` deja el caso 1 en 0.14 dB: una interferencia tonal intensa parece señal persistente y no queda bien representada por un piso de ruido de banda ancha. `top_k` obtiene 0.03, 17.75 y 7.93 dB en los casos 1, 2 y 3, respectivamente. Los resultados completos y tiempos de ejecución están en `resultados/resultados_2_4.json` y `resultados/resumen_2_4.csv`.

### Inciso f): compromiso entre reducción de ruido y distorsión útil

En el caso 2 se barrió `alpha` **sin protección tonal** para hacer visible el compromiso. Esta es una prueba de ablación: no sustituye la configuración elegida para el resultado principal. La atenuación fuera de ±20 Hz de los tonos útiles aproxima la reducción de ruido de banda ancha; la ganancia del tono de 1100 Hz se obtiene ajustando seno y coseno contra la referencia. Así se mide por separado cuánto se suprime fuera de los tonos y cuánto se daña una componente útil.

| `alpha` | Atenuación fuera de tonos | SNR salida | Ganancia del tono de 1100 Hz |
|---:|---:|---:|---:|
| 0 | 0.00 dB | 5.00 dB | −0.02 dB |
| 1 | 8.49 dB | 13.08 dB | −1.30 dB |
| 2 | 20.62 dB | 16.94 dB | −2.71 dB |
| 3 | 25.85 dB | 14.74 dB | −4.28 dB |
| 8 | 25.98 dB | 7.64 dB | −15.58 dB |

Al pasar de `alpha=2` a `alpha=8`, se atenúa más energía fuera de los tonos, pero el tono útil cae 12.87 dB adicionales y el SNR empeora 9.30 dB. La protección tonal de la configuración elegida reduce este daño.

## Métricas y comparación con 2.3

Se usa el mismo criterio básico que el script de 2.3: `MSE = mean((limpia - salida)^2)` y `SNR = 10 log10(sum(limpia²)/sum((limpia - salida)²))`. `ΔSNR` resta el SNR de entrada. En 2.4 se calculan sobre las muestras en sus posiciones originales, porque la reconstrucción no desplaza la salida. Para comparar con 2.3, deben usarse sus columnas **sin alinear**; sus cifras alineadas compensan el retardo del FIR/IIR. `energia_salida_respecto_limpia_pct` es energía **total** de salida respecto a la limpia e incluye ruido residual; no equivale a la energía útil conservada. La ganancia de cada tono se informa por separado.

## Limitaciones y condiciones de fallo

- La mediana temporal y la sustracción de DC usan la captura completa. Esta implementación de la Tarea 1 es de evaluación **fuera de línea**; los tiempos medidos en PC no prueban cumplimiento de tiempo real.
- La ventana y el solape requieren conservar bloques y realizar dos FFT por tramo. El bloque dura 128 ms y el resultado depende también del contexto usado para estimar el piso.
- Un tono interferente dentro de la banda protegida podría conservarse. El caso 3 ya muestra el límite de separar señal y ruido superpuestos en 1100 Hz.
- La sustracción fuerte puede producir variación espectral audible y pérdida de tonos; `top_k` puede descartar energía útil distribuida o conservar ruido fuerte.
- Los valores fueron evaluados en los tres archivos oficiales de 2.2. La generalización a otras señales necesita nuevas pruebas.

## Reproducción y fuentes

Ejecutar `python seccion_2_4/pruebas/filtrado_espectral/evaluar_casos.py` desde la raíz. El script guarda las tres salidas elegidas en `resultados/caso_*/salida_filtrada.npz` y regenera JSON y CSV. Las pruebas se ejecutan con `python -m unittest discover -s seccion_2_4/pruebas/filtrado_espectral -p "test_*.py" -v`. Solo se requiere NumPy.

El enunciado de **Tarea 1, apartado 2.4** solicita bloques potencia de dos, simetría, adaptación, solapamiento, los tres casos y un ejemplo del compromiso ruido/distorsión. Esta implementación se contrastó con esos puntos. Para el fundamento de DFT, ventanas y procesamiento por bloques se tomó como referencia el material indicado en el borrador previo del integrante: J. G. Proakis y D. G. Manolakis, *Digital Signal Processing*, Pearson, 2013. La sustracción espectral se relaciona con S. F. Boll, “Suppression of acoustic noise in speech using spectral subtraction,” *IEEE Transactions on Acoustics, Speech, and Signal Processing*, vol. 27, núm. 2, pp. 113–120, 1979. Las mediciones y decisiones numéricas de esta sección proceden del código y los datos del repositorio.

### Declaración de uso de IA

Se usó asistencia de IA para revisar el borrador inicial, reorganizar el módulo, preparar el evaluador y redactar esta documentación. Se suministraron el enunciado de la Tarea 1, el documento del proyecto solo como contexto, el plan de trabajo, el resumen previo de 2.4 y el código y datos de 2.2 y 2.3. Se verificaron los resultados ejecutando el evaluador y las pruebas sobre los tres `muestras_exactas.npz`, además de comprobar la reconstrucción con ganancia unitaria, la simetría conjugada y la respuesta ante una interferencia desplazada.
