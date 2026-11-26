# Bitácora breve del firmware

Rama de trabajo `dg/feat/control-frenado-pid`. Base de referencia `17be651`. Las entradas registran cambios locales y verificaciones, no commits ni pruebas físicas realizadas.

## 25 de noviembre de 2026 — Paso 1

Se separaron medición, freno, motor, comandos y registro. Se conservaron los comandos manuales y el CSV de tres columnas. GPIO25 quedó reservado para el driver, con el control deshabilitado hasta confirmar su conexión y polaridad.

Se verificaron la compilación ESP32, los comandos, los pulsos y movimientos comparados con la versión anterior, el rechazo de líneas largas y ambas polaridades de salida mediante simulación.

Quedaron pendientes el cableado del driver y las pruebas físicas. No se cargó firmware a la placa.

## 25 de noviembre de 2026 — Paso 2

Se agregaron reposo, preparación, ensayo fijo, finalización, cancelación y fallo. Se incorporaron `preparar`, `fijoN`, `tiempoN`, `estado` y `cancelar`. Se bloquearon comandos que interfieren durante el ensayo.

Se registran las órdenes de motor y servo, velocidad inicial y duración. La prueba fija acaba por tiempo y no afirma detectar la parada física. El modo PID sigue sin implementar.

Se verificaron compilación ESP32 y pruebas simuladas de estados, medidas iniciales, cancelación, tiempo de preparación, bloqueo de comandos y desbordamiento de los relojes.

Quedaron pendientes las pruebas físicas y el diagnóstico completo del sensor.

## 25 de noviembre de 2026 — Paso 3

Se agregó una cola acotada de tiempos de pulso, con contadores de pérdida. La interrupción no imprime ni calcula RPM. La validación ocurre en el ciclo principal.

La lectura distingue ausencia de pulsos, una sola marca, valor reciente, valor antiguo, silencio prolongado, salto sospechoso y desbordamiento. Una lectura inválida entrega NaN para control. El cero del CSV histórico queda únicamente como presentación.

Se conserva el filtro de 20 ms y el último periodo rechazado. Se agregó un criterio provisional de aumento brusco de RPM, con confirmación para cambios sostenidos. Las desaceleraciones rápidas no se rechazan por su magnitud.

Un fallo persistente de medición suspende el ensayo, apaga el motor y libera el freno. El silencio no distingue una parada real de una pérdida del sensor y no se registra como éxito automático. Los umbrales necesitan calibración física.

El capturador guarda `diagnostico_N.csv` además de los dos archivos anteriores. Incluye validez, antigüedad, periodos, rechazos, modo y motor. Los campos futuros de referencia y PID quedan como NaN hasta implementarse.

Se corrigió el teclado del capturador para escribir comandos completos con Enter. Las antiguas teclas rápidas consumían la primera letra de órdenes como `fijo47`, `motor_on` y `cancelar`. Las flechas conservan su funcionamiento inmediato.

Se verificaron 27 escenarios nativos de estados y medición, además de la integración del capturador, los CSV históricos, el diagnóstico y los comandos completos. La compilación para ESP32 pasó. No se cargó firmware a la placa.

Quedan pendientes la calibración de umbrales, la comprobación física del driver, la adquisición real con el capturador y la adaptación explícita de MATLAB al protocolo automático. Los archivos y el análisis de la Tarea 2 se conservan.

## 25 de noviembre de 2026 — Paso 4

Se agregó un generador de referencia lineal separado de la medición, el servo y el PID. Al iniciar un ensayo se fija una sola vez la velocidad inicial validada y se usa la duración configurada con `tiempoN`.

La referencia desciende hasta cero y permanece allí tras el fin normal. Se invalida ante cancelación, fallo, nueva preparación o reinicio de medición. No cambia el ángulo fijo ni activa seguimiento automático.

El diagnóstico ahora guarda referencia y error. El error usa velocidad medida menos referencia y queda como NaN cuando la medición es inválida. Las acciones del PID siguen sin calcularse. Se registra el evento `REFERENCIA_LINEAL_MS` sin cambiar el formato del capturador ni los CSV históricos.

