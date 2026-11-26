# Firmware del banco de frenado

## Avance del plan

Los pasos 1 a 6 incluyen ensayos fijos y PID con referencia lineal, diagnostico y conversion de la accion al servo. La actuacion PID y el control del motor estan deshabilitados por defecto y las ganancias siguen en cero. El control manual y el CSV historico se conservan.

| Archivo | Responsabilidad |
|---|---|
| `include/configuracion.h` | Pines, intervalos, rango manual y habilitacion del motor. |
| `src/main.cpp` | Inicio y coordinacion de tareas. |
| `src/medicion.cpp` | Interrupcion, periodos, RPM, reloj y contadores. |
| `src/freno.cpp` | Servo, posicion, paso y movimiento gradual. |
| `src/motor.cpp` | Unica salida de encendido y apagado del driver. |
| `src/pid.cpp` | Calculo independiente de P, I y D y sus limites. |
| `src/control_pid.cpp` | Observacion durante FIJO y actuacion durante PID. |
| `src/referencia.cpp` | Generacion independiente de la referencia lineal. |
| `src/ensayos.cpp` | Estados, preparacion, ensayo fijo, finalizacion y cancelacion. |
| `src/comandos.cpp` | Recepcion e interpretacion de comandos. |
| `src/registro.cpp` | Encabezado, eventos y muestras seriales. |

## Comandos manuales

Enviar cada comando seguido de nueva linea a 115200 baudios.

| Comando | Accion |
|---|---|
| `gN` | Orden directa entre 0 y 90 grados. |
| `90` | Regresar directamente a la posicion liberada documentada. |
| `+` y `-` | Cambiar posicion segun el paso. |
| `pN` | Elegir paso entre 1 y 10 grados. |
| `0` | Iniciar movimiento gradual hacia cero. |
| `s` | Detener solamente el movimiento gradual. |
| `c` y `f` | Marcar primer contacto y contacto util. |
| `m` | Marcar manualmente apagado de fuente. No controla el motor. |
| `v` | Consultar pulsos aceptados y rechazados. |
| `r` | Reiniciar medicion y su reloj. No cambia motor ni servo. |
| `motor_on` y `motor_off` | Solicitar encendido o apagado si el driver esta habilitado. |
| `?` | Imprimir ayuda. |

El rango manual sigue siendo 0 a 90 grados para conservar la calibracion anterior. No se debe recorrer completo con el freno cargado sin conocer sus limites. El control automatico usa por separado los limites provisionales de 90 y 47 grados.

## Driver del motor pendiente de confirmar

GPIO25 queda reservado. `controlMotorHabilitado` es falso por defecto. En ese estado el firmware no configura ni escribe el pin y los comandos responden con `MOTOR_NO_HABILITADO`. Esto no corta una alimentacion externa ni garantiza por si solo un nivel electrico de apagado.

Antes de habilitarlo, identificar el terminal controlado, fijar las demas entradas, confirmar compatibilidad de niveles y elegir `nivelMotorEncendido`. Verificar si apagar deja girar libremente o produce frenado electrico. Comprobar tambien el estado del driver durante arranque y reinicio de la ESP32. Si necesita una resistencia para quedar apagado, debe existir en el montaje.

Con el control habilitado, se prepara el nivel inactivo antes de configurar GPIO25 como salida. No hay encendido automatico. `MOTOR_CMD` registra la orden enviada, no una medicion del estado fisico.

## Datos conservados

La salida mantiene `tiempo_ms,rpm,servo_cmd_grados` cada 100 ms y eventos `#EVENT`. El origen es la primera RPM calculable a partir de dos pulsos aceptados. Se conserva el rechazo de pulsos separados por 20 ms o menos y el cero indicado despues de un segundo sin pulsos.

El capturador Python existente puede seguir separando filas y eventos. El CSV historico conserva su formato. La lectura validada y el diagnostico se describen abajo y deben usarse para el control futuro.

## Verificacion

Compilar con `pio run` desde esta carpeta. La compilacion no carga el programa a la ESP32. La comprobacion sobre la maqueta queda pendiente y debe incluir servo, pulsos, comandos, formato de captura y driver cuando su conexion este confirmada.

Las lineas de comando demasiado largas se rechazan completas hasta la siguiente nueva linea. Su fragmento final no se interpreta como otra orden.

