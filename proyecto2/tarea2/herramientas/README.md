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