Se verificaron las secuencias anteriores y las pruebas del generador con varias velocidades, duración, monotonía, extremos, datos inválidos y desbordamiento del reloj. También se comprobó que la referencia no se reancla con cada nueva RPM y que el capturador conserva referencia y error. La compilación para ESP32 pasó. No se cargó firmware a la placa.

La duración físicamente alcanzable y el rango de velocidades siguen pendientes de la maqueta. Queda abierta la incorporación de otras formas de curva después de completar la primera referencia.

## 25 de noviembre de 2026 — Paso 5

Se agregó el cálculo PID independiente de Arduino y un adaptador de observación durante el ensayo fijo. No aplica su resultado al servo. Las ganancias iniciales son cero y se identifican como no ajustadas.

Se implementaron P, integral condicional con límites y D filtrada sobre mediciones nuevas. La acción limitada queda entre cero y uno. Si la velocidad es inferior a la referencia, se pide liberar y se elimina la acumulación integral.

El periodo provisional es 20 ms y se usa el tiempo real transcurrido. Se cuentan periodos omitidos y se invalidan los cálculos con retraso excesivo, medición inválida, referencia inválida o error numérico. La memoria se reinicia en los cambios de ensayo.

El diagnóstico agrega términos P, I y D, salida limitada y datos de temporización. La acción aplicada por PID queda como NaN. El capturador acepta los diagnósticos anteriores y actuales sin cambiar los CSV históricos de datos y eventos.

Se verificaron los cálculos con datos conocidos, límites, liberación, anti-windup, muestras repetidas, filtrado, retrasos y reloj. Una simulación didáctica comprobó el sentido de la acción sin afirmar representar la maqueta. Con ganancias de prueba no nulas, se comprobó que el cálculo no cambia el servo. La compilación ESP32 pasó.

No se cargó firmware a la placa. Las ganancias, el periodo y el filtro definitivos requieren diseño y ensayos físicos. GPIO25 sigue deshabilitado hasta verificar el driver. Su identificación comunicada es mini L298N AD70178 y todavía no se verificaron módulo físico, terminales ni comportamiento de apagado.

## 25 de noviembre de 2026 — Confirmación del producto del driver

