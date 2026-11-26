# Captura serial y calibración del freno

El programa [registrar_ensayo.py](registrar_ensayo.py) abre el puerto de la ESP32 a **115200 baudios**, guarda las filas numéricas en `datos_*.csv` y las marcas de tiempo en `eventos_*.csv`. Cerrar antes el Monitor Serial de Arduino o PlatformIO: solo un programa puede abrir el puerto a la vez.

```sh
python3 -m pip install -r proyecto2/tarea2/herramientas/requirements.txt
python3 proyecto2/tarea2/herramientas/registrar_ensayo.py /dev/ttyUSB0
```

En Windows, sustituir `/dev/ttyUSB0` por el puerto correspondiente, por ejemplo `COM3`. Los archivos se crean en `proyecto2/tarea2/capturas/` y el programa imprime sus rutas. Se recomienda iniciar **una captura nueva por corrida**. El capturador reinicia automáticamente el reloj y contador de pulsos de la ESP32 al abrir cada captura; tarda unos dos segundos en dejarla lista.

Los archivos se numeran automáticamente: si no hay capturas numeradas, se guardan `datos_1.csv` y `eventos_1.csv`; la siguiente ejecución guarda `datos_2.csv` y `eventos_2.csv`. El número es el **ID** de la corrida: identifica el par, no indica si fue libre o frenada. Los archivos existentes no se sobrescriben. Las capturas antiguas con fecha en el nombre pueden quedarse en la carpeta, pero MATLAB también las leerá si no se filtran.

| Tecla o comando | Acción |
| --- | --- |
| Flecha derecha o arriba | Aumenta el ángulo ordenado en un paso. |
| Flecha izquierda o abajo | Disminuye el ángulo ordenado en un paso. |
| `p5` + Enter | Cambia el paso a 5°. Se admite de 1° a 10°. `p1` recupera el valor inicial. |
| `g75` + Enter | Ordena ir directamente a 75°. Elegir el ángulo final después de calibrar. |
| `c` | Guarda el ángulo ordenado en el momento en que se observa el primer contacto. |
| `f` | Guarda el ángulo de contacto útil elegido, antes de forzar o bloquear el servo. |
| `m` | Marca el instante aproximado en que se apagó manualmente la fuente del motor. Pulsar al apagarla. |
| `v` | Muestra los pulsos aceptados y los rechazados por llegar demasiado pronto. Comparar los aceptados antes y después de girar manualmente un número conocido de vueltas. |
| `q` | Cierra la captura y deja los CSV guardados. |

El ángulo permitido es **0° a 90°**, como en el firmware anterior. Las flechas envían un cambio por pulsación, aunque mantenerlas presionadas puede activar la repetición del teclado. El número mostrado es el **ángulo ordenado**, no una medición del ángulo físico ni de la fuerza sobre el disco. Calibrar primero con el motor apagado y elegir un ángulo que frene sin forzar el SG90. El comando gradual anterior `0` y `s` siguen disponibles si se escriben con Enter; su velocidad se conserva, pero `0` no se usa para la prueba de escalón.

El tiempo de `datos_*.csv` empieza en la **segunda marca aceptada del sensor**, cuando puede calcularse la primera RPM. El primer pulso sí suma en `PULSOS`, pero una sola vuelta no basta para conocer la velocidad; con el firmware actualizado, el segundo pulso inicia el tiempo incluso si se giró a mano y pasaron más de un segundo entre ambos. Antes de ese momento no aparecen filas de medición; los eventos previos llevan tiempo `-1`. Una vez iniciado, el reloj sigue avanzando aunque las RPM sean cero: así se conservan en una sola escala los instantes de apagado y frenado. Si no llega otra marca durante un segundo, el firmware muestra `RPM=0`; este límite **no reinicia el reloj ni descarta vueltas lentas**. Al girar a mano, las RPM pueden variar mucho porque cada valor se calcula con el intervalo entre dos marcas. En `eventos_*.csv`, `SERVO_CMD` registra cuándo se envió la posición al SG90 y `MOTOR_OFF_MANUAL` registra cuándo se pulsó `m`. Este último es aproximado por el tiempo de reacción de la persona. El intervalo de impresión es **100 ms**; la estimación de RPM sigue limitada por una marca por vuelta.

Para usar solo el Monitor Serial del IDE, escribir `+` o `-` y pulsar Enviar con final de línea **Nueva línea**; las flechas del teclado del Monitor Serial no se transmiten a la ESP32. El IDE tampoco guarda automáticamente los CSV separados. Para las corridas que irán a MATLAB, usar el programa de captura.

### Comprobar que el KY-033 cuenta una marca por vuelta

Con el motor apagado y el freno separado del disco, colocar la marca **fuera** del campo del sensor. Mantener el disco quieto y pulsar `v`: anotar `N0`. Esperar cinco segundos sin moverlo y pulsar `v`: anotar `N1`. Girar **exactamente cinco vueltas completas**, despacio, hasta volver a la misma orientación inicial, y pulsar `v`: anotar `N2`. Esperar otros cinco segundos quieto y pulsar `v`: anotar `N3`. No hace falta reiniciar entre estas cuatro lecturas.

