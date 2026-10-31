# Simulación del sistema de reducción de ruido

## Propósito

Simulación en Python del sistema de tres ESP32 conectados por UART (CE1110, Análisis de Señales Mixtas). Esta base contiene:

- el **protocolo** binario entre nodos (`sim/protocolo.py`);
- el **banco de señales** de las pruebas P1–P5 (`sim/senales.py`), que genera WAV estéreo (canal izquierdo = x, canal derecho = s) para que la PC los reproduzca hacia el nodo 1;
- la **configuración** de las pruebas (`config/pruebas.json`).

Parámetros: fs = 8000 Hz, N = 1024, H = 512, float32 en transporte, señal normalizada en [−1, 1).

## Instalación del entorno

Requisito: Python 3.14.

1. Crear el entorno virtual **fuera del repositorio**, para no subirlo:

   ```
   python3.14 -m venv ~/venvs/asm
   source ~/venvs/asm/bin/activate
   ```

   En Windows: `py -3.14 -m venv %USERPROFILE%\venvs\asm` y `%USERPROFILE%\venvs\asm\Scripts\activate`.

2. Instalar las dependencias, desde `proyecto1/simulacion/`:

   ```
   pip install -r requirements.txt
   ```

   Las versiones de numpy, scipy y pytest están fijadas en `requirements.txt`; no se cambian sin acordarlo con el grupo.

3. Activar el entorno en cada terminal nueva.
4. En VS Code, seleccionar el intérprete del entorno: `Python: Select Interpreter` → `~/venvs/asm/bin/python`.
5. Verificación rápida: `python -m pytest pruebas` debe pasar todas las pruebas.

## Orden de uso

Desde esta carpeta, con el entorno activo:

```
python -m pytest pruebas     # comprueba que todo funciona
python -m sim.senales        # genera las señales de P1–P5
python -m sim.analogico      # genera los coeficientes del FIR de decimación
python -m sim.nodo2          # muestra los filtros del nodo 2 para P1–P5
```

Cada comando se explica en su sección más abajo.

## Estructura

```
config/pruebas.json     configuración de las pruebas (único lugar con valores numéricos)
sim/protocolo.py        paquetes, COBS, CRC-32, DIAG y CONTROL
sim/senales.py          generación de las señales de P1–P5
pruebas/                pruebas con pytest
senales/                salida de la generación (valor por defecto de global.carpeta_salida)
config/cadena_analogica.json  parámetros de hardware de la cadena analógica (único lugar con esos valores)
sim/analogico.py        modelo de la cadena analógica de entrada (nodo 1) y de salida (nodos 2 y 3)
resultados/decimacion.json  coeficientes del FIR de decimación y sus métricas, generados por sim/analogico.py
config/nodo2.json       parámetros del filtrado del nodo 2 (FIR de la banda protegida y Q del notch automático)
sim/nodo2.py            FIR de la banda protegida, notch IIR, polos y ceros, y filtrado por bloques con estado
config/nodo3.json       historial, umbrales, ganancias y tramo de evaluación del nodo 3
sim/nodo3.py            FFT/IFFT causal por bloques y reconstrucción con solape
sim/metricas.py         MSE, SNR, energía útil, atenuación y ganancia de tonos
sim/comparacion.py      P1–P5 por tres semillas, comparación y figuras
resultados/comparacion.csv          métricas por corrida y ruta, generadas por sim.comparacion
resultados/comparacion_resumen.csv  medias y desviaciones, generadas por sim.comparacion
resultados/figuras/P1.png–P5.png   comparación temporal y espectral, generada por sim.comparacion
sim/dft.py             DFT por frecuencia desde su definición y comparación con FFT
sim/costo.py           estimación de multiplicaciones, memoria y latencia por método
resultados/dft_fft.json  errores, tiempos y operaciones, generados por sim.dft
resultados/costo.csv     cinco filas de costo, memoria y latencia, generadas por sim.costo
sim/informe.py           punto de entrada para regenerar las tablas y figuras del informe
resultados/figuras/nodo2_polos_ceros.png  plano z, ROC causal y estabilidad del FIR y notch
resultados/figuras/nodo2_respuesta.png   magnitud y fase de los filtros del nodo 2
resultados/figuras/cadena_analogica.png  entrada, decimación y reconstrucción analógica
resultados/figuras/dft_fft.png           espectros DFT/FFT y diferencia numérica
```

## Generar las señales

Desde esta carpeta:

```
python -m sim.senales
```

