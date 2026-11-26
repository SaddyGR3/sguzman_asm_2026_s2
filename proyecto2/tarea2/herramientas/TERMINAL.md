# Banco de frenado en terminal o panel

Las dos interfaces utilizan el mismo receptor, validación de datos, protocolo y captura. El firmware de la ESP32 no cambia al elegir una interfaz. Las ganancias y habilitaciones del firmware siguen siendo independientes de los ajustes de simulación.

## Elegir la interfaz

Ejecutar desde fish en la carpeta de herramientas.

```fish
cd '/home/saddygr/Documentos/GitHub/sguzman_asm_2026_s2/proyecto2/tarea2/herramientas'
```

### Panel en el navegador

```fish
python3 panel_frenado.py --modo panel
```

El comando anterior `python3 panel_frenado.py` sigue abriendo el panel. Si el puerto web está ocupado, cerrar la otra instancia o elegir otro número.

```fish
python3 panel_frenado.py --modo panel --puerto-web 8766
```

### Terminal con ESP32

Cerrar el monitor serial de PlatformIO y desconectar cualquier otra interfaz que esté usando la misma placa. Sustituir el puerto de ejemplo por el real.

```fish
python3 panel_frenado.py --modo terminal --puerto-serial /dev/ttyUSB0
```

Requiere pyserial, incluido en `requirements.txt`. El modo terminal actual usa una terminal interactiva de Linux o POSIX. No redirigir su entrada o salida a un archivo. El registro de datos ya se guarda automáticamente.

### Terminal sin maqueta

```fish
python3 panel_frenado.py --modo terminal --simular
```

Se puede elegir la figura y los parámetros iniciales de la simulación.

```fish
python3 panel_frenado.py --modo terminal --simular --curva coseno --rpm 1500 --duracion 6 --kp 0.005 --ki 0 --kd 0
```

Las figuras disponibles son `lineal`, `exponencial` y `coseno`. La simulación requiere `g++` y utiliza el cálculo PID y la conversión angular del firmware con una planta ficticia. No necesita pyserial, navegador, servidor web ni MATLAB.

Los argumentos `--rpm`, `--duracion`, `--kp`, `--ki`, `--kd` y `--curva` configuran la simulación. No cambian la configuración física de la ESP32. En el modo físico se configura la duración enviando `tiempoN` y el firmware todavía admite solo referencia lineal.

## Qué muestra la pantalla

La pantalla se actualiza unas cinco veces por segundo. Esto no cambia el periodo del controlador ni crea nuevas mediciones.

- Fuente, modo, figura activa y antigüedad del diagnóstico.
- RPM validadas, referencia y error.
- Ángulo ordenado, acción normalizada al servo y tiempo de ensayo.
- Estado de medición, estado PID y motor ordenado.
- Contribuciones P, I y D, petición y acción limitada.
- RPM cruda, pulsos aceptados, rechazos, saltos, pérdidas de cola y último periodo rechazado.
- Intervalo de control, periodos omitidos y tiempo de cálculo.
- Minigráficas de RPM, referencia y acción PID.
- Eventos recientes, ruta de captura y entrada de comandos.

Las minigráficas usan las últimas 120 muestras y cada una tiene su propia escala, cuyo mínimo y máximo aparecen al lado. Son una ayuda visual y no reemplazan las gráficas con ejes ni el análisis de los CSV. Los huecos de medición se representan con puntos y no se convierten en cero. Para ver los picos concretos, consultar RPM cruda y los contadores.

NaN y datos ausentes se muestran como un guion. Si deja de llegar diagnóstico reciente, la pantalla lo indica y conserva los últimos valores como históricos. Las ventanas pequeñas muestran un resumen y piden ampliar la terminal.

## Escribir comandos

Escribir el comando completo y pulsar Enter. Retroceso borra un carácter y Ctrl+U limpia la entrada. No se utilizan las flechas para mover el servo en esta interfaz.