El resultado esperado es `N1 = N0`, `N2 - N1 = 5` y `N3 = N2`. `PULSOS` es **acumulado** desde `REINICIO`: una sola lectura como `PULSOS=6` no demuestra una vuelta adicional. Si el contador aumenta con el disco quieto, comprobar primero alimentación y masa del sensor, conexiones y estabilidad de su LED. Si aumenta de más solo durante el giro, fijar mejor el disco/acople y el KY-033, comprobar que haya una sola marca de alto contraste y ajustar su potenciómetro en incrementos pequeños. No asumir un sentido de giro: probar el LED con la marca frente al sensor y luego sin ella, y conservar el ajuste que dé dos estados estables y **un único intervalo de detección por vuelta**. Repetir la prueba tres veces antes de usar las RPM en MATLAB. El firmware actualizado descarta transiciones separadas por **20 ms o menos** y `v` las cuenta en `PULSOS_RECHAZADOS`. Este umbral permite hasta unas 3000 RPM con una marca por vuelta y se eligió según las dos corridas del montaje actual (menos de 1800 RPM estables, picos falsos de 3 a 16 ms). Si se aumenta mucho la velocidad del motor, habrá que revisar el umbral. El filtro no corrige un disco que oscile ni pulsos falsos más separados: comprobar la mecánica y repetir el ensayo.

Después calibrar el contacto con las flechas. Pulsar `c` al observar el primer contacto y `f` en el ángulo de frenado útil elegido. Esas marcas guardan el ángulo en `eventos_*.csv`; también anotar el ángulo sin contacto. Cerrar esa captura y abrir otra para cada ensayo de giro libre o frenado.

## Actualización del diagnóstico del firmware

El capturador ahora crea también `diagnostico_N.csv`, con el mismo número que datos y eventos. Conserva el formato histórico de esos dos archivos y puede capturar firmware antiguo sin líneas de diagnóstico. Los números se eligen sin sobrescribir ninguno de los tres archivos.

Las líneas `#DIAG` incluyen RPM cruda y validada, estado, antigüedad, periodos y contadores de rechazo o pérdida. También incluyen modo, motor ordenado, tiempo de ensayo y campos reservados de referencia y PID. NaN indica que una medición es inválida o que el cálculo todavía no existe. No debe sustituirse automáticamente por cero.

Los comandos escritos, incluidas las marcas `c`, `f`, `m` y `v`, se envían ahora con Enter. Esto permite escribir `fijo47`, `motor_on`, `motor_off` o `cancelar` completos. Las flechas mantienen su efecto inmediato. Para interrumpir una prueba, enviar `cancelar` antes de salir con `q`. La tecla `q` solo cierra la captura.

Las instrucciones anteriores sobre las marcas se conservan como contexto, pero se aplica esta actualización de teclado. El comando `m` sigue siendo una marca manual y no equivale al apagado automático `MOTOR_CMD`.

El analizador MATLAB de la Tarea 2 continúa disponible para sus archivos históricos. Interpretar los eventos automáticos y filtrar la calidad del diagnóstico requiere adaptar explícitamente ese análisis. El nuevo capturador no declara que el protocolo automático ya sea compatible con ese ajuste histórico.

La bitácora está en `proyecto2/firmware/freno abs/BITACORA.md`.

## Diagnóstico PID en observación

El paso 5 agrega ocho columnas al final del diagnóstico, con acción limitada, términos P, I y D, estado y tiempos del cálculo. El capturador admite las 18 columnas anteriores y las 26 actuales. Al leer un diagnóstico anterior conserva sus valores y deja los nuevos campos como no disponibles.

`u_solicitada` es la petición matemática del PID y `pid_u_limitada` su resultado acotado. `u_aplicada` sigue como NaN mientras el PID no gobierne el servo. `GANANCIAS_CERO` identifica el cálculo con parámetros todavía sin ajustar. No interpretar estos valores como una prueba física de seguimiento.


## Capturas del modo PID

El capturador admite el modo `PID` y el estado `CONTROLANDO`. Conserva las 26 columnas del diagnóstico y la compatibilidad con registros anteriores. `u_aplicada` puede contener un valor entre cero y uno cuando el firmware ordena el servo desde PID. Representa la orden normalizada después del redondeo angular y no una medición de torque o posición. En FIJO y manual permanece NaN.

Los comandos completos `preparar`, `pid`, `estado` y `cancelar` se envían con Enter. El firmware conserva bloqueada la actuación PID por defecto hasta verificar el montaje y configurar ganancias. El analizador MATLAB histórico todavía necesita adaptación al protocolo de ensayos automáticos.

## Interfaz gráfica de diagnóstico

El panel nuevo ofrece gráficas en vivo, controles y captura automática de datos. Se inicia con `python3 panel_frenado.py` desde esta carpeta. Tiene modo ESP32 y modo de planta ficticia, que usa el cálculo PID y la conversión angular del firmware sin cargar una placa. La guía completa y la primera prueba sin maqueta están en [panel/README.md](panel/README.md).