Crea `senales/P<p>/<semilla>/` con `entrada_estereo.wav`, `muestras.npz` y `metadatos.json`. Los WAV se suben al repositorio; los `.npz` no, porque se regeneran.

## Correr las pruebas

Desde esta carpeta:

```
python -m pytest pruebas
```

## Cadena analógica

`sim/analogico.py` modela el hardware entre la PC y las muestras a 8 kHz, y entre las muestras y el parlante:

- **Entrada (nodo 1):** PC → acople → Sallen-Key → ADC a 24 kHz (12 bits, 0.15–2.45 V) → FIR de decimación ÷3 → 8 kHz.
- **Salida (nodos 2 y 3):** DAC de 8 bits → retención de orden cero → Sallen-Key.
- **x y s pasan por la misma cadena** de entrada, con el mismo retardo y la misma atenuación.

Los parámetros están en `config/cadena_analogica.json`. Para generar los coeficientes del FIR de decimación (fuente para el firmware del nodo 1), desde esta carpeta:

```
python -m sim.analogico
```

Crea `resultados/decimacion.json`, que sí se sube al repositorio.

## Limitaciones del modelo

La calibración del ADC se supone ideal e ignora la alinealidad real del ADC del ESP32, y el paso de cuantización de 3.3 V/4096 es un supuesto levemente pesimista. Ambos se verifican en la placa en la fase 4.

## Nodo 2 (filtrado temporal)

`sim/nodo2.py` modela los dos filtros del nodo 2:

- **FIR de la banda protegida:** Kaiser de 37 coeficientes con transición de 600 Hz. Es pasa bajas o pasa banda según el borde inferior de la banda. Se calcula con la fórmula explícita (sinc por ventana de Kaiser), igual que en la placa, y se valida contra `firwin`.
- **Notch IIR de 2.º orden:** con sus polos, ceros y región de convergencia (ROC). En P1 usa la Q automática de `config/nodo2.json`; en P5 se barre la Q.
- **Aplicación por bloques:** se filtra en bloques de 512 muestras conservando el estado entre bloques.

Para ver el resumen de los filtros de P1 a P5, desde esta carpeta:

```
python -m sim.nodo2
```

## Nota

El código marcado como "Origen: Tarea 1" se copió de `proyecto1/tarea1/`.

## Nodo 3 y comparación

`sim/nodo3.py` recibe la misma señal `x8` que el nodo 2. Trabaja a 8 kHz con
tramas de **N = 1024** muestras y avance **H = 512**: aplica raíz de Hann antes
de la FFT y después de la IFFT, y suma las mitades solapadas. La ganancia real
por bin conserva la simetría conjugada, por lo que la salida es real. El método
de **picos** detecta interferencias tonales fuera de la banda útil; el de
**resta** reduce un piso espectral y puede proteger tonos estables. El piso se
estima con la mediana de las últimas ocho tramas reales y se suaviza con una
mediana de 31 bins. Durante el calentamiento se usa ganancia 1. Ninguna decisión
usa tramas futuras.

`config/nodo3.json` reúne los parámetros para ajustar el método sin cambiar
el algoritmo:

| Campo | Función |
|---|---|
| `historial_tramas: 8`, `suavizado_bins: 31` | Medianas temporal y frecuencial del piso de ruido |
| `picos` | Umbral de detección, seis bins vecinos y atenuación de 60 dB |
| `resta` | Intensidad inicial α = 3 y ganancia mínima 0.05 |
| `proteccion_tonos` | Identifica tonos estables dentro de la banda útil y deja su ganancia en 1 |
| `evaluacion` | Intervalo de 1 a 9 s usado por las métricas |

La salida en flujo corresponde al bloque de entrada anterior: su retardo
algorítmico es **512 muestras (64 ms)**. Las métricas se calculan entre 1 y 9 s
contra `s8`, la referencia limpia que pasó por la misma cadena de entrada que
`x8`. Se compensan solo los retardos propios de las rutas: **18 muestras** en
el FIR del nodo 2, **0** en el notch y **512** en el nodo 3. El notch puede
introducir desfase aunque su retardo declarado sea cero. Para medir energía
útil en el nodo 3, se aplican a `s8` las ganancias aprendidas de `x8`.

Desde `proyecto1/simulacion/`, con las dependencias instaladas:

```
python -m pytest pruebas
python -m sim.comparacion
```

