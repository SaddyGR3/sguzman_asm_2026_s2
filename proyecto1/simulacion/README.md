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
