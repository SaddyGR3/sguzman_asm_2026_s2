# Paso 6: elección de métodos y condiciones de fallo

El análisis está integrado en
[la documentación de 2.5](../../seccion_2_5/docs/2_5_comparacion_propuesta.md).
Su criterio de elección es menor MSE y mayor SNR sobre las mismas 8174
muestras, con compensación de las 18 muestras del FIR.

## Resultado

- Caso 1: FIR; ventaja de 19.745 dB de SNR frente al espectral.
- Caso 2: resta espectral con protección tonal; ventaja de 11.290 dB.
- Caso 3: resta espectral con protección tonal; ventaja de 11.606 dB.

Se explican separación y superposición de bandas, conservación útil frente
a energía total, reducción frente a distorsión, retardo real y límites del
benchmark de PC. Las condiciones medidas se distinguen de los riesgos que
requieren pruebas adicionales. Se incorpora el experimento de 2.4 sin
protección tonal, indicando su intervalo y configuración distintos.

## Reproducción de las derivaciones

Desde la raíz del repositorio:

```bash
.venv/bin/python revision/paso_6/derivar_analisis.py
```

El script lee el CSV y las salidas NPZ guardadas, contrasta sus MSE,
comprueba la descomposición útil/ruido y calcula diferencias de SNR y
razones de MSE. También registra un diagnóstico exploratorio de error
en las primeras y últimas 512 muestras del intervalo común. Esas muestras
siguen incluidas en la comparación principal. No se ejecutan filtros,
se ajustan parámetros ni se repite el benchmark.

[analisis_datos.json](analisis_datos.json) registra números sin redondear,
la configuración del diagnóstico y SHA-256 de todas las fuentes numéricas.
Su registro de distorsión, ruido y término cruzado permite comprobar la
identidad del MSE. El diagnóstico de extremos es posterior a la evaluación
y no demuestra por sí solo una causa específica del error.

## Fuentes y verificación

Se consultaron las secciones de linealidad y filtrado de Oppenheim,
Willsky y Nawab (PDF, páginas 76 y 251–254), y la sección 5.4.1 de
Proakis y Manolakis (página impresa 327 / PDF 347). Las referencias y
enlaces están en la documentación de 2.5. Las cifras principales proceden
de los resultados del paso 4, ya contrastados y revisados en el paso 5.

La propuesta causal para ESP32, las bibliotecas, la arquitectura de nodos
y la integración LaTeX continúan en los pasos 7–10. No se modificaron
las fuentes de los compañeros, las métricas ni las figuras.
