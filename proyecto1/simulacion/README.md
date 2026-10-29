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