El segundo comando recorre P1–P5, tres semillas por condición y cuatro niveles
en P5. Escribe las métricas de entrada, nodo 2 y nodo 3 en
`resultados/comparacion.csv`, sus medias y desviaciones muestrales en
`resultados/comparacion_resumen.csv` y cinco figuras en `resultados/figuras/`.
**Las pruebas no crean esos archivos**: verifican cálculos en memoria, igual
que las pruebas de los otros módulos. Las tablas y figuras solo se generan al
ejecutar explícitamente `python -m sim.comparacion`, para incorporarlas al PDF.
Las pruebas de integración verifican la alineación, la causalidad y los
criterios de P1, P2 y P5.

## DFT y costo

`sim.dft` calcula la DFT directamente desde su definición:
`X[k] = sum(x[n]*exp(-2j*pi*k*n/N))`, en `complex128`. Calcula una frecuencia
k a la vez, sin matriz N×N, y reutiliza un vector para los exponentes, los
factores y los productos mediante operaciones de NumPy con `out`.
La compara con `numpy.fft.fft` para N muestras de P1 desde el segundo 1
(primera semilla de la configuración) y para una señal normal aleatoria
con semilla 0. N se obtiene de `config/pruebas.json`.

Se informa el error máximo relativo `max|DFT-FFT|/max|FFT|` y la mediana de
cinco mediciones con `perf_counter` para cada método. El tiempo de la DFT
incluye generar los factores y ejecutar el bucle; la conversión inicial de la señal queda fuera
de las mediciones. Para una señal nula, el error relativo se define como cero.
El conteo teórico es N² multiplicaciones complejas para la DFT y
`(N/2)*log2(N)` para una FFT radix-2: con N = 1024 son 1 048 576 y 5120,
respectivamente, una relación de **204.8**. Esa relación no predice exactamente
la aceleración medida ni describe el algoritmo interno de NumPy. Los tiempos
también incluyen el bucle Python y las llamadas a NumPy: comparan estas
implementaciones, no únicamente la complejidad de los algoritmos.

`sim.costo` toma los parámetros de `config/pruebas.json`, `config/nodo2.json`
y `config/cadena_analogica.json`. Estima multiplicaciones reales por segundo,
memoria base y latencia algorítmica con estas fórmulas (L es el número de
coeficientes, B = N/2+1 y T el historial de tramas):

| Método | Mult. reales/s | Memoria base en bytes | Latencia |
|---|---|---|---|
| FIR, incluida decimación | `L*fs_salida` | `4*(2*L-1)` | `(L-1)/2` muestras a fs de entrada |
| Notch biquad | `5*fs` | `4*(5+2)` | 0 muestras de alineación; desfase dependiente de frecuencia |
| DFT por frecuencia | `4*N²*fs/H` | `56*N` | 0 como referencia de costo |
| Espectral | `(4*N*log2(N)+2*N+2*B)*fs/H` | `4*(3*N+(3+T)*B)` | H muestras |

Con la configuración actual, las cinco filas exportadas son:

| Método | Mult. reales/s | Memoria base (B) | Latencia (ms) |
|---|---:|---:|---:|
| FIR decimación nodo 1 | 296 000 | 292 | 0.75 |
| FIR banda protegida nodo 2 | 296 000 | 292 | 2.25 |
| Notch nodo 2 | 40 000 | 28 | 0 |
| DFT por frecuencia | 65 536 000 | 57 344 | 0 (referencia) |
| Espectral nodo 3 | 688 031.25 | 34 860 | 64 |

La memoria de la DFT incluye tres arreglos `complex128` de N elementos
(entrada, salida y términos: 16 KiB cada uno) y los índices `float64` (8 KiB):
**56 KiB** para N = 1024. Todos crecen proporcionalmente a N; no se guarda
una matriz cuadrática. Se corrigió el supuesto de 12 KiB de la guía original
para representar la implementación elegida y su espacio de trabajo. La columna
`memoria_valores` del CSV expresa unidades equivalentes de 4 bytes; no indica
que los arreglos de la DFT sean float32. Se excluyen objetos Python, escalares
y trabajo interno de NumPy, por lo que no es el pico de RAM.
Tampoco es la memoria total del experimento de comparación.

Los conteos no incluyen sumas ni el costo de generar los factores con
exponenciales. El modelo espectral omite medianas y detección de ruido;
su memoria supone buffers float32, no el consumo real de la simulación en
Python. Las latencias excluyen tiempo de cómputo, UART y reproducción: cero
en la DFT no significa ejecución instantánea, y el notch puede tener retardo
de grupo aunque se use cero para alinear las métricas.

