# Resultados de 2.5

Resultados generados por el evaluador del paso 4, sin sobrescribir las salidas
de 2.3 o 2.4. Las tablas y figuras fueron preparadas y revisadas en el paso 5.

| Archivo | Contenido |
|---|---|
| `metricas.csv` | Nueve filas principales: tres métodos por cada caso; métricas alineadas, directas, tiempo y memoria identificados por columnas |
| `resultados_2_5.json` | Configuración utilizada, hashes de señales/protocolo/código, resultados completos, entorno, repeticiones de tiempo y notas metodológicas |
| `caso_*/senales_comparacion.npz` | Fuentes exactas, salidas, componentes útiles, ruido residual y ganancias espectrales fijadas desde la mezcla |
| `figuras/` | Seis figuras revisadas, cada una en PNG de 300 dpi y SVG |
| `resumen_2_5.md` | Cuatro tablas de calidad, energía/atenuación, tonos y recursos, y enlaces a las figuras |
| `revision_figuras.json` | Comprobaciones numéricas, revisión visual y hashes de las figuras |

El significado de las métricas y las columnas previstas se define en
`revision/paso_2/criterios_comparacion.md` y `revision/paso_2/protocolo.json`,
relativos a la raíz. No se introducirán cifras de ejemplo como si fueran
mediciones. Los resultados ya verificados de los compañeros
permanecen en sus respectivas secciones.

## Lectura de las métricas

La calidad principal se calcula sobre 8174 muestras comunes, con
compensación de 18 muestras en el FIR. Las columnas `*_directo` utilizan las
8192 muestras originales sin desplazamiento. Por eso los valores espectrales
principales pueden diferir de los de 2.4: por ejemplo, la SNR del caso 1 pasa
de 30.314 dB sobre la captura completa a 32.166 dB en el tramo común. Cambia
el intervalo de evaluación; no se modificó el filtro.

`energia_util_conservada_pct` usa la componente útil obtenida con el operador
condicionado a las ganancias de la mezcla. `energia_total_salida_pct` incluye
ruido residual. El caso 2 no tiene una banda interferente dominante única:
sus columnas de banda quedan vacías en CSV y como `null` en JSON.

Los tiempos son mediciones de PC sobre la captura completa: tres
calentamientos y 30 repeticiones, alternando el orden de los filtros. El
tiempo equivalente por 1024 muestras y el tiempo por trama son amortizados.
El espectral procesa 17 tramas con relleno; el temporal, ocho bloques.

La memoria persistente lógica del FIR genérico suma 592 bytes: 37
coeficientes b, un a, y 36 estados float64. El pico trazado adicional también
incluye la asignación de estados y no se suma directamente a esa columna.
La entrada ocupa 65536 bytes y está fuera del pico trazado. La persistencia
espectral figura como cero porque no hay estados preasignados entre llamadas;
sus ventanas, matrices y ganancias están incluidas en el pico durante la
llamada. Estos números no constituyen un presupuesto de RAM para ESP32.