En esta etapa se comprobo la compilacion para ESP32 y una regresion simulada frente al firmware anterior con comandos manuales, pulsos aceptados y rechazados, reinicio, movimiento gradual y muestras CSV. Tambien se verifico la ausencia de escrituras en GPIO25 con el control deshabilitado, la secuencia de salida en ambas polaridades y el descarte completo de comandos demasiado largos. Estas pruebas no sustituyen la comprobacion fisica.

## Ensayos del paso 2

El control del motor sigue deshabilitado por defecto hasta confirmar el driver. Por eso `preparar` no activa la prueba en una placa sin configurar. No se simula un apagado exitoso del motor cuando la salida esta deshabilitada.

| Comando | Accion |
|---|---|
| `preparar` | Libera el freno y ordena encender el motor. |
| `tiempo5000` | Configura cinco segundos de ensayo fijo antes de preparar. |
| `fijo47` | Desde preparacion, apaga el motor e inicia frenado fijo a 47 grados. |
| `fijo90` | Desde preparacion, apaga el motor y observa giro sin freno. |
| `estado` | Consulta el estado mediante una linea `#ESTADO`. |
| `cancelar` | Apaga el motor, libera el freno y deja el ensayo cancelado. |
| `pid` | Inicia lazo cerrado desde preparacion si la actuacion y las ganancias estan habilitadas. |

El estado inicial es `REPOSO`. Una preparacion aceptada pasa a `PREPARACION`. El inicio fijo pasa a `FIJO`. La duracion cumplida produce `FINALIZADO`, una cancelacion produce `CANCELADO` y un fallo de preparacion produce `FALLO`. Se puede preparar de nuevo desde los estados terminales.

Los limites provisionales estan en `configuracion.h`. El ensayo fijo dura diez segundos por defecto, admite entre 100 y 30000 ms y permite angulos entre 47 y 90 grados. La preparacion vence a los treinta segundos para no dejar el motor encendido esperando indefinidamente. Estos valores son configuracion inicial y no provienen de una calibracion final.

Para comenzar se exige una RPM positiva, calculable y reciente, con antiguedad maxima de 250 ms y al menos dos pulsos nuevos desde la preparacion. Una lectura rechazada permite reintentar mientras no venza la preparacion. El inicio tambien requiere que la lectura validada del paso 3 sea reciente y no sospechosa.

El operador elige cuando iniciar observando las RPM. No se regula automaticamente la velocidad inicial del motor. En esta primera secuencia se apaga el motor y se ordena el freno inmediatamente despues. No se reproduce la espera manual de los ensayos historicos y debe documentarse ese cambio de protocolo al comparar curvas.

Durante `PREPARACION` y `FIJO`, las consultas `?`, `v` y `estado`, la orden de inicio fijo y la cancelacion siguen disponibles. Se bloquean cambios manuales del servo, reinicios del reloj y otras ordenes que interfieran. `motor_off` cancela si el ensayo esta activo. El comando historico `s` no es la cancelacion del ensayo.

Al terminar por tiempo o cancelar, el motor recibe orden de apagado y el freno se libera. El disco puede seguir girando. `ENSAYO_FIN_DURACION` indica solo que termino el intervalo configurado. No certifica parada fisica ni exito de seguimiento. La confirmacion fisica de parada sigue pendiente. Una medicion invalida persistente ahora termina en fallo, no en exito.

## Registro de la secuencia

Se mantiene el CSV de tres columnas y los eventos numericos. `MOTOR_CMD` marca la orden al driver, `SERVO_CMD` marca la orden al servo y `ENSAYO_FIJO_INICIO` identifica el comienzo de cada prueba. `ENSAYO_DURACION_MS` conserva su duracion y `RPM_INICIAL_X100` guarda la RPM inicial multiplicada por cien y redondeada. Por ejemplo, 134590 representa 1345,90 RPM.

El reloj del CSV no se reinicia al preparar o empezar el ensayo. Se conservan sus eventos anteriores y cada marca pertenece a la misma escala temporal. El fin por duracion, la cancelacion y el tiempo excedido de preparacion llevan eventos distintos. Las lineas `#ESTADO` son diagnostico y el capturador Python actual las muestra sin confundirlas con muestras.

