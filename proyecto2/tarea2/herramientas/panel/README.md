# Panel de diagnóstico del banco de frenado

La interfaz sigue la idea de las gráficas y métricas en vivo de `test/diagnostico_radar.py` y `test/osciloscopio.py` del Proyecto 1 en el repositorio Dgarcia. Esta versión agrega controles de ensayo, captura y una simulación separada de los datos reales. Se abre en el navegador local y no necesita Internet ni MATLAB.

## Iniciar en fish

```fish
cd '/home/saddygr/Documentos/GitHub/sguzman_asm_2026_s2/proyecto2/tarea2/herramientas'
python3 panel_frenado.py
```

Se abrirá la dirección `http://127.0.0.1:8765`. Mantén el proceso Python abierto mientras uses la interfaz. Si no se abre la ventana, introduce esa dirección en tu navegador. Puedes usar `--sin-abrir` para iniciar sin abrir una pestaña y `--puerto-web 8766` si el puerto predeterminado está ocupado.

## Primera prueba sin maqueta

1. Deja seleccionado Simulación. El objetivo predeterminado es 1500 RPM, la duración seis segundos, Kp 0,005 y Ki y Kd cero. Son valores didácticos.
2. Pulsa Iniciar simulación. Se compilan temporalmente el cálculo PID y la conversión angular. No modifica la ESP32.
3. Elige ángulo y duración y pulsa Iniciar ciclo fijo. Desde reposo, el botón envía la duración y arma todo el ciclo. También puedes elegir Ciclo libre o Iniciar ciclo PID en simulación.
4. La velocidad sube hasta el corte de 1400 RPM. El motor se apaga y el modo cambia a DESCENSO_LIBRE con el freno liberado a 45 grados.
5. Al bajar a 1300 RPM empieza el ensayo. Se captura la velocidad medida de ese instante, comienza la referencia y se aplica el ángulo fijo o el controlador elegido.
6. Puedes pulsar Simular pico para introducir una lectura sintética inválida. Los umbrales no se ejecutan por ese dato sospechoso.
7. Pausar vista solo detiene el dibujo. Cancelar detiene el ciclo y libera el freno. Desconectar cierra la captura y no envía cancelación.
8. Preparar es opcional. Si se utiliza, hay que armar el ciclo fijo, libre o PID antes de cruzar 1300 RPM durante el descenso. Para cambiar la duración, envíala antes de Preparar.
9. El objetivo simulado debe superar 1400 RPM. Una simulación configurada por debajo no puede completar este ciclo. Las ganancias solo afectan a la simulación y no habilitan el PID físico.

El botón Guardar gráfica descarga una imagen PNG de la gráfica de velocidad con la fuente identificada. Las curvas completas y los otros datos quedan en CSV. Pasar el puntero sobre las gráficas permite consultar valores.

## Elegir la figura de referencia

El selector Figura de referencia ofrece Lineal, Exponencial normalizada y Coseno suave en la simulación. Elegirla antes de Iniciar simulación la configura desde el comienzo. Con una simulación ya conectada, elegir otra y pulsar Aplicar figura antes de Preparar o después de terminar o cancelar. El texto Figura activa muestra la selección realmente aceptada.

La selección se bloquea durante PREPARACION, DESCENSO_LIBRE, FIJO y PID. La figura usada para dibujar la referencia es la misma que recibe el cálculo PID. La velocidad inicial se captura al iniciar el ensayo y la duración sigue siendo la configurada. Las tres curvas llegan a cero en T y permanecen allí.

Con x igual a t dividido entre T, durante el intervalo de cero a T se usan estas expresiones.

| Figura | Referencia |
|---|---|
| Lineal | $r=\omega_0(1-x)$ |
| Exponencial normalizada | $r=\omega_0(e^{-3x}-e^{-3})/(1-e^{-3})$ |
| Coseno suave | $r=\omega_0[1+\cos(\pi x)]/2$ |

El factor tres de la exponencial fija la forma del dibujo elegido y no es una ganancia PID. Las curvas se generan en la PC para la simulación. El firmware físico todavía solo genera la lineal, por lo que en modo ESP32 el selector queda bloqueado en Lineal y el servidor rechaza enviarle opciones no soportadas.

Los metadatos conservan la figura inicial y el significado de los códigos. El evento `REFERENCIA_TIPO` identifica cada selección aceptada y se repite al iniciar cada ensayo. Cero corresponde a lineal, uno a exponencial y dos a coseno. Las modificaciones entre ensayos se reconstruyen desde eventos sin cambiar las columnas de los CSV.

