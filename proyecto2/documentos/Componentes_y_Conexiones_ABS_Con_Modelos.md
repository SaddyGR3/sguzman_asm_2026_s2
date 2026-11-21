# Componentes y conexiones — Sistema de frenado tipo ABS

Alcance: propuesta preliminar para la Tarea 2 (pruebas a lazo abierto) y reutilización posterior en el proyecto completo con PID. Confirmar modelos y fichas técnicas antes de cablear.

## 1. Lista de componentes

| Cantidad | Componente | Modelo sugerido / especificación | Función | Estado |
| --- | --- | --- | --- | --- |
| 1 | ESP32 Dev Module | ESP32-WROOM-32 DevKit V1 (verificar placa exacta) | Medición, registro y futuro PID | Disponible |
| 1 | Motor DC | JGA25-370, 12 V, versión ~200 RPM (verificar corriente de bloqueo) | Girar el disco | Pendiente |
| 1 | Driver TB6612FNG | TB6612FNG (solo si I_arranque/I_bloqueo cumplen límites del módulo) | Controlar motor | Pendiente |
| 1 | Disco de frenado | Disco de acrílico rígido, Ø 100–150 mm (fabricación local) | Superficie de frenado | Pendiente |
| 1 | Acople para eje | Acople rígido según diámetro real del eje JGA25-370 | Fijar disco | Pendiente |
| 1 | Servomotor | TowerPro MG996R, 5–6 V (comprobar autenticidad y consumo) | Accionar zapata | Pendiente |
| 1 | Zapata | Zapata de caucho sobre soporte rígido (fabricación local) | Aplicar fricción | Pendiente |
| 1 | Sensor óptico de ranura | KY-010, módulo fotointerruptor de ranura (verificar tensión y salida de la unidad) | Medir giro | Pendiente |
| 1 | Disco encoder | Disco encoder ranurado de 20 ranuras, compatible con KY-010 | Producir pulsos | Pendiente |
| 1 | Fuente para motor | Fuente regulada 12 V, corriente por definir según motor | Potencia del motor | Pendiente |
| 1 | Fuente para servo | Fuente regulada 5 V / 3 A como punto de partida; verificar picos | Alimentar servo | Pendiente |
| 1 | Cable USB | Cable USB según conector de la placa ESP32 | Programación y datos | Por verificar |
| 1 | Base y soportes | Base MDF de 12 mm y soportes a medida | Estructura | Pendiente |
| Varios | Cables y conectores | Cables Dupont para señales; borneras/cable adecuado para potencia | Cableado | Pendiente |
| 1 | Interruptor de seguridad | Interruptor DC ≥ tensión y corriente reales del motor | Corte de alimentación | Pendiente |
| 1 | Protector del disco | Pantalla protectora de policarbonato transparente | Seguridad | Pendiente |

Modelos propuestos, no confirmados: JGA25-370, TB6612FNG, MG996R y KY-010 son referencias para cotización; NO asumir compatibilidad entre motor y driver sin comprobar la corriente de bloqueo, ni conectar una salida de sensor de 5 V al ESP32. Las fuentes y el acople se dimensionan después de seleccionar las piezas reales.

## 2. Pines propuestos del ESP32

| ESP32 | Componente | Pin del componente | Función |
| --- | --- | --- | --- |
| GPIO25 | TB6612FNG | PWMA | PWM motor |
| GPIO26 | TB6612FNG | AIN1 | Dirección |
| GPIO27 | TB6612FNG | AIN2 | Dirección |
| GPIO14 | TB6612FNG | STBY | Habilitación |
| GPIO18 | Servomotor | Señal | Posición del freno |
| GPIO34 | Sensor óptico | OUT/DO | Pulsos de encoder |
| 3V3 | TB6612FNG | VCC | Alimentación lógica |
| 3V3 | Sensor compatible | VCC | Alimentación del sensor |
| GND | Driver, sensor, fuente servo | GND | Referencia común |
| USB | Computadora | USB | Alimentación y datos |

GPIO34 es solo entrada y no tiene pull-up interno. No aplicar 5 V a ningún GPIO del ESP32.

## 3. Conexiones del driver TB6612FNG

| Pin del driver | Conectar a | Descripción |
| --- | --- | --- |
| VM | +12 V de fuente del motor | Alimentación de potencia |
| VCC | ESP32 3V3 | Lógica |
| GND | GND común | Retorno |
| PWMA | GPIO25 | PWM |
| AIN1 | GPIO26 | Dirección |
| AIN2 | GPIO27 | Dirección |
| STBY | GPIO14 | Habilitación |
| AO1 | Terminal 1 motor | Salida |
| AO2 | Terminal 2 motor | Salida |