El capturador existente puede guardar estos eventos, pero el analizador MATLAB historico espera `MOTOR_OFF_MANUAL`. No se afirma que interprete automaticamente el protocolo nuevo con `MOTOR_CMD`. Su adaptacion se hara explicitamente al preparar el registro y analisis de los nuevos ensayos. Los CSV historicos permanecen intactos.

## Pruebas de estados sin hardware

Con Python 3 y `g++` disponibles, ejecutar desde esta carpeta.

```sh
python3 test/host/verificar.py
```

La prueba usa reloj, puerto serial, GPIO y servo simulados. Comprueba el rechazo con motor deshabilitado, inicio con pulsos recientes, bloqueo de comandos, fin por duracion, cancelacion desde manual y ensayo, tiempo maximo de preparacion, valores invalidos, lineas demasiado largas y desbordamientos de los relojes. Ejecuta las secuencias con ambas polaridades del driver en copias temporales, sin cambiar la configuracion real ni tocar una placa.

La compilacion con PlatformIO y estas pruebas no sustituyen verificar el cableado, las RPM y la respuesta mecanica en la maqueta.

## Diagnostico del paso 3

La interrupcion deposita tiempos de pulsos en una cola acotada y no imprime. El ciclo principal valida esos datos antes de permitir su uso para control. Si la cola se llena, se registra la perdida y se exige una nueva pareja de pulsos para recuperar la medicion.

Se mantienen el rechazo de intervalos de 20 ms o menos y sus contadores. Se conserva tambien el ultimo periodo rechazado, de modo que un pico corto no desaparece de la evidencia aunque ocurra entre dos filas seriales.

Como criterio provisional, una subida de RPM de mas de 1,8 veces la ultima validada se marca sospechosa. Se necesitan tres periodos consecutivos consistentes dentro de un 20 % para aceptar ese cambio sostenido. Una desaceleracion no se rechaza por su magnitud. Los saltos rechazados quedan contados. Esto no elimina todo pulso falso ni demuestra precision del sensor y sus umbrales necesitan calibracion.

| Estado | Significado |
|---|---|
| `SIN_PULSOS` | No se han recibido marcas aceptadas. |
| `UNA_MARCA` | Todavia no hay una pareja confiable. |
| `RECIENTE` | Hay una estimacion utilizable segun los criterios actuales. |
| `ANTIGUA` | La ultima estimacion supero su antiguedad permitida. |
| `SIN_SENAL` | Ha transcurrido mas de un segundo desde la ultima validacion. No demuestra parada. |
| `SOSPECHOSA` | Un aumento brusco espera confirmacion. |
| `DESBORDAMIENTO` | Se perdieron pulsos por capacidad de cola y se necesita recuperar medicion. |

La antiguedad permitida es tres veces el ultimo periodo, con minimo de 250 ms y maximo de un segundo. No recibir un pulso nuevo en cada vuelta del programa es normal. La lectura solo es utilizable si `valida` es verdadera. `rpm` vale NaN cuando no lo es. `rpmUltimaValida` permite investigar el ultimo valor aceptado sin confundirlo con una medicion actual.

El CSV antiguo sigue mostrando la ultima RPM aceptada y un cero de presentacion tras el silencio. El PID no debe consumir esa representacion. Para ello usa la lectura validada. Despues de un silencio prolongado, el primer pulso vuelve a anclar y el siguiente permite calcular otra velocidad.

## Diagnostico en archivos

El firmware emite `#DIAG` a intervalos de 100 ms, incluso antes de tener una primera RPM. El capturador actualizado guarda un tercer archivo `diagnostico_N.csv` junto a `datos_N.csv` y `eventos_N.csv`. Un firmware anterior que no emita diagnostico puede seguir capturandose. El tercer archivo quedara solo con su encabezado.

El diagnostico incluye tiempo, RPM cruda y validada, estado de medicion, antiguedad, periodo, contadores de aceptados y rechazados, saltos rechazados, perdidas de cola, ultimo periodo rechazado, modo, motor ordenado y tiempo de ensayo. La referencia y el error se rellenan desde el paso 4 cuando estan disponibles. La peticion del PID se registra desde el paso 5 en observacion. La accion enviada al servo se registra en PID desde el paso 6. En modo fijo o manual permanece NaN.