| Comando | Función |
|---|---|
| `preparar` | Libera el freno y solicita encender el motor. |
| `pid` | Solicita iniciar el ensayo con PID. |
| `libre` | Envía `fijo45` para giro libre con el freno liberado. |
| `fijo30` | Solicita un ensayo fijo a 30 grados, únicamente después de calibrar ese contacto. |
| `tiempo6000` | Configura seis segundos antes de preparar. |
| `cancelar` | Solicita cancelar, apagar el motor y liberar el freno. |
| `motor_on` | Solicita encender el motor si el firmware lo permite. |
| `motor_off` | Solicita apagar el motor y cancela una preparación o ensayo activo. |
| `g90` | Orden manual de 90 grados fuera del ensayo. |
| `estado` | Consulta el estado. |
| `v` | Consulta los contadores de pulsos. |
| `curva coseno` | Cambia la figura entre ensayos, solo en simulación. |
| `curva exponencial` | Elige la exponencial normalizada en simulación. |
| `curva lineal` | Elige la recta en simulación. |
| `pico` | Inyecta un pico sintético en la simulación. |
| `ayuda` | Recuerda los comandos principales. |
| `salir` | Cierra la captura y restaura la pantalla de la terminal. |

También se admiten los comandos existentes del firmware y las formas separadas `fijo 30`, `tiempo 6000`, `motor on` y `motor off`.

Un aviso de orden enviada no demuestra que el firmware la haya aceptado ni que el mecanismo se haya movido. Comprobar el evento, modo y respuesta física. Los rechazos por motor deshabilitado o PID deshabilitado permanecen visibles. Esta interfaz no evita las protecciones del firmware.

## Primera prueba simulada

1. Abrir el modo terminal con `--simular`.
2. Escribir `preparar` y esperar cerca de dos segundos.
3. Escribir `libre` para observar la caída sin freno o `pid` para seguir la referencia.
4. Observar el estado, las minigráficas y los eventos.
5. Escribir `cancelar` y esperar el evento `ENSAYO_CANCELADO` antes de salir.
6. Escribir `salir`.

Para otra figura, cambiarla después de cancelar o terminar y antes de preparar. Los comandos de figura quedan bloqueados durante preparación y ensayo, igual que en el panel.

## Capturas y cierre

El modo terminal guarda en `proyecto2/tarea2/capturas/terminal`, en subcarpetas `reales` y `simuladas`. El panel conserva su carpeta anterior `proyecto2/tarea2/capturas/panel`.

En ambos casos cada conexión crea su propia carpeta con datos, eventos, diagnóstico, texto serial y metadatos. Los metadatos identifican si se usó la interfaz terminal o panel. Usar `--salida` para elegir otra raíz de captura. Se conserva el mismo formato de CSV.

Salir, Ctrl+C, Ctrl+D y cerrar el proceso no envían una cancelación implícita. Para terminar un ensayo físico, enviar `cancelar`, comprobar su recepción y respuesta, y después cerrar la interfaz. Una pérdida de comunicación impide garantizar que una orden llegue. El corte físico de energía sigue siendo independiente de esta herramienta.

El modo terminal no ocupa el puerto web, pero sí necesita el puerto serial de la ESP32. No usar panel, terminal y PlatformIO Serial Monitor simultáneamente sobre el mismo puerto. Cambiar de interfaz exige cerrar la conexión anterior y puede reiniciar algunas placas al volver a abrirla.

Si no se quieren colores, agregar `--sin-color`. La actualización de pantalla y restauración de la terminal se mantienen.

## Verificación sin hardware

```fish
python3 -m unittest discover -s pruebas -v
```

Las pruebas incluyen ambas interfaces, los comandos, los datos inválidos, los CSV y una sesión real en una pseudoterminal con una planta simulada. Se comprueban captura y restauración de la terminal al salir. El puerto y la mecánica reales siguen pendientes de validación.

## Diagnóstico de GPIO34