El usuario confirmó el Mini L298N 2-Channel DC Motor Drive Module, código AD70178. Se localizó la [ficha de MicroJPM](https://www.microjpm.store/products/ad70178), con alimentación publicada de 2 a 10 V y señales de 1,8 a 7 V.

Queda identificado el producto comercial. Siguen pendientes la conexión del módulo físico, sus estados de mando y la condición eléctrica de apagado. No se deduce el chip instalado ni una tabla lógica solo del título comercial.

La fuente histórica indicaba 1 V, por debajo del mínimo publicado para el driver. Se debe revisar la alimentación junto con el motor real antes de conectarlo. GPIO25 permanece deshabilitado.

## 25 de noviembre de 2026 — Paso 6

Se integró el modo PID con la preparación, apagado del motor, referencia lineal y servo. La acción limitada se convierte al rango provisional de 90 a 47 grados y se registra la orden normalizada después del redondeo. Esa orden no mide torque ni posición real.

La medición inválida libera el freno mientras se espera recuperación. Los fallos persistentes, errores numéricos y retrasos excesivos terminan el ensayo. Cancelar apaga el motor, libera el freno y limpia el controlador. El final exige confirmación provisional de baja velocidad después de completar la referencia y tiene un tiempo adicional máximo.

Se conserva deshabilitada la actuación PID y el control del motor. Las ganancias siguen en cero. El usuario confirmó IN1 como señal de control e IN2 a tierra en el AD70178. La compatibilidad eléctrica y el comportamiento físico siguen pendientes.

Pasaron las pruebas nativas de integración, conversión, permisos, órdenes bloqueadas, liberación, recuperación, cancelación, fallos, final de ensayo, relojes y capturador. La compilación para ESP32 pasó. No se cargó firmware a la placa.

## Próximo avance

Verificar primero los pasos anteriores en la maqueta y las órdenes del servo sin presión de frenado. Después continuar con la etapa 7 para elegir ganancias, confirmar tiempos y umbrales, y comparar frenado fijo contra PID con repeticiones.

## 25 de noviembre de 2026 — Panel de diagnóstico en la PC

Se agregó una interfaz local con gráficas de velocidad cruda y validada, referencia, error, acción solicitada y limitada, orden al servo, ángulo y términos P, I y D. Incluye controles de ensayo, consulta, cancelación, calibración manual y eventos. La vista puede pausarse sin detener la captura.

El modo ESP32 reutiliza la validación del capturador y conserva el protocolo y los CSV. La recepción serial ocurre fuera de la interfaz. Se guarda una carpeta por conexión con datos, eventos, diagnóstico, texto serial y metadatos. El cierre de la ventana no cancela el ensayo físico.

El modo simulado compila en la PC los archivos reales de PID y conversión angular, con una planta ficticia y medición ideal. No emula toda la ESP32 ni su sensor. Sus parámetros y capturas quedan separados de los reales y no modifican el firmware.

Se verificaron pruebas automatizadas de simulación nativa, límites, pico sintético, captura, sesiones, comandos, servidor local y lectura serial fragmentada. Pasaron también las pruebas existentes del firmware y capturador. Se comprobó la interfaz en el navegador. Falta verificar la conexión serial física y el montaje. No se cargó firmware a una placa.


## 25 de noviembre de 2026 — Giro libre desde el panel

Se agregó el botón Giro libre · sin freno, que utiliza `fijo90`. Después de preparar apaga el motor y mantiene el servo en la posición liberada. La referencia y el cálculo PID quedan como observación y no gobiernan el frenado. No cambia el protocolo ni requiere cargar otro firmware.

Se documentó que terminar por duración no demuestra parada y que la captura continúa. Se agregó una prueba que verifica motor apagado, ángulo liberado y desaceleración por rozamiento idéntica con ganancias nulas y con Kp de uno. La posición liberada y el efecto del driver siguen pendientes de comprobación física.


## 25 de noviembre de 2026 — Selección de figura de referencia

Se agregó un selector de referencia lineal, exponencial normalizada y coseno suave en el panel para la simulación. La figura elegida genera tanto la curva dibujada como la entrada de referencia al PID. Puede cambiarse antes de conectar o aplicarse entre ensayos, con bloqueo durante preparación y ejecución.

La captura conserva la figura inicial en metadatos y los cambios en eventos `REFERENCIA_TIPO`, con códigos cero, uno y dos respectivamente. No cambian las columnas de diagnóstico. Las tres formas conservan la velocidad inicial y llegan a cero en la duración elegida.

El firmware físico sigue usando solo la lineal. El panel bloquea otras selecciones al conectar ESP32 y el servidor rechaza mandos de figura dirigidos al dispositivo. No se cargó firmware ni se cambiaron ganancias de la placa.

Pasaron ocho pruebas del panel, incluidas formas, extremos, monotonía, referencia usada por el PID, bloqueo de cambios, trazabilidad y rechazo de opciones físicas no soportadas. Se verificó el selector en el navegador. Quedan pendientes integración física de las nuevas curvas y comprobación de su alcanzabilidad.


## 25 de noviembre de 2026 — Modos panel y terminal

Se agregó `--modo terminal` al mismo programa de PC. Muestra métricas, calidad de señal, temporización, minigráficas y eventos, y recibe comandos completos con Enter. El modo panel sigue siendo predeterminado. Ambos utilizan el mismo receptor y protocolo sin cambiar el firmware.

La terminal admite ESP32 o simulación, conserva el registro de datos y marca la interfaz en metadatos. La captura se guarda por separado bajo la carpeta terminal. No abre un navegador ni servidor web y restaura la pantalla y la entrada al cerrar. Cerrar no envía una cancelación implícita.

Pasaron doce pruebas de panel y terminal. Incluyen una sesión en pseudoterminal con simulación, cambio de curva, giro libre, cancelación, archivos y restauración del estado de terminal. Se verificaron datos ausentes, avisos de diagnóstico antiguo y rechazo de comandos inválidos. La conexión física sigue pendiente de prueba. No se cargó firmware ni se hicieron cambios en las ganancias o habilitaciones del motor.


## 26 de noviembre de 2026 — Búsqueda de puertos USB

La búsqueda del panel enumeraba los puertos ttyS del sistema y elegía el primero como sugerencia, aunque no correspondiera a una ESP32. Se modificó para sugerir dispositivos USB y terminales ttyUSB o ttyACM. Se conserva la entrada manual de otros puertos. Se agregó una prueba con 32 puertos ttyS y dispositivos USB para comprobar el filtrado. No se abrió el puerto de la placa ni se modificó el firmware.

### Selección automática del puerto USB

Al seleccionar ESP32, el panel busca los puertos USB sin abrirlos. Antes de conectar vuelve a consultar la lista. Selecciona el único puerto disponible y conserva una selección vigente cuando hay varios. Si hay varios sin una selección válida, pide elegir. Sigue disponible la entrada manual para puertos que no aparecen en la búsqueda. La conexión permanece bajo el botón del usuario.

### Diagnóstico temporal del sensor desde terminal

Agrega `sensor_on` y `sensor_off` para observar llamadas de la misma ISR FALLING, con tiempo, nivel leído y contadores, mediante una cola acotada. La activación no cambia el modo ni la función de interrupción. No agrega filtros, no modifica el conteo y conserva un pulso por vuelta. Se permite únicamente en reposo con motor ordenado apagado y bloquea preparación y encendido mientras está activo.

La terminal muestra las llamadas, guarda `sensor_1.csv`, conserva `serial.txt` e informa pérdidas de captura. El nivel es una lectura dentro de la ISR y no sustituye una medida de osciloscopio. Incluye pruebas del conteo inalterado incluso si el nivel leído ya es alto, pulsos cortos, cola llena, continuidad de FALLING, bloqueo del motor, formato CSV y presentación.

### Terminal con historial para diagnosticar FALLING

La vista predeterminada de terminal imprime líneas y mantiene el historial en lugar de redibujar toda la pantalla. Los registros ISR llegan a una cola acotada de presentación y se imprimen con tiempo, nivel y contadores. Si la presentación pierde mensajes, avisa y remite al CSV. La captura conserva su propio flujo y formato. La vista anterior se selecciona con `--vista-terminal panel`. Este cambio corresponde al programa Python y no requiere volver a cargar firmware.

### Corrección del doble conteo del sensor

Sustituye la aceptación directa de cada FALLING por un detector de secuencias de niveles mediante CHANGE. Observar ambos bordes no aumenta dos veces el contador. Solo cuenta una zona activa completa después de una zona libre suficientemente larga. Descarta notificaciones del mismo nivel y transiciones breves. Conserva un pulso por vuelta y el cálculo del periodo entre entradas a marcas completas.

Los mínimos iniciales son 100 microsegundos por nivel, configurables y pendientes de comprobar en el montaje. Al iniciar dentro de la zona activa se descarta el primer fragmento. La interrupción no imprime ni bloquea con delay. El diagnóstico sigue disponible y muestra los cambios de la misma ISR que usa el detector nuevo.

Se verificaron marcas estrechas de 200 microsegundos a unas 1800 RPM, marcas anchas a baja velocidad, perturbaciones breves, repetición de niveles, arranque dentro de marca y desbordamiento del reloj. Pasaron las pruebas del firmware y la compilación ESP32. Se adaptaron las señales de las pruebas de integración para entregar los dos niveles reales de una marca en lugar de invocar una ISR sin señal. Falta cargar y verificar el conteo físico. No se realizaron commits ni cargas automáticas.

### Caducidad del estado UNA_MARCA

Corrige el estado que permanecía indefinidamente en UNA_MARCA si no se había calculado una velocidad. Se registra el instante de recepción de la última marca aceptada y el tiempo de espera también se aplica cuando solo existe una referencia de giro. Pasado un segundo sin nueva marca, el estado es SIN_SENAL y la velocidad sigue siendo inválida.

Al recibir una marca tras un silencio mayor que ese límite, se usa como nueva referencia. No se calcula velocidad a través de una pausa ni se alterna entre UNA_MARCA y una lectura ya caducada. Las vueltas manuales separadas más de un segundo pueden contarse, pero no proporcionan RPM válidas con este límite. Se agregan pruebas de una marca aislada, pasos lentos, recuperación con dos marcas próximas y vuelta a cero de los relojes.

### Habilitación del control del motor

Se activa controlMotorHabilitado para probar motor_on y motor_off con GPIO25 conectado a IN1 e IN2 a tierra. La salida activa sigue siendo HIGH. La actuación del PID permanece deshabilitada. Requiere cargar este firmware y verificar físicamente el encendido y apagado.

### Rango provisional del freno según calibración manual

Se establece 45 grados como liberado y 15 grados como máximo automático a petición del usuario. El disco ya queda libre a 40 grados. Se observaron contacto leve a 35, roce a 33, frenado a 30 y frenado fuerte a 25. Los 15 grados son el máximo provisional elegido, no una medida de torque ni una calibración dinámica final.

Preparación, cancelación, finalización y liberación del PID utilizan ahora 45 grados. La acción normalizada va de 45 a 15 grados. El panel acepta ensayos fijos entre 15 y 45, propone inicialmente 30 y usa fijo45 para giro libre. La simulación obtiene los extremos desde la conversión del firmware. La calibración manual conserva su rango de 0 a 90 grados y los comandos explícitos como g90 conservan su significado. La actuación PID sigue deshabilitada.

### Margen de preparación para el arranque real

Se amplía tiempoMaximoPreparacionMs de 30000 a 60000 tras observar que el motor tarda aproximadamente 40 segundos en alcanzar 1400 RPM. La simulación y las instrucciones usan el mismo límite. No modifica la duración de la referencia ni inicia el frenado automáticamente por velocidad.

### Cero estimado en pantalla tras ausencia de pulsos

Completa la presentación acordada de cero tras un segundo sin detecciones. El panel y la terminal muestran cero estimado cuando el firmware informa SIN_SENAL, la antigüedad es al menos un segundo y ya se habían recibido marcas. La serie cruda de la gráfica se interrumpe al caducar para no prolongar una velocidad antigua. La tarjeta y la leyenda identifican la estimación.

Los campos originales de RPM, los CSV de medición y la entrada del PID se conservan. No se genera cero por desconexión de Python ni por desbordamiento de cola. Los nuevos campos son derivados de presentación. No requiere cargar otro firmware, solo reiniciar Python y recargar el panel.

### Secuencia automática de corte e inicio por RPM

Agrega auto_preparar, auto_fijoN y auto_pid. Un ciclo armado desde reposo acelera con servo liberado a 45 grados, apaga el motor al alcanzar una medición válida de 1400 RPM y espera en DESCENSO_LIBRE. Una medición nueva válida igual o inferior a 1300 RPM inicia el ángulo fijo y la referencia desde el valor realmente medido. La duración de ensayo comienza en ese instante, sin incluir aceleración ni descenso libre.

El panel envía la duración elegida al iniciar desde reposo. Sus botones de ciclo fijo, libre y PID arman toda la secuencia sin otro clic durante el giro. Preparar sigue disponible como paso opcional. Las órdenes anteriores de ensayo manual se conservan. El PID físico permanece bloqueado hasta ajustar y habilitar su actuación.

Se registran umbrales, ángulo armado, corte real e inicio real sin modificar columnas CSV. El descenso tiene límite de 15 segundos además de los 60 de preparación. Cancelar, fallos y pérdida persistente de medición borran lo pendiente y liberan el mecanismo. La simulación lee umbrales y tiempos desde el firmware compilado. Su objetivo predeterminado pasa a 1500 RPM para superar el corte de 1400.

Incluye pruebas de ciclo fijo, giro libre, PID habilitado solo en prueba, cancelación en ambas fases, medición sospechosa, ausencia de datos, espera agotada, armado durante descenso y continuidad del reloj. La validación física sigue pendiente. No se realizan cargas ni commits automáticos.

### Captura del descenso libre automático

Corrige el importador de diagnóstico para reconocer DESCENSO_LIBRE. Antes conservaba esas líneas en serial.txt pero las omitía del CSV de diagnóstico y de la gráfica. La prueba del ciclo automático ahora pasa todas las muestras por el importador y verifica que se guarden completas, incluido el descenso. No cambia el firmware ni las mediciones.
