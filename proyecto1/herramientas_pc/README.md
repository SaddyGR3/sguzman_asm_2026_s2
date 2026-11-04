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

Desde la raíz del repositorio:

```
python proyecto1/herramientas_pc/receptor_nodo1.py --puerto /dev/ttyUSB1 --enlace n3 --segundos 60 --guardar captura_n3.bin
python proyecto1/herramientas_pc/receptor_nodo1.py --archivo proyecto1/herramientas_pc/capturas/captura_n3.bin --enlace n3
python proyecto1/herramientas_pc/receptor_nodo1.py --puerto /dev/ttyUSB1 --enlace n2out --segundos 60
```

## Capturas

`capturas/captura_n2.bin` y `capturas/captura_n3.bin` son capturas reales de 60 s del 28 oct. La de N3 incluye un reinicio con EN a los 30 s. Las dos dieron `RESULTADO: OK` en vivo y reprocesadas con `--archivo`. Sirven como evidencia y para los diagramas de validación sin montar la placa.

## Diagnóstico

Si hay errores de CRC solo en la PC, el sospechoso es el adaptador a 921 600 baudios, no el emisor. Se distingue reprocesando la captura con `--archivo`.