Carga primero el firmware que incluye `sensor_on` y `sensor_off`. Desconecta el panel y cierra el monitor de PlatformIO antes de abrir la terminal. Mantén apagada la fuente del motor y gira el disco a mano.

```fish
/tmp/asm-panel-venv/bin/python '/home/saddygr/Documentos/GitHub/sguzman_asm_2026_s2/proyecto2/tarea2/herramientas/panel_frenado.py' --modo terminal --puerto-serial /dev/ttyUSB0
```

Escribe `sensor_on` y pulsa Enter. Cada fila corresponde a una llamada de la ISR de cambios. El detector corregido usa `CHANGE` para observar ambos niveles, pero solo cuenta una secuencia completa y estable. Activar el diagnóstico no altera ese detector. El nivel leído es una observación dentro de la ISR, no una reconstrucción completa de la señal.

La tabla muestra número de llamada, tiempo en microsegundos desde el arranque, intervalo desde la llamada anterior, nivel leído, total aceptado y total rechazado por periodo corto. El primer intervalo parte de la activación del diagnóstico. Los tiempos vuelven a cero aproximadamente cada 71 minutos. La resta sin signo del intervalo soporta esa vuelta a cero.

El objetivo es comprobar qué cambios produce una pasada por la marca, sus separaciones y cuáles completan un conteo. No se presupone la causa del segundo conteo. Esta instrumentación añade trabajo a la ISR y no sustituye un osciloscopio para observar transiciones muy breves o pulsos perdidos por el hardware.

Solo puede activarse sin ensayo y con el motor ordenado apagado. Mientras está activo bloquea `preparar` y `motor_on`. Comprueba además que la fuente física esté apagada.

La sesión guarda `sensor_1.csv` y las líneas originales en `serial.txt`. La pantalla muestra las últimas cuatro llamadas y el CSV conserva todas las recibidas. La cola tiene 128 posiciones y capacidad útil de 127 registros. Si se llena, informa pérdidas y marca la captura incompleta. La ISR no imprime por serial.

Escribe `sensor_off` y después `salir`. Desactivar deja de registrar llamadas y mantiene el detector de marcas completas. Cerrar la terminal no desactiva el diagnóstico automáticamente. Reiniciar la ESP32 también lo desactiva. Los CSV de velocidad mantienen su formato y continúa configurado un pulso por vuelta.

## Terminal con historial de líneas

`--modo terminal` imprime ahora mensajes normales y conserva el historial. No usa pantalla alternativa ni borra la salida. Puedes desplazarte para revisar las llamadas de la interrupción. Cada registro muestra número de ISR, tiempo, intervalo, nivel leído y contadores. Los comandos se escriben con el eco normal de la terminal y se envían al pulsar Enter. Mientras `sensor_on` está activo, se ocultan los resúmenes de RPM de un segundo para facilitar la lectura.

La pantalla anterior con minigráficas sigue disponible con `--vista-terminal panel`. `--sin-color` no es necesario para la vista de líneas, que no utiliza secuencias ANSI. Si la pantalla no alcanza a consumir los mensajes, avisa y conserva los recibidos en los archivos de captura. Las pérdidas de la cola del firmware se informan por separado.

## Detector de marcas completas

La corrección del doble conteo mantiene un pulso por vuelta. Usa ambos bordes de GPIO34 para reconocer primero una zona libre y después una zona activa, cada una con duración mínima configurable. El nivel activo provisional es LOW. Eso describe el nivel eléctrico y debe comprobarse su correspondencia con negro o blanco en la maqueta.

Los mínimos iniciales son 100 microsegundos por nivel y no dependen de la velocidad de giro. Un aviso repetido del mismo nivel no cambia el estado. Una salida muy breve no vuelve a habilitar el conteo. El contador aumenta al completar la zona activa, pero el periodo de RPM utiliza los tiempos de entrada a esa zona. Así no interpreta el ancho de la franja como una vuelta.