Verificación obligatoria: confirmar que la tensión y, especialmente, la corriente de arranque/bloqueo del motor sean compatibles con el driver. No conectar el motor a un GPIO.

## 4. Conexiones del servomotor

| Cable habitual | Conectar a | Función |
| --- | --- | --- |
| Rojo (V+) | +5–6 V de fuente externa | Alimentación |
| Marrón/negro (GND) | Negativo de fuente y GND común | Retorno |
| Naranja/amarillo (señal) | GPIO18 | Control |

- No alimentar el servo desde 3V3 del ESP32.
- Verificar que el servo admita señal de control de 3.3 V.
- Un capacitor de 470–1000 µF entre V+ y GND, cerca del servo, puede ayudar con caídas de tensión; respetar polaridad y tensión nominal.
## 5. Conexiones del sensor óptico

| Pin del sensor | Conectar a | Función |
| --- | --- | --- |
| VCC | 3V3, solo si es compatible | Alimentación |
| GND | GND común | Retorno |
| OUT/DO | GPIO34 | Lectura de pulsos |

Si la salida es de colector abierto y no tiene pull-up integrado, usar una resistencia de 10 kΩ de OUT a 3V3:

```text
ESP32 3V3 ── 10 kΩ ──┬── GPIO34
│
Sensor OUT
Sensor GND ───────────── GND común
```
Si el sensor requiere 5 V, verificar el tipo de salida y adaptar niveles cuando corresponda; nunca enviar 5 V directamente a GPIO34.

## 6. Resistencias y capacitores

| Componente adicional | Valor orientativo | Ubicación | Necesidad |
| --- | --- | --- | --- |
| Resistencia pull-up | 10 kΩ | OUT del sensor a 3V3 | Solo si la salida es colector abierto y carece de pull-up |
| Capacitor electrolítico | 470–1000 µF | Alimentación del servo | Recomendado según fuente y servo |
| Capacitor cerámico | 100 nF | Cerca de alimentación lógica | Según módulo |
| Capacitores del driver | Según hoja de datos | Cerca de VM/GND | Según módulo y fabricante |
| Resistencia para LED externo | Según tensión y LED | En serie con LED | Solo si se agrega LED |

No se coloca una resistencia en serie con el motor ni con la señal del servo para la conexión básica propuesta.

## 7. Alimentación

| Fuente | Alimenta | Precaución |
| --- | --- | --- |
| USB computadora | ESP32 | No alimentar motor ni servo desde el ESP32 |
| 12 V | Driver y motor | Dimensionar para corriente de arranque/bloqueo |
| 5–6 V | Servomotor | Soportar picos de corriente |
| 3V3 del ESP32 | Lógica del driver y sensor compatible | Respetar capacidad del regulador |

Las tierras de los circuitos que intercambian señales deben tener GND común. No unir los positivos de 12 V, 5 V y 3.3 V.

## 8. Tarea 2 y proyecto final

| Elemento | Tarea 2: lazo abierto | Proyecto final: lazo cerrado |
| --- | --- | --- |
| Motor | Giro del disco | Giro del disco |
| Driver | Orden predefinida | Según estrategia de operación |
| Sensor | Medición de RPM | Realimentación |
| ESP32 | Lectura y registro | Lectura y PID |
| Servo | Frenado fijo/programado | Frenado ajustado por PID |
| PID | Código documentado; no activo en prueba física | Implementado y ajustado |
| MATLAB | Caracterización experimental | Validación del modelo |

## 9. Orden recomendado de montaje

1. Fijar motor y disco; verificar giro sin roces.
2. Conectar driver y fuente; probar giro lento sin freno.
3. Instalar sensor; verificar pulsos y RPM en ESP32.
4. Probar servo sin carga; después instalar zapata.
5. Integrar y ensayar frenado a lazo abierto; registrar RPM.
6. Exportar CSV y analizarlo en MATLAB.
7. En el proyecto final, activar PID después de validar sensor, actuador y seguridad.
## 10. Información pendiente

| Dato | Estado |
| --- | --- |
| Modelo y corriente de bloqueo del motor | Pendiente |
| Driver definitivo | Pendiente |
| Modelo, voltaje y salida del sensor | Pendiente |
| Número de ranuras del encoder | Pendiente |
| Servo definitivo | Pendiente |
| Capacidad real de las fuentes | Pendiente |
| Dimensiones/material del disco | Pendiente |
| Pines definitivos | Propuestos, por validar |

Seguridad: verificar fichas técnicas, polaridad, tensiones y corrientes antes de energizar. Sujetar el disco, instalar protección mecánica y contar con un corte accesible de alimentación del motor.
