# Montaje de las capturas reales del 22 de noviembre de 2026

## Datos comunicados por el equipo

| Elemento | Dato | Alcance de la afirmación |
| --- | --- | --- |
| Motor | Motor DC miniatura; modelo exacto desconocido y hoja de datos no disponible | La foto comercial compartida por el equipo no permite confirmar el modelo del motor instalado. |
| Alimentación del motor | Fuente ajustada o indicando 1 V durante las corridas | Valor comunicado por el equipo; no se midió con multímetro en los terminales bajo carga. |
| Apagado | Se apaga la fuente con los cables conectados; el disco sigue girando por inercia | Comunicado por el equipo. |
| Controlador de motor | Mini L298N AD70178 disponible, no conectado | El motor no está conectado a la ESP32. |
| Disco | MDF de 12 cm de diámetro y 3 mm de espesor | Dimensiones confirmadas por el equipo; no se informó masa. |
| Acople | Provisional; el disco oscila y se estabiliza más a velocidades altas | Observación del equipo; describirla como limitación de RPM. |
| Sensor | KY-033 conectado a GPIO34 y alimentado desde la placa ESP32 | Una marca por vuelta es el supuesto del cálculo de RPM; falta confirmación visual definitiva. |
| Actuador | Servo SG90 conectado a GPIO18 y alimentado desde la placa ESP32 | 90° es la orden sin freno y 40° es la orden de frenado en las corridas principales. Son ángulos ordenados, no posición física medida. |
| Contacto de freno | Brazo del SG90 con hule unido a una esponja; la esponja toca la cara superior del disco | Descripción comunicada por el equipo; no se midieron fuerza normal ni torque. |
| Registro | Una muestra cada 100 ms; filtro de pulsos de 20 ms | Según el firmware usado en las capturas. |

## Evidencia de la entrega

El informe usa `datos_1.csv`/`eventos_1.csv` para giro libre y `datos_2.csv`/`eventos_2.csv` para frenado; los CSV están en `../capturas/` y se mantienen fuera de Git. Las cuatro fotografías se guardaron en [informe/imgs/](../informe/imgs/). Los videos entregados son [planta completa](https://youtu.be/hc-JIA8kH4Y) y [caracterización con MATLAB](https://youtu.be/BWD1uK7m35k).

## Datos físicos todavía útiles para describir el montaje

1. Pines exactos de alimentación del SG90 y del KY-033 y una foto clara del cableado, si están disponibles. El equipo confirmó que ambos reciben alimentación de la placa, sin documentar tensión ni corriente.
2. Una medición independiente de pulsos por vuelta permitiría confirmar el factor usado en las RPM; ya no se prevén ensayos adicionales para esta entrega.

La masa del disco, la corriente del motor y el torque del servo serían necesarios para calcular parámetros físicos absolutos como inercia o torque. **No son necesarios** para la comparación experimental de las corridas 1 y 2 ni para el modelo local ajustado en `matlab/ejecutar_analisis.m`. Si no se midieron, no inventar valores.
