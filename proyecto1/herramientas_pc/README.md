# Herramientas de la PC

Herramientas que corren en la PC; no son firmware.

## `receptor_nodo1.py`

Recibe un enlace del emisor (nodo 1) por un adaptador USB-serie (YP-05, FT232RL), o desde una captura guardada, y valida:

- CRC, COBS, secuencia, banderas, DIAG y energía de cada bloque;
- los picos de la FFT de x (300, 700, 1100 y 2150 Hz);
- en el enlace N3, la SNR de 0 dB.

Termina con `RESULTADO: OK` o `RESULTADO: FALLA` y la lista de fallas.
Con `--enlace n2out` también valida los paquetes FIR_OUT de nodo 2 hacia nodo 3:
CRC, COBS, sesión, secuencia, banderas y avance de `first_sample`.

## Instalación

Usa el mismo tipo de entorno que la [simulación](../simulacion/README.md#instalación-del-entorno). Con el entorno activo, desde esta carpeta:

```
pip install -r requirements.txt
```

Instala numpy y pyserial. El receptor importa `sim/protocolo.py` de `proyecto1/simulacion/`, así que esa carpeta debe estar presente (no se copia ni se modifica).

## Conexión

Un enlace a la vez:

- jumper del YP-05 en 3.3 V;
- RX del YP-05 a GPIO18 (enlace N2) o a GPIO17 (enlace N3);
- para FIR_OUT, RX del YP-05 a GPIO17 **del nodo 2**;
- GND común entre el YP-05 y la ESP32;
- TX del YP-05 sin conectar;
- no conectar VCC.

## Puertos

Ejecuta `python3 -m serial.tools.list_ports -v` antes y después de conectar el
YP-05; el puerto nuevo es el que debes poner en `--puerto`. Puede ser
`/dev/ttyUSB0`, `/dev/ttyUSB1` u otro nombre. El puerto del nodo 2, usado por
su monitor serie, no es el del YP-05.

## Uso

| Argumento | Uso |
|---|---|
| `--puerto` | puerto serie, por ejemplo `/dev/ttyUSB1` |
| `--archivo` | captura cruda guardada antes; excluyente con `--puerto` |
| `--enlace {n2,n3,n2out}` | obligatorio. `n2`: INPUT del nodo 1. `n3`: INPUT_REF del nodo 1. `n2out`: FIR_OUT del nodo 2. |
| `--segundos` | duración de la captura en vivo (60 por defecto) |
| `--baudios` | 921600 por defecto |
| `--guardar` | ruta donde guardar los bytes crudos recibidos; solo en vivo |
| `--solo-protocolo` | valida `n2` o `n3` sin las expectativas de señal y DIAG del generador |

Desde la raíz del repositorio:

```
python proyecto1/herramientas_pc/receptor_nodo1.py --puerto /dev/ttyUSB1 --enlace n3 --segundos 60 --guardar captura_n3.bin
python proyecto1/herramientas_pc/receptor_nodo1.py --archivo proyecto1/herramientas_pc/capturas/captura_n3.bin --enlace n3
python proyecto1/herramientas_pc/receptor_nodo1.py --puerto /dev/ttyUSB1 --enlace n2out --segundos 60
```

## Solo protocolo (ADC)

Para validar el nodo 1 en modo ADC con P1, usa `--solo-protocolo`: conserva las
comprobaciones de protocolo, secuencia, índices y valores finitos; exige 0x0001
en INPUT_REF y acepta las demás banderas, contándolas por tipo. Omite las
expectativas del generador sobre DIAG, energía, tonos y SNR. Al finalizar muestra
paquetes/s, banderas y mínimo, máximo y RMS de x y s. En vivo las tasas usan el
tiempo real de captura; con `--archivo` se infiere la duración de `first_sample`
a 8000 Hz. Sin la opción se conserva la validación original.

```sh
python3 proyecto1/herramientas_pc/receptor_nodo1.py --puerto /dev/ttyUSB1 --enlace n3 --segundos 60 --solo-protocolo
```

Con P1 sonando se esperan ~15.6 INPUT_REF/s y ~15.6 DIAG/s, cero errores y 0x0001
en todos los INPUT_REF. Como comprobación orientativa, el RMS de s debería ser
aproximadamente la mitad del de x; esa relación no condiciona el veredicto.

## Capturas guardadas

`capturas/captura_n2.bin` y `capturas/captura_n3.bin` son capturas reales de 60 s del 28 oct. La de N3 incluye un reinicio con EN a los 30 s. Las dos dieron `RESULTADO: OK` en vivo y reprocesadas con `--archivo`. Sirven como evidencia y para los diagramas de validación sin montar la placa.

## Diagnóstico

Si hay errores de CRC solo en la PC, el sospechoso es el adaptador a 921 600 baudios, no el emisor. Se distingue reprocesando la captura con `--archivo`.

## Captura y gráficos de métricas

En la rama de métricas la placa de nodos 2+3 calcula SIN FILTRO, FIR, NOTCH y
RESTA en **una sola reproducción** de la misma grabación. Solo se escucha el
modo elegido. Emite cuatro registros `METRICAS,2,` al terminar, o al ejecutar
`metricas`. La PC no abre otro puerto, no modifica muestras ni procesa filtros.

### 1. Mantener el monitor y guardar solo métricas

`firmware/nodo2/platformio.ini` activa `monitor_filters = default, metricas_csv`.
El filtro propio `monitor/filter_metricas.py` usa la
[API de filtros de PlatformIO](https://docs.platformio.org/en/latest/core/userguide/device/cmd_monitor.html#custom-filters).
El monitor sigue mostrando todos los mensajes y aceptando comandos como antes.
Si ya estaba abierto antes del cambio, cerrarlo y abrirlo de nuevo para cargar
el filtro. El analizador de archivos puede ejecutarse con ese monitor abierto;
no abrir un segundo monitor serial sobre el mismo puerto.
El filtro guarda solo registros completos y válidos, incluso si llegaron partidos
en varias lecturas seriales. No necesita pyserial adicional ni un YP-05.

1. Cargar el firmware actualizado de nodo 2 y abrir su monitor normal de PlatformIO.
2. Si ya hay grabación LISTA, usar `reproducir` o el botón de play. Si no, reproducir
   el audio de prueba hacia el micrófono y esperar a que la grabación automática
   llegue a LISTA antes de usar play. `grabacion` consulta el estado, no inicia
   manualmente una grabación.
3. Esperar que termine la reproducción. El monitor anuncia una ruta como:
   `proyecto1/herramientas_pc/resultados/metricas/metricas_FECHA.csv`.
4. Ese CSV contiene únicamente líneas `METRICAS,`; no hay encabezado añadido.
   Puede analizarse mientras el monitor permanece abierto, una vez impresas las
   cuatro filas. Un informe incompleto se marca y se puede analizar de nuevo al
   terminar, usando otra carpeta de salida.

Se usa un archivo nuevo por apertura del monitor y, al reconocer el arranque de
la placa, se separan sesiones para evitar mezclar IDs que vuelven a 1. La fecha
del nombre es UTC con microsegundos; los archivos se crean al llegar la primera
fila válida. Si se pierde el mensaje de reinicio, no concatenar manualmente sus
capturas: abrir otra sesión de monitor. Un archivo de sesión puede contener varias
reproducciones; se distinguen por ID. Los CSV/figuras generados están ignorados por
Git, no los respaldos ni el código.

### 2. Generar la tabla y los gráficos

Con el entorno Python de PC activo, desde la raíz del repositorio:

```sh
python3 -m pip install -r proyecto1/herramientas_pc/requirements_metricas.txt
python3 proyecto1/herramientas_pc/analizar_metricas.py RUTA_DEL_CSV --etiqueta P1
```

`RUTA_DEL_CSV` se sustituye por la ruta anunciada por el monitor. Para seleccionar
una reproducción y nombrar la carpeta del informe:

```sh
python3 proyecto1/herramientas_pc/analizar_metricas.py RUTA_DEL_CSV --reproduccion 1 --etiqueta P1 --salida proyecto1/herramientas_pc/resultados/P1_r1
```

La carpeta indicada debe estar vacía o no existir, para no mezclar informes viejos.
Si se omite `--salida` se crea una carpeta nueva con fecha. No se instala ni usa
ninguna dependencia de la simulación. El parser y `--sin-graficos` usan solo la
biblioteca estándar; los gráficos requieren matplotlib (y sus dependencias).
El receptor histórico mantiene su `requirements.txt` separado.

| Opción | Uso |
|---|---|
| Archivos posicionales | Uno o varios CSV; también admite logs con mensajes ajenos |
| `--etiqueta P1` | Etiqueta dada por el usuario; no identifica automáticamente el audio |
| `--reproduccion 1` | Selecciona ID; se puede repetir. Se aplica a cada archivo |
| `--salida CARPETA` | Carpeta vacía/nueva para resultados |
| `--sin-graficos` | Genera solo CSV normalizado y tabla Markdown |

La salida contiene `metricas.csv` con encabezado y metadatos, `informe.md` y una
figura PNG y SVG por reproducción completa y válida. Cada figura compara los
modos disponibles: SNR estimada de salida (con referencia de entrada), ΔSNR,
energía, atenuación, MSE respecto de x, retardo, procesamiento y carga. La RAM y
los tiempos totales se incluyen en el informe y CSV. **No hay muestras: no es
posible graficar ondas ni espectros ni obtener métricas exactas frente a señal
limpia a partir de estas líneas.**

### Validez, repeticiones y versiones

- v2 espera exactamente SIN_FILTRO, FIR, NOTCH y RESTA; v1 admite el modo temporal
  seleccionado más RESTA, sin atribuir resultados a modos no medidos.
- `metricas` repite resultados: las filas idénticas con mismo archivo, versión,
  ID y modo se deduplican. IDs iguales de archivos distintos nunca se fusionan.
- Filas contradictorias y campos comunes inconsistentes invalidan el conjunto;
  no se elige silenciosamente el último resultado. Faltantes, líneas truncadas
  o versiones desconocidas se informan. Un conjunto inválido no genera figuras.
- NA permanece no disponible y se rotula en las figuras; nunca se transforma en
  cero. Se conservan informes CONFIG_CAMBIADA o DATOS_NO_FINITOS como diagnóstico.
- FIR/NOTCH comparten el cálculo temporal: sus barras incluyen ese costo conjunto
  más la FFT de su propia salida; **no se suman** para obtener el tiempo total.
  SIN FILTRO reutiliza x; su costo adicional es 0, no su costo global. El máximo
  total es el que se contrasta con 64 ms. Retardo de notch cero significa ausencia
  de desplazamiento fijo, no fase nula ni retardo de grupo cero.
- Código de salida 0: selección completa/coherente, estado de placa OK y sin
  líneas rechazadas. Código 2: error o captura incompleta/inválida; si hay filas
  reconocidas se guarda un informe diagnóstico. No equivale a que el filtro haya
  mejorado la señal ni garantiza que todos los cocientes sean finitos.

### Validación de PC

```sh
python3 -m unittest discover -s proyecto1/herramientas_pc/tests -v
```

Las 13 pruebas verifican deduplicación, sesiones separadas, versiones, NA, inválidos,
fragmentación, límites de línea, reinicios, tabla CLI e informes incompletos.
Las referencias numpy verifican convenciones de retardo y conservación de
energía por ventanas; no ejecutan C++ ni sustituyen pruebas del ESP32.
La integración con el registro de filtros de PlatformIO y una figura sintética
se verificaron sin abrir un puerto. Después se procesó la captura real de seis
reproducciones del usuario: cinco informes válidos y uno invalidado a propósito,
cuatro duplicados omitidos, sin líneas rechazadas. Los máximos observados en placa
fueron menores de 64 ms, con margen ajustado. Resultados y límites en
[VALIDACION_METRICAS.md](VALIDACION_METRICAS.md).