Que una figura se pueda seleccionar no demuestra que la planta pueda seguirla. El inicio suave del coseno puede desacelerar menos que el rozamiento natural, lo que el freno unilateral no puede corregir. Comparar con el giro libre y conservar los fallos y errores observados.

## Giro libre sin freno

Pulsa Ciclo libre · sin freno. Desde reposo inicia la preparación, apaga el motor al alcanzar 1400 RPM y comienza la referencia al bajar a 1300 RPM, manteniendo el servo a 45 grados. Así puedes observar la desaceleración natural sin que el PID gobierne el freno. No necesitas poner las ganancias en cero.

El botón usa el comando automático `auto_fijo45`, tanto en simulación como con ESP32. El protocolo lo registra como `FIJO`. Los cálculos PID que aparezcan son únicamente de observación. Cambiar las ganancias no altera el giro libre. La referencia azul queda como comparación y no como una curva que este ensayo intente seguir.

Al cumplirse la duración configurada aparece `FINALIZADO` por tiempo. Esto no significa que el disco se haya detenido. El motor permanece apagado, el freno liberado y la captura continúa mostrando la velocidad. Para apreciar una caída lenta, cambia la ventana gráfica a Últimos 60 s o Hasta 300 s.

En el modelo ficticio, sin freno la velocidad cae aproximadamente de forma exponencial. La maqueta puede responder de otra manera por rozamiento y por el comportamiento eléctrico del driver al apagar el motor. Confirma que 45 grados libera realmente el mecanismo antes de usarlo físicamente.

## Qué se está simulando

La planta ficticia cumple la relación siguiente, con velocidad en RPM y tiempo en segundos.

$$
\frac{d\omega}{dt}=-0.05\omega-300u_a.
$$

La acción mecánica ficticia tiene un retardo de primer orden de 0,12 s. El ángulo ordenado se convierte mediante el código real de `freno.cpp`, entre 45 y 15 grados. El controlador compila directamente `pid.cpp` y usa su integral, derivada filtrada y límites. Las pequeñas cabeceras nativas sustituyen únicamente las llamadas físicas necesarias para ejecutarlo en la PC.

La preparación representa una aceleración ficticia hacia la RPM elegida. Durante el ensayo el motor virtual se apaga. La medición de velocidad es ideal y continua a 50 Hz, con publicación nominal a 10 Hz. Los contadores de pulsos son sintéticos. No se emulan interrupciones del sensor, la cola de pulsos, todos los estados del firmware, ruido aleatorio ni el circuito eléctrico. El final de baja velocidad usa umbrales provisionales similares al firmware y puede fallar si la medición llega a cero antes de confirmar el criterio. El silencio no demuestra una parada física.

Esta simulación permite aprender y verificar el sentido de la acción. No identifica la planta real ni obtiene ganancias finales. Para estudiarlas se pueden cambiar Kp, Ki y Kd entre sesiones. No se ofrece una copia del PID escrita en Python que pueda divergir del cálculo del firmware.

Requiere Python 3.10 o posterior y `g++`, en Linux. La compilación genera una biblioteca temporal `.so`. No se ha verificado el modo nativo en Windows. La interfaz y la captura serial pueden adaptarse a otros sistemas, pero no se afirma esa compatibilidad sin probarla.

## Conectar la ESP32

El modo físico requiere pyserial, incluido en `../requirements.txt`. Usa un entorno virtual para instalar dependencias si aún no están disponibles.

```fish
python3 -m venv /tmp/asm-panel-venv
/tmp/asm-panel-venv/bin/python -m pip install -r requirements.txt
/tmp/asm-panel-venv/bin/python panel_frenado.py
```

Cierra PlatformIO Serial Monitor y cualquier programa que tenga abierto el puerto. Selecciona ESP32, busca o escribe el puerto y conecta. Se usa 115200 baudios. Abrir el puerto puede reiniciar algunas placas. El panel no envía `r`, no habilita el motor y no cambia las ganancias de la placa. Los campos Kp, Ki y Kd solo pertenecen a la simulación.

Los comandos se escriben en el puerto y el firmware conserva la decisión final sobre si los acepta. Un mensaje de orden enviada no es confirmación de movimiento. Revisa los eventos y el modo informado. Si la actuación PID o el motor siguen deshabilitados en el firmware, la interfaz mostrará los rechazos correspondientes.

