# Lista de componentes — Proyecto Grupal 1

Qué se necesita en cada nodo. Cómo se conecta cada cosa está en `guia_conexiones_hardware.md`, y los pines, en `contrato_nodos.md`. Actualizada: 28 oct.

---

## 1. Por comprar (verificar si ya se compró)

| Componente | Cantidad | Dónde | Notas |
|---|---|---|---|
| LM358 **DIP-8** | 4 (3 + repuesto) | MicroJPM, código AD5727, $0.95 c/u | No el SOP-8 (AD68872): no entra en la protoboard |
| Jack hembra 3.5 mm estéreo PJ-307 | 1 | MicroJPM, código AD19305, $1.50 | Entrada de audio del nodo 1. No calza en la protoboard: soldarle 3 cables |
| Cable de audio 3.5 mm macho–macho (auxiliar) | 1 | Cualquier tienda | De la salida de audífonos de la PC al jack del nodo 1 |

Si no hay jack: cortar el cable auxiliar por la mitad, pelar sus tres hilos (izquierdo, derecho y tierra) y soldarlos a pines para la protoboard; el extremo con conector va a la PC.

---

## 2. Ya disponibles

| Componente | Cantidad | Uso |
|---|---|---|
| ESP32 (WROOM-32D) | 3 (verificar) | Nodos 1, 2 y 3 |
| Cable USB | 3 (verificar) | Alimentación y programación |
| Adaptador YP-05 (USB a TTL, FT232RL) | 1 | La PC escucha o imita un nodo (jumper en 3.3 V) |
| PAM8403 | 2 | Amplificador de las salidas de los nodos 2 y 3 |
| Parlante (4–8 Ω) | 2 | Salidas de los nodos 2 y 3 |
| LCD 1602 I2C | 1 | Métricas del nodo 3 |
| Protoboards y jumpers | — | Montaje |
| Resistencias, capacitores y diodos | — | Ver valores por nodo abajo |
| Potenciómetros de 10 kΩ | 3 | Nivel de entrada y volumen de las dos salidas |
| LEDs, LED RGB y botones | — | Avisos de error, método activo y cambio de parámetros |

Para medir: multímetro y osciloscopio.

---

## 3. Por nodo

### Nodo 1 — adquisición (entrada de audio, dos canales: x y s)

| Componente | Cantidad | Para qué |
|---|---|---|
| ESP32 + cable USB | 1 | Nodo 1 |
| Jack PJ-307 + cable auxiliar | 1 | Audio de la PC |
| Capacitor de 10 µF | 2 (uno por canal) | Acople de entrada (quita el DC de la PC) |
| Resistencia de 1.5 kΩ | 2 | Divisor hacia 3.3 V (centro en 1.32 V) |
| Resistencia de 1 kΩ | 4 | Divisor hacia GND (2) y protección en serie del pin del ADC (2) |
| Resistencia de 6.8 kΩ | 4 | Sallen-Key anti-aliasing (R1 y R2, por canal) |
| Capacitor de 10 nF | 2 | Sallen-Key (C1, realimentación) |
| Capacitor de 4.7 nF | 2 | Sallen-Key (C2, a tierra) |
| LM358 DIP-8 | 1 | Una mitad por canal |
| Capacitor de 100 nF | 1 | Desacople de la alimentación del LM358 (5 V desde VIN) |
| Diodos de señal (por ejemplo, 1N4148) | 4 | Protección del ADC hacia GND y hacia 3.3 V (2 por canal) |
| Potenciómetro de 10 kΩ | 1 | Nivel de entrada (opcional; el nivel se ajusta también con el volumen de la PC) |
| LED + resistencia de 220–330 Ω | 1 | LED de error (GPIO4) |

### Nodo 2 — filtrado temporal (salida de audio)

| Componente | Cantidad | Para qué |
|---|---|---|
| ESP32 + cable USB | 1 | Nodo 2 |
| LM358 DIP-8 | 1 | Una mitad: seguidor del DAC; la otra: Sallen-Key de reconstrucción |
| Capacitor de 100 nF | 1 | Desacople del LM358 |
| Resistencia de 6.8 kΩ | 2 | Sallen-Key (R1 y R2) |
| Capacitor de 10 nF | 1 | Sallen-Key (C1) |
| Capacitor de 4.7 nF | 1 | Sallen-Key (C2) |
| Capacitor de 10 µF | 1 | Acople en serie antes del atenuador |
| Potenciómetro de 10 kΩ | 1 | Atenuador antes del PAM8403 (**obligatorio**; arrancar al mínimo) |
| PAM8403 + parlante | 1 | Salida de audio |
| LED + resistencia de 220–330 Ω | 1 | LED de error (GPIO4) |

### Nodo 3 — filtrado espectral, métricas y pantalla

Lo mismo que el nodo 2, más:

| Componente | Cantidad | Para qué |
|---|---|---|
| LCD 1602 I2C | 1 | Métricas (SDA en GPIO21, SCL en GPIO22) |
| LED RGB + 3 resistencias de 220–330 Ω | 1 | Método activo |
| Botones | 2 | Cambiar de método y modo automático/manual (GPIO32 y GPIO33, pull-up interno) |

### Para las pruebas

| Componente | Cantidad | Para qué |
|---|---|---|
| YP-05 | 1 | Validar cada enlace desde la PC (`proyecto1/herramientas_pc/`) |
| Jumpers macho–hembra | varios | Enlaces UART entre placas y al YP-05 (cables cortos: 921 600 baudios) |

---

## 4. Totales de valores fijos

| Valor | Total (3 nodos) |
|---|---|
| Resistencia de 6.8 kΩ | 8 |
| Resistencia de 1.5 kΩ | 2 |
| Resistencia de 1 kΩ | 4 |
| Resistencia de 220–330 Ω | 6 (3 LEDs de error + 3 del RGB) |
| Capacitor de 10 nF | 4 |
| Capacitor de 4.7 nF | 4 |
| Capacitor de 10 µF | 4 |
| Capacitor de 100 nF | 3 |
| Diodos de señal | 4 |
| LM358 DIP-8 | 3 (+1 de repuesto) |
| Potenciómetro de 10 kΩ | 3 |
