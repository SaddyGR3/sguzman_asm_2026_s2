# Paso 1: revisión de los aportes existentes

Fecha de revisión: 12 de octubre de 2026.

**Resultado:** las señales y los algoritmos existentes permiten avanzar a la
comparación común de 2.5. Pasaron las verificaciones numéricas descritas aquí.
Esto no constituye una aprobación de todos los requisitos del informe final.

## Alcance y reproducción

Se revisaron el notebook de 2.2, los ocho scripts de pruebas de 2.3, su
evaluador FIR/IIR, las cuatro pruebas automáticas de 2.4 y los resultados
espectrales guardados. No se modificaron los archivos de los compañeros.

Se creó un entorno local `.venv/`, excluido de Git. Desde la raíz del repositorio:

```bash
uv --cache-dir /tmp/uv-tarea1-cache venv --python python3.12 .venv
uv --cache-dir /tmp/uv-tarea1-cache pip install --python .venv/bin/python -r revision/paso_1/requirements.txt
.venv/bin/python revision/paso_1/verificar_aportes.py
```

Si `.venv/` ya existe con las dependencias, basta con el último comando.
La ejecución comprobada utilizó Python 3.12.14, NumPy 2.5.4, SciPy 1.18.1
y Matplotlib 3.11.2. El verificador usa `assert`: ejecutar sin la opción `-O`.

El verificador ejecuta todas las celdas Python del notebook, en orden, en un
namespace limpio y un directorio temporal. Esta comprobación no incluye el
frontend de Jupyter ni la inspección visual de las figuras. Las señales
regeneradas y otras exportaciones temporales se eliminan al finalizar;
se conservan los registros y `verificacion.json` en esta carpeta.

## 2.2: señales comunes

| Caso | Ruido | Semilla | SNR objetivo | SNR verificada |
|---|---|---:|---:|---:|
| 1 | Interferencia tonal a 2150 Hz | 202601 | 0 dB | 0 dB |
| 2 | Ruido blanco gaussiano | 202602 | 5 dB | 5 dB |
| 3 | Ruido de banda 900–1300 Hz | 202603 | 3 dB | 3 dB |

En todos: `fs = 8000 Hz`, `L = 8192`, duración `1.024 s`, bloque `N = 1024`
y tonos útiles de 300, 700 y 1100 Hz. Las configuraciones generales y los
metadatos individuales coinciden en los parámetros de generación revisados.

Resultados de la comprobación:

- Las diez celdas Python del notebook se ejecutaron correctamente.
- Las señales regeneradas coinciden exactamente con los arreglos NPZ existentes
  en este entorno: error máximo cero en limpia, ruido y contaminada.
- Todos los arreglos tienen la longitud esperada y valores finitos.
- `limpia + ruido = contaminada` con error máximo de `2.22e-16`.
- Los WAV son mono PCM de 16 bits a 8 kHz y coinciden con la cuantización del
  generador. El error máximo de cuantización es inferior a `3.052e-5`.
- Ambos evaluadores cargan exactamente la misma referencia limpia y entrada
  contaminada de los NPZ. Estos serán la base de 2.5.
- El SHA-256 de cada NPZ queda registrado en `verificacion.json` para detectar
  cambios posteriores en las señales.

## 2.3: filtro temporal

Los ocho scripts `test_*.py` terminaron con código cero y sus aserciones pasaron.
Se ejecutaron como programas, porque sus verificaciones están en funciones
invocadas desde `__main__`; `unittest discover` no las ejecuta.

La selección documentada es un FIR pasa bajas Kaiser de orden 36, con 37
coeficientes. El IIR Butterworth de orden 11 se conserva como candidato.
Ambos cumplen las especificaciones de paso y rechazo evaluadas por los scripts.

La implementación manual y su versión por bloques coinciden con
`scipy.signal.lfilter` en los tres casos: error máximo `3.331e-16`, por debajo
de la tolerancia declarada de `1e-12`. Se verifica la continuidad del estado
entre bloques. El retardo estimado del FIR es 18 muestras, equivalente a 2.25 ms.

El evaluador temporal también se ejecutó correctamente. Sus SNR del FIR son:

| Caso | SNR de salida con compensación de retardo | SNR de salida sin compensación |
|---|---:|---:|
| 1 | 51.911 dB | −4.998 dB |
| 2 | 9.524 dB | −5.152 dB |
| 3 | 3.071 dB | −5.667 dB |

Estas cifras describen dos criterios distintos. No deben mezclarse en una
comparación sin explicar el alineamiento y el intervalo de evaluación.

## 2.4: filtro espectral

Las cuatro pruebas automáticas pasaron: reconstrucción y simetría,
mejora en los tres casos, compromiso entre ruido y distorsión, y adaptación
al desplazar la interferencia de 2150 a 2350 Hz.

Se ejecutaron los tres métodos en cada caso con `guardar=False`, sin
sobrescribir los resultados existentes. Las diferencias respecto al JSON
guardado fueron menores que `1e-10` para MSE, SNR y ΔSNR. Las tres salidas NPZ
guardadas coinciden con una ejecución nueva: error máximo `2.22e-16`.

| Caso | Método seleccionado | SNR de salida, sin desplazamiento de la reconstrucción |
|---|---|---:|
| 1 | `picos` | 30.314 dB |
| 2 | `resta` | 20.731 dB |
| 3 | `resta` | 14.670 dB |

La selección usa el tipo de ruido de los metadatos. No se ha demostrado
clasificación automática del tipo de ruido para una entrada desconocida.

## Puntos que deben resolverse al integrar

1. **Alineamiento y longitud de evaluación.** El paso 2 debe definir la
   comparación directa y la compensación conocida del retardo FIR, usando
   intervalos comunes y declarando el tratamiento de los extremos. Las cifras
   anteriores no constituyen todavía una tabla final homogénea de 2.5.
2. **Energía útil.** La función `energia_util_conservada` de 2.4 calcula la
   energía total de salida respecto a la limpia. Incluye ruido residual y no
   equivale a energía útil conservada. Se necesita definir un estimador común.
3. **Procesamiento fuera de línea.** El método espectral usa la captura completa
   para calcular DC, mediana temporal y persistencia tonal. Su reconstrucción
   no desplaza los arreglos, pero eso no implica latencia cero. Para ESP32 se
   deberá proponer una estimación causal y presupuestar su latencia.
4. **Tiempos y memoria.** 2.3 describe memoria de coeficientes y estados; 2.4
   mide tiempo de procesamiento de la captura en PC. Falta una medición común
   por bloque y un presupuesto de memoria que incluya buffers y temporales.
   Los tiempos de PC no validan tiempo real en ESP32.
5. **Notebook integrado.** El notebook actual genera y caracteriza las señales;
   todavía no integra 2.3, 2.4 y 2.5. Sus rutas de salida son relativas al
   directorio de ejecución. En la entrega deben fijarse de manera coherente.
   Tampoco exporta el archivo agregado `metadatos/configuraciones.json`.
6. **Identificación del ruido.** El análisis de 2.2 utiliza el arreglo de ruido
   aislado y el número de caso. Sirve como caracterización de referencia;
   no prueba identificación automática desde la entrada contaminada.
7. **Documentación temporal.** `2_3_filtro_temporal.md` mantiene expresiones
   preliminares como «el diseño definitivo se realizará posteriormente».
   La selección final sí está en `2_3_desarrollo_decisiones.md`; deberá
   consolidarse al preparar el informe.
8. **Figuras.** Se generaron sin ventana gráfica, con backend Agg. Las
   advertencias de `show()` son esperadas. Hay además una leyenda sin etiquetas
   en la figura de fase de 2.2. La revisión visual corresponde a la preparación
   del informe.

No se encontraron fallos numéricos en las comprobaciones ejecutadas. Los puntos
anteriores son pendientes de comparación, propuesta e integración.

## Evidencias

- `verificacion.json`: versiones, hashes, errores y pruebas ejecutadas.
- `notebook_2_2.log`: ejecución de las celdas del notebook.
- `test_*.log`: resultados de cada script temporal.
- `evaluador_temporal.log`: resultados FIR/IIR en los tres casos.
- `pruebas_espectrales.log`: las cuatro pruebas de 2.4.

Se utilizó asistencia de IA para inspeccionar los aportes, crear este verificador
y documentar la revisión. Las afirmaciones numéricas se comprobaron mediante
la ejecución del código y la comparación con los archivos existentes.
