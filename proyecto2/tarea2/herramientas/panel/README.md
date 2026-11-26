# Panel de diagnóstico del banco de frenado

La interfaz sigue la idea de las gráficas y métricas en vivo de `test/diagnostico_radar.py` y `test/osciloscopio.py` del Proyecto 1 en el repositorio Dgarcia. Esta versión agrega controles de ensayo, captura y una simulación separada de los datos reales. Se abre en el navegador local y no necesita Internet ni MATLAB.

## Iniciar en fish

```fish
cd '/home/saddygr/Documentos/GitHub/sguzman_asm_2026_s2/proyecto2/tarea2/herramientas'
python3 panel_frenado.py
```

Se abrirá la dirección `http://127.0.0.1:8765`. Mantén el proceso Python abierto mientras uses la interfaz. Si no se abre la ventana, introduce esa dirección en tu navegador. Puedes usar `--sin-abrir` para iniciar sin abrir una pestaña y `--puerto-web 8766` si el puerto predeterminado está ocupado.

## Primera prueba sin maqueta

1. Deja seleccionado Simulación y los valores iniciales. Son 1200 RPM, seis segundos, Kp de 0,005 y Ki y Kd en cero. Son valores didácticos.
2. Pulsa Iniciar simulación. Se compilan temporalmente el cálculo PID y la conversión angular del firmware. Esto no modifica archivos ni ganancias de la ESP32.
3. Pulsa Preparar. La velocidad virtual sube hacia 1200 RPM. Espera unos dos segundos para verla estabilizarse.
4. Pulsa Iniciar PID. La referencia desciende y el controlador cambia el ángulo para seguirla. La referencia inicial parte de la velocidad virtual de ese instante.
5. Observa referencia y velocidad, error, acción y ángulo. La orden normalizada no es un torque medido.
6. Puedes pulsar Simular pico para mostrar una lectura cruda de 14000 RPM, marcada como sospechosa, sin usarla como velocidad válida. Este diagnóstico es sintético y no prueba el rechazo físico del KY-033.
7. Pausar vista detiene el dibujo y los valores mostrados. La captura, los comandos y la simulación continúan. Reanudar recupera la vista actual. Puedes ocultar la señal cruda para ver mejor el seguimiento cuando un pico amplía la escala.
8. Pulsa Cancelar para liberar. Puedes preparar otra corrida y usar Iniciar fijo para comparar visualmente. Si cambias la duración durante la conexión, envíala antes de Preparar.
9. Desconecta para cerrar los archivos. Para cambiar las ganancias simuladas desconecta y vuelve a iniciar. Se crea otra carpeta, sin sobrescribir la anterior.

El botón Guardar gráfica descarga una imagen PNG de la gráfica de velocidad con la fuente identificada. Las curvas completas y los otros datos quedan en CSV. Pasar el puntero sobre las gráficas permite consultar valores.

## Giro libre sin freno

Después de Preparar y esperar que se estabilice la velocidad, pulsa Giro libre · sin freno. Se apaga el motor y se mantiene la orden del servo en 90 grados, la posición liberada. Así puedes observar la desaceleración natural sin que el PID gobierne el freno. No necesitas poner las ganancias en cero.

El botón usa el comando existente `fijo90`, tanto en simulación como con ESP32. El protocolo lo registra como `FIJO`. Los cálculos PID que aparezcan son únicamente de observación. Cambiar las ganancias no altera el giro libre. La referencia azul queda como comparación y no como una curva que este ensayo intente seguir.

Al cumplirse la duración configurada aparece `FINALIZADO` por tiempo. Esto no significa que el disco se haya detenido. El motor permanece apagado, el freno liberado y la captura continúa mostrando la velocidad. Para apreciar una caída lenta, cambia la ventana gráfica a Últimos 60 s o Hasta 300 s.

En el modelo ficticio, sin freno la velocidad cae aproximadamente de forma exponencial. La maqueta puede responder de otra manera por rozamiento y por el comportamiento eléctrico del driver al apagar el motor. Confirma que 90 grados libera realmente el mecanismo antes de usarlo físicamente.

## Qué se está simulando

La planta ficticia cumple la relación siguiente, con velocidad en RPM y tiempo en segundos.

$$
\frac{d\omega}{dt}=-0.05\omega-300u_a.
$$

La acción mecánica ficticia tiene un retardo de primer orden de 0,12 s. El ángulo ordenado se convierte mediante el código real de `freno.cpp`, entre 90 y 47 grados. El controlador compila directamente `pid.cpp` y usa su integral, derivada filtrada y límites. Las pequeñas cabeceras nativas sustituyen únicamente las llamadas físicas necesarias para ejecutarlo en la PC.

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

Los controles manuales conservan el recorrido histórico de 0 a 90 grados. Ese rango no garantiza un recorrido mecánico seguro. Los ensayos fijos de la interfaz usan 47 a 90 grados. El límite físico necesita calibración.

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