`tabla_costo` conserva las cuatro filas independientes del nodo 3.
`generar_costo` agrega una quinta mediante `costo_espectral`, con el historial
de `config/nodo3.json`, y la exporta junto a las demás. Con historial 8 estima
688 031.25 mult./s, 34 860 B y 64 ms. Los decimales se conservan en la consola.

Desde `proyecto1/simulacion/`, con el entorno activo:

```
python -m pytest pruebas/test_dft.py pruebas/test_costo.py
python -m pytest pruebas
python -m sim.dft
python -m sim.costo
```

Los dos últimos comandos crean `resultados/dft_fft.json` y
`resultados/costo.csv`; las pruebas no modifican los resultados del proyecto
(la prueba del comando de costo escribe un CSV en un directorio temporal). Los tiempos
dependen del equipo y de su carga, por lo que no se exige una aceleración
mínima en las pruebas. Los valores de las tablas anteriores son estimaciones
del diseño, no resultados medidos en la placa.

Verificación del 29 oct 2026: **207 pruebas pasaron** con Python 3.14.8 y las
versiones fijadas en `requirements.txt`. Ambos comandos terminaron correctamente.
En esta ejecución, el error relativo fue 2.562e-13 para P1 y 3.093e-13 para
la señal aleatoria. Las medianas DFT/FFT fueron 16.0855/0.021558 ms y
16.0307/0.019057 ms, respectivamente: aceleraciones medidas de 746.15 y 841.20.
Estos tiempos corresponden a la PC usada para la verificación; no al ESP32.

## Figuras y tablas del informe

Desde esta carpeta, con el entorno activo:

```
python -m sim.informe
```

Es el comando para regenerar el material antes de armar el PDF. Carga las
configuraciones una sola vez y reutiliza los cálculos existentes. Produce:

- `resultados/comparacion.csv`: métricas de entrada y ambas rutas para P1–P5.
- `resultados/comparacion_resumen.csv`: medias y desviaciones por condición.
- `resultados/dft_fft.json`: precisión, tiempos y operaciones de ambas transformadas.
- `resultados/costo.csv`: los cinco métodos, incluido el nodo 3.
- `resultados/figuras/P1.png` a `P5.png`: tiempo y espectros separados por nodo.
- `resultados/figuras/nodo2_polos_ceros.png`: ceros, polos, ROC causal y estabilidad.
- `resultados/figuras/nodo2_respuesta.png`: magnitud de los FIR y notch, y fase.
- `resultados/figuras/cadena_analogica.png`: Sallen-Key, decimación y salida con retención.
- `resultados/figuras/dft_fft.png`: espectros superpuestos y diferencia absoluta.

Las cuatro figuras nuevas se guardan a 150 dpi. En la figura de decimación,
la línea horizontal identifica el parámetro Kaiser de 50 dB que figura en
`config/cadena_analogica.json`, no una garantía de rechazo mínimo ni un nuevo
criterio de aceptación. Se usa este parámetro en lugar de la referencia fija
de −45 dB propuesta en la guía del paso 6.

Los comandos `python -m sim.comparacion`, `python -m sim.dft` y
`python -m sim.costo` siguen funcionando por separado. Para generar todo en
otra carpeta desde Python, se puede llamar a `sim.informe.generar_todo(salida)`.

Las figuras P1–P5 tienen tres paneles: 40 ms de señales alineadas desde los
5 s, espectro del nodo 2 frente a limpia/contaminada y espectro del nodo 3
frente a esas mismas referencias. Cada señal conserva su color en todos los
paneles y la contaminada se dibuja con transparencia. El espectro conserva
la ventana de Hann periódica y el tramo de evaluación configurado. No se
normaliza cada curva por separado: las magnitudes permiten comparar niveles.
Los límites superiores se comparten entre los dos paneles espectrales para
facilitar la comparación; el límite inferior es −100 dB.

Verificación final del paso 6, 29 oct 2026: **213 pruebas pasaron** con las
dependencias fijadas y Python 3.14.8. `python -m sim.informe` terminó sin
errores y generó en `resultados/` cuatro archivos de datos y nueve figuras,
revisadas visualmente. Las tablas contienen 72 filas de métricas, 24 grupos
de resumen y cinco métodos de costo. Las pruebas también verifican los tres
paneles, sus leyendas, colores y la alineación temporal de la salida del nodo 3.
Las figuras y CSV de comparación son regenerables y permanecen ignorados por
Git, según las reglas existentes; el script los crea antes de armar el PDF.