Los valores se prueban con marcas de 200 microsegundos a unas 1800 RPM. Eso no demuestra que la marca real tenga ese ancho ni que la señal física sea correcta. Si negro o blanco duran menos del mínimo, pueden perderse vueltas. Una perturbación que dure tanto como una marca real puede superar el filtro. Falta validar físicamente antes de usar la medición para PID.

Al arrancar o reiniciar con `r` dentro de una zona activa, se descarta esa primera fracción de marca. Para comprobar el conteo, gira una vuelta de inicialización, anota el contador y después completa diez vueltas en el mismo sentido. Debe aumentar diez veces, tanto con giro lento como rápido.

### Calibración provisional vigente

El rango automático es de 45 grados liberado a 15 grados de freno máximo provisional. El disco queda libre a 40 grados y se eligen 45 para dejar margen. Las observaciones manuales son contacto leve a 35, roce a 33, frenado a 30 y frenado fuerte a 25. El ensayo fijo inicia con un valor sugerido de 30 grados. No se interpreta esta relación como torque medido. La calibración manual sigue permitiendo órdenes de 0 a 90 grados. Hay que validar el rango en funcionamiento antes de ajustar el PID.

## Secuencia automática por velocidad

El panel permite iniciar un ciclo completo sin cronometrar clics. Desde reposo, elige la duración y el ángulo y pulsa Iniciar ciclo fijo. El botón envía primero la duración y después `auto_fijoN`. Se puede pulsar Ciclo libre para usar `auto_fijo45`, que conserva el freno liberado.

El firmware prepara con servo a 45 grados y motor encendido. Al recibir una velocidad válida y reciente igual o superior a 1400 RPM, apaga el motor y entra en DESCENSO_LIBRE. Mantiene el freno liberado. La primera medición nueva válida igual o inferior a 1300 RPM inicia el ensayo y la referencia. El valor inicial de la referencia es la RPM realmente medida, que puede quedar ligeramente por debajo del umbral por el muestreo. No se interpola un instante exacto de cruce.

`auto_preparar` permite preparar antes de elegir el tipo de ensayo. En ese caso se debe armar con `auto_fijoN` o `auto_pid` durante la aceleración o mientras el descenso todavía supera 1300 RPM. Si se cruza sin una prueba armada, termina con AUTO_SIN_ENSAYO_ARMADO y no inicia un ensayo tardío. Una prueba ya armada no cambia de ángulo por una segunda orden.

Los comandos anteriores `preparar`, `fijoN` y `pid` siguen disponibles para ensayos manuales. Un ensayo automático no admite iniciar por esos comandos manuales. `motor_on` y `motor_off` conservan el control manual fuera de ensayos.

La preparación tiene un máximo de 60 segundos y el descenso libre uno de 15 segundos. Las mediciones inválidas no activan los umbrales. La pérdida persistente de medición, la cancelación y los tiempos máximos apagan el motor, liberan el freno y eliminan la prueba pendiente. El PID físico sigue deshabilitado hasta configurar ganancias y activarlo explícitamente. `auto_pid` respeta ese bloqueo antes de encender el motor.

Los eventos AUTO_CORTE_OBJETIVO_RPM y AUTO_INICIO_OBJETIVO_RPM guardan los umbrales. AUTO_FIJO_ARMADO guarda el ángulo. MOTOR_CMD y AUTO_MOTOR_OFF_RPM_X100 identifican el corte y su velocidad. AUTO_INICIO_RPM_X100 y ENSAYO_FIJO_INICIO identifican el inicio del freno. RPM_INICIAL_X100 y REFERENCIA_LINEAL_MS permiten reconstruir la referencia. Los campos X100 están expresados en RPM multiplicadas por cien. Los formatos de los CSV existentes se conservan.

Los umbrales y tiempos están en configuracion.h. La simulación lee esos valores del código compilado y reproduce el ciclo con su planta ficticia. Esto no valida la respuesta física. Para completar el ciclo simulado, su objetivo de aceleración debe ser superior al umbral de apagado.