Antes de la primera RPM el tiempo de diagnostico vale -1. Los eventos de cambio de calidad usan `ESTADO_MEDICION`, con codigos de cero a seis en el orden de la tabla de estados anterior. El registro conserva contadores y el ultimo periodo rechazado, no una traza exhaustiva de todos los pulsos individuales.

## Fallo persistente

Durante preparacion se conceden tres segundos iniciales para obtener pulsos. Despues, o durante un ensayo fijo, una lectura invalida por 1500 ms continuos produce `FALLO_MEDICION`. La prueba se suspende, se apaga el motor y se libera el freno. Una recuperacion valida antes del limite reinicia esa espera.

Si el disco realmente se detiene antes de terminar el intervalo fijo, la ausencia de pulsos tambien puede producir este fallo. No es posible distinguir una parada real de una perdida de sensor solo por el silencio. Ese resultado no debe presentarse como exito o averia fisica confirmada. El criterio final de parada necesita calibracion e integracion con las etapas siguientes.

Para enviar comandos desde el capturador, escribirlos completos y pulsar Enter. Esto incluye `c`, `f`, `m` y `v`. Las flechas mantienen su respuesta inmediata. Enviar `cancelar` antes de `q` cuando se quiera interrumpir un ensayo. `q` cierra la captura y no es una orden al motor.

Las pruebas host incluyen pulsos cortos de 20000 RPM aparentes, saltos aislados, cambios sostenidos, desaceleracion rapida, lecturas antiguas, desbordamiento, recuperacion tras silencio, fallo persistente y lectura de diagnostico por el capturador. No se requiere pyserial para esas pruebas simuladas. La captura fisica requiere las dependencias de `herramientas/requirements.txt`.

El detalle breve de cambios y verificaciones esta en [BITACORA.md](BITACORA.md).

## Referencia lineal del paso 4

El generador esta separado del sensor, del servo y del PID en `referencia.h` y `referencia.cpp`. Recibe RPM inicial, duracion e instante inicial en milisegundos. Calcula la velocidad deseada en cada consulta, sin modificar un actuador.

$$
r(t)=\omega_0\max\left(0,1-\frac{t}{T}\right).
$$

La primera forma disponible es lineal. La separacion permite incorporar otras curvas posteriormente sin rehacer el controlador. Todavia no se implementan ni se seleccionan curvas adicionales.

Al aceptar `fijoN`, se captura una sola vez la RPM inicial validada, se apaga el motor y se inicia la referencia con la duracion del ensayo. Una medicion posterior no cambia el punto de partida. La orden `tiempoN`, enviada antes de `preparar`, establece tanto la duracion del ensayo fijo como la del descenso de referencia.

Por ejemplo, `tiempo6000` configura seis segundos. Si el ensayo empieza a 1500 RPM, la referencia vale 1500, 1000, 500 y cero RPM a los cero, dos, cuatro y seis segundos. Desde 900 RPM, esos valores son 900, 600, 300 y cero. Estas son comprobaciones matematicas, no pruebas de que la maqueta pueda seguir esas trayectorias.

Durante el ensayo fijo el servo mantiene su angulo. La referencia no lo corrige. Sirve para comparar la respuesta a lazo abierto con una curva deseada y preparar la integracion posterior del PID.

`diagnostico_N.csv` ahora incluye `referencia_rpm` y `error_rpm`. Se usa velocidad medida menos referencia. Si la lectura no es valida, el error permanece NaN aunque la referencia siga definida. Desde el paso 5, `u_solicitada` registra el calculo de observacion cuando es valido. `u_aplicada` permanece NaN en FIJO. En PID registra la orden normalizada enviada al servo.

`REFERENCIA_LINEAL_MS` registra el tipo de curva y su duracion. `RPM_INICIAL_X100` conserva la velocidad inicial con la escala documentada. El instante inicial coincide con `ENSAYO_FIJO_INICIO`. La telemetria sigue su intervalo de 100 ms, por lo que no siempre contiene una fila exactamente en ese instante. Los eventos permiten reconstruir el punto inicial.