Los controles manuales conservan el recorrido histórico de 0 a 90 grados. Ese rango no garantiza un recorrido mecánico seguro. Los ensayos fijos de la interfaz usan 15 a 45 grados. El límite físico necesita calibración.

Cerrar el navegador o desconectar no envía cancelación a la placa. Usa Cancelar y comprueba su evento y estado antes de desconectar. Si falla el enlace, la interfaz no puede asegurar que la orden de cancelación llegue. El firmware mantiene su lógica local de ensayo y fallos.

## Gráficas y diagnóstico

La ventana muestra velocidad cruda y validada, referencia, error, acción solicitada, acción limitada, orden normalizada al servo, ángulo y contribuciones P, I y D. La señal validada tiene huecos cuando el firmware indica una lectura inválida. NaN se muestra como un guion y no se convierte en cero.

Los contadores, antigüedad, estado del sensor, estado PID y tiempos facilitan investigar picos, pérdidas y retrasos. Se avisa cuando el diagnóstico deja de llegar. Los últimos valores son históricos mientras no exista una actualización. Un firmware antiguo con solo tres columnas se captura, pero no se inventa una validación ni se muestran esas RPM como confiables.

El eje de las gráficas usa tiempo de recepción en la PC desde la conexión, para evitar mezclar el reinicio del reloj del firmware con el tiempo de la ventana. El registro conserva el tiempo original de cada mensaje. No se debe usar el eje gráfico como medida precisa de latencia o tiempo de control.

La memoria de la vista conserva hasta 3000 filas de diagnóstico y 160 eventos. Los archivos siguen guardando la captura completa. Si se superan unos cinco minutos a 10 Hz, la vista descarta los puntos más antiguos.

## Archivos de cada sesión

Las capturas quedan bajo `proyecto2/tarea2/capturas/panel`, en carpetas `simuladas` y `reales`, con una subcarpeta única por conexión. La ruta aparece en la interfaz. Se puede elegir otra raíz con `--salida`.

Cada sesión contiene `datos_1.csv`, `eventos_1.csv`, `diagnostico_1.csv`, `serial.txt` y `metadatos.json`. Los tres CSV conservan el formato del capturador existente. Los metadatos identifican la fuente, puerto o parámetros ficticios y fecha con zona horaria de Costa Rica. `serial.txt` conserva las líneas recibidas, incluidas las que no se acepten como filas de diagnóstico.

Usar la misma conexión para varias corridas conserva sus eventos en la misma sesión. Para separar archivos por corrida desconecta y conecta de nuevo. Se registran todas las muestras disponibles y no se exige iniciar una prueba para comenzar la captura.

Los CSV no convierten las pruebas simuladas en mediciones experimentales. El analizador MATLAB histórico sigue pendiente de adaptación al protocolo automático.

## Verificación sin hardware

```fish
python3 -m unittest discover -s pruebas -v
```

Las pruebas comprueban el controlador nativo, conversión, pico sintético, captura, comandos, separación de sesiones, protección de operaciones del servidor, lectura fragmentada del puerto y cierre de la conexión. Usan puertos y servidor locales simulados. La conexión serial física y el funcionamiento de la maqueta siguen pendientes.

## Alternativa de terminal

El mismo programa tiene un modo de terminal con datos, eventos, comandos y minigráficas. Se inicia con `--modo terminal --simular` o `--modo terminal --puerto-serial` seguido del puerto real. El modo panel sigue siendo el predeterminado. Consultar `proyecto2/tarea2/herramientas/TERMINAL.md` para instrucciones. Utilizar una sola interfaz a la vez sobre el puerto serial de la placa.

### Calibración provisional vigente

El rango automático es de 45 grados liberado a 15 grados de freno máximo provisional. El disco queda libre a 40 grados y se eligen 45 para dejar margen. Las observaciones manuales son contacto leve a 35, roce a 33, frenado a 30 y frenado fuerte a 25. El ensayo fijo inicia con un valor sugerido de 30 grados. No se interpreta esta relación como torque medido. La calibración manual sigue permitiendo órdenes de 0 a 90 grados. Hay que validar el rango en funcionamiento antes de ajustar el PID.

### Cero estimado sin pulsos

Tras un segundo sin nuevas marcas, el estado SIN_SENAL se representa como cero estimado en la tarjeta y en la gráfica. Se identifica explícitamente como estimación. El último valor crudo deja de prolongarse al caducar. Las mediciones originales, los CSV y el PID mantienen la velocidad inválida, sin sustituirla por cero. La falta de comunicación con la ESP32 o el desbordamiento de la cola no generan por sí solos una estimación de parada.