Tras finalizar por duracion la referencia permanece en cero. Al cancelar, fallar, preparar otra prueba o reiniciar la medicion con `r`, se borra y vuelve a NaN hasta un nuevo inicio valido. `r` sigue bloqueado durante un ensayo.

Las pruebas incluyen distintas velocidades iniciales, monotonia, extremos, permanencia en cero, entradas invalidas, desbordamiento del reloj, velocidad inicial inmutable, bloqueo de cambios de duracion durante el ensayo, cancelacion, fallo y lectura de referencia y error por el capturador existente. Su formato no cambia y los CSV historicos se conservan.

## Calculo PID del paso 5

`pid.h` y `pid.cpp` contienen un controlador sin dependencias del sensor, del servo, de Serial ni de Arduino. Recibe referencia, una medicion validada con su instante real y el instante actual. `control_pid.cpp` lo ejecuta en observacion durante `FIJO` y conecta su salida al servo durante `PID`. El calculo independiente no escribe al servo ni al motor.

Las ganancias `pidKp`, `pidKi` y `pidKd` son cero por defecto. No estan ajustadas. El diagnostico muestra `GANANCIAS_CERO` para no confundir ese resultado con un controlador sintonizado. Los valores distintos de cero usados en pruebas son hipoteticos y solo existen en copias temporales de prueba.

Se usa error igual a RPM medida menos referencia. P responde al error actual. La integral acumula la contribucion de Ki por error y tiempo transcurrido. Se expresa directamente en unidades de accion y se acota entre cero y uno. La integracion se suspende si empuja mas hacia la saturacion.

Si la velocidad esta por debajo de la referencia, la accion limitada es cero y se elimina la integral acumulada. Esto evita que siga pidiendo freno por memoria anterior. Cuando el error vale exactamente cero no se fuerza esa regla de liberacion.

D usa cambios de la medicion, no cambios de referencia. Su tiempo es el intervalo entre las mediciones nuevas. Si la marca temporal se repite, no vuelve a derivar la misma muestra. Un filtro de primer orden reduce cambios bruscos de la derivada. La constante de filtro inicial es 0,1 s y requiere evaluacion experimental.

Los Kp, Ki y Kd usan RPM y segundos. Sus unidades son accion por RPM, accion por RPM segundo y accion segundo por RPM, respectivamente. Cambiar a rad/s requiere revisar las ganancias, no copiar los mismos numeros.

## Temporizacion del calculo

El periodo provisional es 20000 microsegundos, equivalente a 20 ms o 50 Hz. No es la eleccion final del proyecto. El controlador consulta tiempo y retorna sin recalcular si aun no corresponde. No usa `delay`.

La primera ejecucion calcula P con I y D inicializadas a cero. Despues usa el tiempo real transcurrido para integrar. Una ejecucion tardia no provoca rafagas de calculos para recuperar todos los periodos pendientes. Los intervalos omitidos quedan contados.

Si transcurren mas de 100 ms entre calculos, la salida se invalida con `TIEMPO_EXCEDIDO`, se registra el intervalo y se reinicia la memoria interna. Una nueva ejecucion valida reancla el calculo en observacion. En modo PID este retraso termina el ensayo con fallo y libera el freno. Los tiempos fisicos siguen pendientes de verificar.

Las mediciones invalidas, referencias invalidas, marcas temporales incoherentes y errores numericos invalidan el resultado y limpian la memoria. Una medicion invalida no se convierte en cero RPM ni se usa para integrar o derivar. Los contadores de periodos omitidos se conservan hasta reiniciar el ensayo.

`pid_tiempo_calculo_us` mide la ultima ejecucion calculada del adaptador, incluyendo lectura y referencia. No mide la latencia total de lazo, la impresion serial ni la respuesta del servo. Es necesario medir esos tiempos en la ESP32 real.

## Diagnostico PID y compatibilidad

Se agregan al final del diagnostico `pid_u_limitada`, `pid_p`, `pid_i`, `pid_d`, `pid_estado`, `pid_dt_us`, `pid_omitidos` y `pid_tiempo_calculo_us`. Las columnas anteriores conservan sus nombres y posicion.

`u_solicitada` representa la suma matematica P mas I mas D. `pid_u_limitada` representa esa peticion limitada entre cero y uno, incluyendo la regla de liberacion. `u_aplicada` permanece NaN durante FIJO y contiene la orden al servo durante PID. No presentar `pid_u_limitada` como frenado realmente aplicado por PID.

El capturador admite tanto las 18 columnas de diagnostico anteriores como las 26 actuales. Para registros anteriores deja explicita la ausencia de datos PID con `NO_DISPONIBLE`, NaN y tiempos vacios. Los CSV historicos de datos y eventos conservan su lectura.

El estado `OBSERVACION` indica calculo valido con alguna ganancia no nula durante FIJO. `CONTROLANDO` identifica el calculo en modo PID. Otros estados distinguen inactividad, falta de configuracion, medicion invalida, referencia invalida, tiempo excedido y error numerico. Al cancelar, terminar, preparar, reiniciar medicion o iniciar otro ensayo, se reinicia la memoria del controlador.

Las pruebas comprueban P, acumulacion integral, saturacion, recuperacion, derivada filtrada sin golpe de referencia, muestras repetidas, datos invalidos, reloj, retrasos y errores numericos. Incluyen una simulacion didactica que verifica el sentido de la correccion y un ensayo con ganancias no nulas donde se comprueba que el calculo no mueve el servo. Esa simulacion no identifica la maqueta ni obtiene sus ganancias finales.


## Integracion del paso 6

`pid` inicia un ensayo de lazo cerrado despues de `preparar` y de obtener una medicion inicial valida. Se apaga el motor y se captura una sola vez la RPM inicial para la referencia lineal. `tiempo6000`, enviado antes de preparar, configura un descenso de seis segundos tanto para FIJO como para PID.

El inicio exige `controlMotorHabilitado` y `actuacionPIDHabilitada`, ademas de una configuracion PID valida con alguna ganancia positiva. Ambos permisos siguen en falso y las tres ganancias en cero. Cambiarlos requiere verificar el montaje y elegir ganancias justificadas. Los valores de las pruebas automaticas solo existen en copias temporales.

La conexion comunicada por el usuario usa GPIO25 hacia IN1 del AD70178 e IN2 a tierra. Se conserva HIGH como orden provisional de encendido. Quedan pendientes la comprobacion electrica, la alimentacion compatible, el arranque y el comportamiento real de apagado. Confirmar esos resultados antes de habilitar el motor.

La accion limitada vale entre cero y uno. Cero ordena 90 grados y uno ordena 47 grados. Se usa interpolacion lineal y redondeo al grado mas cercano. Por ejemplo, 0,5 ordena 69 grados. Esto relaciona dos ordenes y no supone una relacion lineal entre angulo y torque de frenado.

`u_solicitada` es la suma P mas I mas D. `pid_u_limitada` contiene el resultado limitado antes del redondeo. `u_aplicada` expresa la orden normalizada correspondiente al angulo entero enviado. No es una medicion de posicion ni de torque. En modo manual o fijo se deja NaN. El servo solo recibe una nueva orden si cambia el angulo entero y el control automatico detiene cualquier rampa manual pendiente.

Si una medicion deja de ser valida se libera inmediatamente el freno y se reinicia la memoria PID. La recuperacion permite continuar mientras no se cumpla el fallo persistente de 1500 ms. Los errores numericos, entradas invalidas y retrasos mayores de 100 ms terminan el ensayo, apagan el motor y liberan el freno. `cancelar` hace lo mismo con estado de cancelacion. Los comandos manuales que interfieren permanecen bloqueados durante PID.

Al terminar la referencia no se declara exito por tiempo. Se mantiene la referencia en cero y se buscan RPM validadas de 100 o menos durante 300 ms continuos. Si no se confirma en dos segundos adicionales, termina con `PID_FIN_NO_CONFIRMADO`. Estos tres valores son provisionales. La confirmacion es de baja velocidad estimada y no certifica parada exacta. El silencio del sensor sigue siendo una medicion invalida y puede producir fallo aunque el disco se haya detenido realmente.

Las pruebas simuladas verifican conversion, limites, permisos, ganancias nulas, control del servo, liberacion por debajo de referencia, fallos, cancelacion, final de ensayo y desbordamiento del reloj. Tambien comprueban captura de modo PID y accion aplicada. Falta verificar sin contacto y despues con la maqueta. La etapa 7 incluye ajuste y comparacion experimental.
