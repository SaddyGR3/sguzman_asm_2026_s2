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

## 27 de noviembre de 2026 — Aplicación de escritorio

Se agrega banco_frenado.py como entrada a una ventana nativa con PySide6, sin navegador ni servidor HTTP. El arranque selecciona automáticamente el entorno .venv de herramientas y lo prepara si faltan PySide6 o pyserial. Se elimina la dependencia del entorno temporal para este flujo. Las dependencias nuevas están separadas en requirements-escritorio.txt.

La ventana reutiliza Banco para mantener conexión, simulación, validación y formatos CSV. Conserva tarjetas, cinco gráficas, referencias, ganancias simuladas, ciclos automáticos, pausa, ventana temporal, exportación PNG, diagnóstico y eventos. Añade botones visibles para motor y diagnóstico de sensor. La selección USB detecta un único dispositivo sin abrirlo y mantiene elección explícita si hay varios.

Conexión, compilación y cierre se ejecutan fuera del hilo visual. El cierre de una fuente física activa solicita cancelación y espera confirmación antes de desconectar. La interfaz identifica una cancelación no confirmada o una conexión perdida sin afirmar una parada. El panel y terminal anteriores se conservan. No se modificó ni cargó firmware.

Se agregan pruebas de ventana fuera de pantalla, simulación completa con CSV, exportación PNG, selección USB, pausa, errores y cierre confirmado. La comprobación física de esta interfaz queda pendiente. No se hacen commits ni pushes.

Resultado de verificación de la interfaz de escritorio. Pasaron las 29 pruebas de escritorio, panel y terminal. Se revisó visualmente una corrida simulada en la ventana y se comprobó el arranque desde un Python sin pyserial global mediante el entorno local. La ventana nativa se abrió sin conectar automáticamente hardware.

### Ajuste visual de la aplicación de escritorio

Señal y temporización, Eventos y órdenes y Sensor GPIO34 se muestran en tres cajas paralelas. Los 15 campos de señal se presentan completos mediante etiquetas, sin desplazamiento interno. Kp, Ki y Kd comparten una fila. Se comprobó la distribución en ventanas de 1080 y 1440 píxeles de ancho. No cambia el firmware ni los comandos del banco.

## 27 de noviembre de 2026 — Arranque y final del ensayo con una marca

Se mantiene marcasPorVuelta en uno. El intervalo minimo se calcula a partir de un limite provisional exclusivo de 3000 RPM y del numero de marcas. Conserva los 20 ms anteriores con una marca y pasa a 3333 microsegundos con seis. Los tiempos minimos de zona libre y negra siguen en 100 microsegundos. Una comprobacion de compilacion rechaza combinaciones incompatibles. La antiguedad ya depende del periodo medido entre marcas y conserva un minimo de 250 ms y un maximo de un segundo. Este limite deja sin velocidad valida los giros muy lentos y no equivale a medir cero.

Una marca que empieza antes de una pausa prolongada podia completarse al reanudar el giro. La siguiente marca llegaba pronto respecto de esa confirmacion, pero su intervalo entre entradas incluia la pausa. Se impide usar intervalos superiores a un segundo o marcas activas de mas de un segundo como medidas de arranque. Al reanclar se limpia el periodo crudo para no presentar una RPM de la pausa. Una prueba reproduce una permanencia de cien segundos sobre negro y comprueba la recuperacion sin la lectura falsa.

En FIJO se admite continuar hasta la duracion configurada cuando se observaron al menos tres muestras nuevas durante el ensayo, la ultima velocidad valida no supera 400 RPM ni la mitad de la inicial, el motor esta apagado y la medicion pasa a SIN_SENAL. Emite FIJO_POSIBLE_PARADA_SIN_PULSOS y al completar el tiempo ENSAYO_FIN_DURACION_SIN_SENAL. No certifica parada ni sustituye NaN por cero en el control o el CSV. Una perdida de sensor despues de desacelerar puede producir la misma evidencia. Los criterios son provisionales y requieren observacion fisica.

Una nueva medida valida registra FIJO_SENAL_RECUPERADA y vuelve a evaluar la condicion. Datos sospechosos, desbordamiento y reanclaje invalidan la evidencia de baja velocidad. La perdida a alta velocidad o sin muestras suficientes sigue causando FALLO_MEDICION. PID conserva su proteccion y su criterio de fin anteriores, queda deshabilitado y con ganancias cero. No se cargó firmware ni se hicieron commits o pushes.

La bateria completa de firmware y capturador paso, incluidas las regresiones de marca detenida, fin fijo sin señal, perdida a alta velocidad, lectura baja aislada, recuperacion y dato sospechoso antes del silencio. Pasaron las pruebas especificas con una y seis marcas. La compilacion PlatformIO para ESP32 fue exitosa y las 30 pruebas de escritorio, panel y terminal tambien pasaron. Pendiente cargar y observar el nuevo arranque y el final en la maqueta con una marca.

## 27 de noviembre de 2026 — Comparacion MATLAB de las capturas actuales

Se agrega comparar_giro_y_freno.m sin modificar el analizador historico de Tarea 2. Compara la captura libre 20261127_190400_799594 a 45 grados con la frenada 20261127_185956_618751 a 30 grados. Valida eventos, duracion, angulo, motor apagado y ausencia de perdidas de cola. Alinea el tiempo de ensayo registrado por la ESP32, conserva NaN y distingue la referencia de las medidas. Señala el evento de posible parada sin convertirlo en un cero medido.

Genera grafica PNG, figura editable FIG, tabla CSV y datos MAT en resultados_reales. El resumen incluye velocidades iniciales, ultima medicion valida, primer registro bajo 500 RPM y pendiente de velocidad entre 0,5 y 2,5 segundos. Las pendientes son aproximadamente -75,286 y -340,569 RPM por segundo. Este calculo exploratorio no identifica ni valida un modelo y no demuestra repetibilidad.

La funcion se ejecuto con MATLAB R2026a en modo batch. Termino sin errores y genero los cuatro archivos. Se contrastaron ambas pendientes mediante un calculo independiente en Python y se verifico que los huecos del frenado se conservan. Se reviso visualmente el PNG generado por MATLAB. No se uso Control System Toolbox ni se modificaron capturas originales. No se realizaron commits ni pushes.

## 27 de noviembre de 2026 — Alineacion del montaje reorganizado

Se agrega alinear_ensayos_frenado.m para el giro libre 20261127_200435_402416 y las dos frenadas a 30 grados 20261127_200152_802180 y 20261127_200642_850954. La captura posterior 20261127_200805_778882 solo contiene movimientos manuales y no se usa como ensayo completo. La funcion acepta una cantidad variable de capturas mediante configuracion con carpeta, nombre y angulo. Los grupos de distintos montajes se deben mantener separados.

Cada curva usa tiempo original de diagnostico menos ENSAYO_FIJO_INICIO. No se desplazan ni reescalan velocidades. Se conservan 60 registros por captura y los NaN de las frenadas. Los tiempos iniciales originales son 187593, 27519 y 317857 ms. El campo tiempo_ensayo_ms coincide a menos de 20 ms, con un desfase observado maximo de 11 ms. El codigo de registro lee ese campo despues del tiempo de captura e imprime por serial entre ambas lecturas. Los dos campos se exportan y la diferencia se muestra en el resumen.

La funcion termino correctamente en MATLAB R2026a. Se comprobo la resta temporal en todos los registros, igualdad de velocidades originales y graficadas, y ausencia de interpolacion. Se reviso el PNG generado y se guardaron FIG, MAT, resumen y CSV alineados por corrida. Las curvas frenadas resultan cercanas sin haberlas forzado a coincidir. Este paso solo alinea y compara, no ajusta ni valida un modelo. No se modificaron capturas originales, firmware ni ganancias y no se hicieron commits ni pushes.

## 27 de noviembre de 2026 — Pendientes entre 0,5 y 1,5 segundos

Se agrega estimar_pendientes_frenado.m sobre los ensayos ya alineados. Usa la misma ventana solicitada, diez registros validos por corrida y ajuste lineal de velocidad frente a tiempo. Conserva tiempos efectivos y datos originales sin interpolar. Se obtuvieron aproximadamente -76,053 RPM/s en giro libre y -544,109 y -530,425 RPM/s en las dos frenadas a 30 grados.

La figura compara los puntos originales y las rectas con escalas iguales. Se guardan resumen CSV, PNG, FIG y MAT separados de la alineacion. Las aceleraciones equivalentes son -7,964, -56,979 y -55,546 rad/s². La resta descriptiva respecto del giro libre da 468,056 y 454,372 RPM/s de perdida adicional, sin aislar torque ni dependencia del angulo porque se recorren velocidades distintas.

Se ejecuto sin errores en MATLAB R2026a, se verificaron las pendientes con un calculo independiente en Python y se reviso visualmente el PNG. Este paso describe un tramo y no identifica un modelo completo ni valida repetibilidad. No se modificaron capturas, firmware o ganancias. No se hicieron commits ni pushes.

## 27 de noviembre de 2026 — Desaceleracion natural en tres velocidades

Se agrega analizar_desaceleracion_libre.m para la captura 20261127_200435_402416. Aprovecha el registro posterior al fin del ensayo de seis segundos, comprobando orden de motor apagado, servo a 45 grados, modos FIJO o FINALIZADO y ausencia de fallos y perdidas de cola en todo el tramo. No modifica el firmware, la duracion del ensayo ni las capturas.

Usa tres ventanas de dos segundos con veinte registros validos cada una. De 0,5 a 2,5 segundos, velocidad media de 1183,224 RPM y pendiente de -74,304 RPM/s. De 8,5 a 10,5 segundos, 664,101 RPM y -57,646 RPM/s. De 15,5 a 17,5 segundos, 288,870 RPM y -50,236 RPM/s. Los valores describen una sola desaceleracion y pueden incluir registros que repiten estimaciones entre marcas. Orientan la eleccion de un modelo, sin demostrar que la resistencia dependa solamente de la velocidad ni separar mecanismos fisicos.

La funcion termino correctamente en MATLAB R2026a. Se contrastaron las tres pendientes con un calculo independiente en Python y se reviso visualmente el PNG. Guarda CSV, PNG, FIG y MAT en resultados_reales. La carpeta de captura y las ventanas son configurables. No se hicieron commits ni pushes.

## 27 de noviembre de 2026 — Modelo de giro libre con corrida reservada

Se agrega modelar_giro_libre.m. Usa 20261127_200435_402416 y 20261127_200805_778882 para ajustar y reserva 20261127_210612_886523 para comprobar predicciones. La captura 200805, antes solo manual, recibio despues un giro libre completo y se selecciona desde ENSAYO_FIJO_INICIO. La ventana fijada es de 0,5 a 17,5 segundos, con 170 registros validos por corrida. No se cambian ni mezclan los archivos originales.

Se ajusta dn/dt = -a - b*n con n en RPM usando su solucion temporal y fminsearch. Parametros aproximados a de 39,048666 RPM/s y b de 0,028239020 inversos de segundo. Cada corrida aporta su primera medida como condicion inicial. La tercera no interviene en el ajuste y sus predicciones posteriores no se corrigen con nuevas medidas. Se excluye esa condicion inicial de las metricas, dejando 169 registros evaluados por corrida.

El modelo alternativo de desaceleracion constante se ajusta con las mismas dos corridas y da 62,652234 RPM/s de perdida. En la captura reservada el RMSE mixto es 2,813161 RPM frente a 27,682653 del constante. El error absoluto medio mixto es 2,308884 RPM y su maximo 7,374065 RPM. Son resultados bajo las mismas condiciones y rango de velocidad, sin validar parada, torque, servo, otros discos ni generalizacion a otras condiciones iniciales. Las lecturas repetidas no constituyen replicas independientes ni se usan para inferencia estadistica.

La ejecucion MATLAB R2026a termino correctamente. Se contrastaron los parametros por una optimizacion independiente en Python, eliminando analiticamente a y buscando b, y se reviso el PNG generado. Se guardan CSV de parametros, metricas y predicciones, PNG, FIG y MAT. No se modifico firmware ni se habilito PID. No se realizaron commits ni pushes.

## 27 de noviembre de 2026 — Hipotesis de aporte constante para 30 grados

Se agrega modelar_frenado_30.m. Las nuevas corridas 20261127_211944_350811 y 20261127_212026_949598 ajustan c30, y 20261127_212109_143576 queda reservada. Conserva los parametros libres y usa una ventana de 0,5 a 2 segundos, con quince registros por captura y catorce evaluados tras excluir la condicion inicial. Valida 30 grados en la ventana, motor apagado y ensayo completo sin perdidas de cola.

El ajuste analitico de errores cuadrados da c30 aproximadamente 439,090141 RPM/s en dn/dt = -a - b*n - c30. Los RMSE de ajuste son 25,103 y 28,130 RPM. En la captura reservada RMSE 44,384, MAE 32,353 y error maximo 105,763 RPM. Es una primera aproximacion y no se declara un modelo validado para todo el frenado o todos los angulos.

La figura incluye la prediccion y el error firmado, que tiende a volverse negativo al final de la ventana reservada. La ultima lectura de 436,32 RPM tiene 273591 microsegundos de antiguedad y periodo de 137515 microsegundos. La comparacion actual de velocidad predicha instantanea frente a estimaciones retenidas por periodo puede contribuir al error. Pendiente estudiar el tiempo y la ventana fisica de la medicion antes de atribuir las diferencias al modelo o añadir terminos. No se transforma esa ausencia de validacion en una conclusion sobre torque variable.

La ejecucion MATLAB R2026a termino correctamente, se contrastaron parametro y metricas mediante Python y se reviso el PNG. Se guardan parametros, metricas, predicciones, PNG, FIG y MAT. No se modifico firmware ni se habilito PID y no se hicieron commits ni pushes.

## 27 de noviembre de 2026 — Comparacion del freno mediante intervalos medidos

Se implementa comparar_frenado_por_intervalos.m y se completa la revision temporal pendiente. Mantiene las dos primeras frenadas nuevas para ajuste, la tercera reservada y los parametros libres fijos. Se confirma en medicion.cpp que antiguedad_us mide tiempo desde la entrada de la ultima marca validada. Reconstruye final de intervalo como tiempo de registro menos antiguedad y comienzo como final menos periodo. Las RPM permanecen intactas. La resolucion del registro y sus lecturas no simultaneas limitan la precision temporal reconstruida.

Agrupa por pulsos_aceptados, comprueba consistencia de periodos y finales y usa cada intervalo una vez. En cada corrida hay quince filas en la ventana de 0,5 a 2 segundos, trece intervalos unicos y doce evaluados tras excluir la media inicial. Calcula el promedio integral de la solucion del modelo en cada intervalo. La primera media determina una condicion inicial compatible, no una velocidad instantanea. Solo c30 se ajusta. Los tiempos observados de la reservada se usan para evaluar el operador de medicion, sin corregir estados ni reajustar parametros. No es una prediccion ciega de tiempos de pulso.

El c30 por intervalos es aproximadamente 490,024589 RPM/s. Para comparar con la misma ponderacion se reajusta el metodo instantaneo en los mismos intervalos unicos y resulta 451,027879 RPM/s. En la reservada MAE baja de 29,645 a 17,547 RPM, RMSE de 38,307 a 23,345 y error maximo de 82,728 a 48,781. El valor anterior de MAE 32,353 usaba las quince filas con repeticiones y no constituye la referencia directa de esta comparacion. Sigue una tendencia negativa al final de la ventana, por lo que no se declara el modelo definitivo ni se atribuye toda diferencia a la sincronizacion.

Se ejecuto correctamente en MATLAB R2026a, se contrastaron parametros y metricas mediante Python y se reviso el PNG. Una integracion numerica independiente de las trayectorias coincidio con las medias analiticas con discrepancia maxima aproximada de 0,0000000074 RPM. Se verificaron RPM exportadas contra los originales e intervalos causales. Se guardan tablas auditables de intervalos, parametros, metricas, PNG, FIG y MAT. No se modificaron capturas ni firmware, no se habilito PID y no se hicieron commits ni pushes.

## 27 de noviembre de 2026 — Diagnostico de diferencias entre frenadas

Se agrega revisar_repeticiones_freno.m, manteniendo intacto el modelo comun c30 de 490,024589 RPM/s y las metricas reservadas anteriores. No añade terminos. El ajuste individual diagnostico da aproximadamente 494,482701, 485,390363 y 456,603746 RPM/s, diferencias de +0,91, -0,95 y -6,82 por ciento respecto del comun. Los MAE dentro de cada ajuste son 7,258, 6,680 y 5,233 RPM. El ajuste individual de la tercera usa sus datos, por lo que es diagnostico posterior y no una nueva validacion independiente.

La tercera es compatible con un aporte menor bajo esta ecuacion. Las tres conservan una curvatura residual parecida despues de ajustar individualmente, sin demostrar que toda desviacion se deba a un unico parametro o a una causa mecanica concreta. Coexisten indicios de variacion entre corridas y una simplificacion comun del modelo. Se mantiene la ecuacion provisional sin añadir dependencia adicional de velocidad. Una futura seleccion basada en este diagnostico requerira datos nuevos para su comprobacion independiente.

Se ejecuto correctamente en MATLAB R2026a y se contrastaron los valores con Python. Se reviso visualmente el PNG y se guardaron resumen, detalles por corrida, PNG, FIG y MAT en un subdirectorio separado. No se modificaron las capturas, el modelo comun ni el firmware, y no se habilito PID. No se hicieron commits ni pushes.

## 27 de noviembre de 2026 — Caracterizacion de 33, 28 y 25 grados

Se agrega caracterizar_angulos_freno.m para los nuevos grupos y una referencia recalculada a 30 grados. Se identificaron tres corridas completas a 33 grados, tres a 28 y cuatro tramos de corridas a 25 que terminaron con FALLO_MEDICION. Se conservan esos estados originales. El grupo de 30 utiliza las tres corridas anteriores y no se mezcla como si fueran nuevas.

Se fija una banda comun permitida de 500 a 1100 RPM y comienzo fisico posterior a 0,25 segundos. El rango realmente disponible se exporta por corrida. Se reconstruyen intervalos, se usan medias del modelo y se eliminan repeticiones de la misma marca, sin modificar RPM ni rellenar huecos. Las dos primeras corridas de cada angulo ajustan el aporte comun, la tercera lo comprueba y la cuarta de 25 aporta otra comprobacion parcial. Los parametros libres se mantienen fijos. Los ajustes individuales se presentan solo como diagnostico.

Aportes comunes aproximados de 197,656849 RPM/s a 33 grados, 494,276611 a 30, 867,452766 a 28 y 1150,264531 a 25. Rangos individuales de 176,417 a 246,376, de 469,235 a 501,530, de 851,325 a 870,475 y de 1105,225 a 1187,682 respectivamente. No son intervalos estadisticos de confianza ni definen una ley continua del servo. El valor a 30 se recalcula para esta banda y no reemplaza el modelo anterior.

En la banda hay entre veinte y veintiseis intervalos por corrida a 33, once o doce a 30, seis o siete a 28 y cuatro a seis a 25. Los dos ultimos grupos tienen pocos intervalos. Los errores absolutos medios de comprobacion son aproximadamente 30,002 RPM a 33, 12,266 a 30 y 5,386 a 28. Los dos parciales reservados a 25 dan 4,280 y 9,864 RPM. Son resultados locales, sin validar frenado completo, parada, otros montajes ni una interpolacion entre angulos.

Las ultimas velocidades validas de las cuatro pruebas a 25 son aproximadamente 430, 528, 503 y 538 RPM. Superan el umbral de 400 RPM del criterio provisional de posible parada y el ensayo termina por ausencia persistente de señal. El usuario observo que el frenado fisico a 25 es muy rapido, aproximadamente 1,5 segundos o incluso menos de uno. Se registra esa observacion cualitativa sin convertirla en tiempo exacto de parada ni sustituir el fallo del protocolo. Es compatible con detenerse antes de completar otra vuelta, pero los CSV solos no distinguen esa situacion de una perdida del sensor.

El analisis completo se ejecuto correctamente en MATLAB R2026a y los aportes y metricas se contrastaron mediante Python. Se verifico que hay trece corridas contando la referencia anterior, nueve completas y cuatro parciales. Tambien se verifico el rechazo de las parciales cuando permitirParciales es false. Se revisaron visualmente mapa y comprobaciones y se corrigieron legibilidad y espaciado. Se guardan inventario, resumen, intervalos, PNG, FIG y MAT en caracterizacion_angulos_actual. No se cambiaron firmware, ganancias, limites o capturas originales. No se habilito PID y no se hicieron commits ni pushes.


## 27 de noviembre de 2026 — Frenado suave y referencia de veinte segundos

Se revisaron nueve capturas de veinte segundos. Hay tres a 35 grados, dos a 34 y una a 36, 37, 38 y 45. Las tres previas de seis segundos a 35 quedan separadas. Todas las nuevas terminan por duracion, sin convertir esa finalizacion en confirmacion de parada. La duracion tambien cambia la recta de referencia dibujada y explica parte de la semejanza observada con el giro libre.

Se agrega caracterizar_frenado_suave.m. El analizador general admite ahora, solo mediante opciones explicitas, grupos exploratorios con menos de tres corridas y aportes de signo libre para diagnosticar discrepancias. Las opciones nuevas estan desactivadas por defecto. Los grupos con menos de tres capturas se etiquetan sin comprobacion reservada y su metrica reservada es NaN.

Con la misma banda de 500 a 1100 RPM y modelo de promedios por intervalo, los aportes locales resultan 52,972878 RPM/s a 35, 157,215680 a 34, 8,954416 a 36, 12,139394 a 37, 2,746039 a 38 y 1,056225 a 45. Se conservan a y b del modelo libre anterior. El aporte de 45 es un diagnostico de discrepancia del modelo libre, no evidencia de contacto del freno. No se fuerza monotonia ni interpolacion entre angulos.

Las dos primeras de 35 ajustan el parametro. La tercera reservada da MAE 3,308120 RPM, RMSE 3,576631 y maximo absoluto 4,777547. Los ajustes individuales de las tres son 52,062814, 53,982251 y 53,927355 RPM/s. A 34 se obtienen 170,311736 y 147,656532 individualmente, sin tercera reservada. En los angulos con una corrida los errores son de ajuste, no de validacion. La prueba de 45 registra dos saltos rechazados. Las demas no registran saltos o pulsos cortos rechazados y ninguna presenta perdidas de cola. No se rellenaron huecos ni se alteraron capturas.

Se ejecuto el analisis en MATLAB R2026a y se contrastaron los seis aportes y la metrica reservada mediante un calculo independiente en Python. Se comprobaron nueve filas, cantidades completas por grupo y ausencia de metricas reservadas en grupos sin reserva. Se revisaron los PNG de mapa y curvas. Los resultados se guardan en resultados_reales/frenado_suave_20s. No se modificaron firmware, ganancias o referencias implementadas y no se habilito el PID. No se hicieron commits ni pushes.

La comprobacion final en MATLAB confirmo que los cuatro aportes de los grupos anteriores se conservan con diferencia menor de 0,001 RPM/s y que un grupo de una corrida se rechaza con las opciones predeterminadas. La ejecucion termino correctamente.


## 27 de noviembre de 2026 — Cuatro comprobaciones nuevas de 34 grados

Se incorporan los ensayos 32, 33, 34 y 35 de las capturas 20261127_233312_551495, 20261127_233407_607995 y 20261127_233951_894077. La captura intermedia contiene dos ensayos y un reinicio temporal entre ellos. Se agrega seleccion explicita mediante #ensayo=N y separacion por epocas en eventos y diagnostico, sin modificar los originales ni ordenar juntas las dos epocas. Se exigen conteos de reinicios coincidentes y selector no ambiguo. Los identificadores y exportaciones distinguen ambos ensayos.

Se mantienen las dos corridas anteriores para ajustar c34 de 157,215680 RPM/s y se comprueban las cuatro nuevas sin reajuste. Hay seis corridas completas por duracion a 34 y trece en el analisis suave. En 500 a 1100 RPM los ensayos nuevos aportan 28, 29, 27 y 29 intervalos unicos. Sus MAE son 10,049033, 6,162445, 3,116020 y 4,869212 RPM y el conjunto da 6,066301 RPM. El maximo absoluto entre las cuatro es 20,787556 RPM. Los parametros individuales posteriores son solo diagnosticos y no modifican el modelo.

Los saltos rechazados permanecen constantes durante cada ensayo, dos en los ensayos 32 y 33 y cuatro en 34 y 35. Son contadores acumulados, no nuevos rechazos durante estos frenados. No aumentan los pulsos cortos rechazados y no hay perdidas de cola. Las cuatro finalizan por duracion con ausencia de señal, sin convertir el final en una medida de parada. Se conserva 38 grados solo como evidencia exploratoria y no se propone como angulo util de control. La posicion liberada sigue en 45.

Los calculos se contrastan con Python y el analisis se ejecuta en MATLAB. Se conservan las limitaciones de banda, condicion inicial por primera media y tiempos de intervalos observados. No se cambia firmware, no se habilita PID y no se hacen commits ni pushes.


## 27 de noviembre de 2026 — Primera simulacion local con modelo medido

Se agrega simular_modelo_medido.py como estudio separado del panel y sin conexion a hardware. Carga a y b del modelo libre y aportes de 28, 30, 33, 34 y 35 de los resultados MATLAB. Reutiliza los archivos PID y conversion angular reales mediante el puente nativo existente. No ejecuta la planta ficticia de ese puente. La medida es ideal a 20 ms y los estados completos de la ESP32 no se simulan.

Se limita la propagacion a 500 a 1100 RPM y a ordenes entre 28 y 45 grados, con final explicito si se sale de esos limites. Se supone ausencia de contacto desde 36, interpolacion lineal entre nodos y dinamica del aporte de contacto de primer orden con constante supuesta de 0,12 segundos. No se presenta como ley de servo identificada. 38 se conserva solo como captura exploratoria y no se usa como nodo. La condicion inicial es 1100 RPM con contacto liberado y controlador reiniciado, sin pretender reproducir el ensayo completo anterior a ese punto.

Se comparan libre, fijo35, fijo34, P y PI en el tramo local de rectas de 1300 a cero en 6 y 20 segundos. La comparacion de error usa referencia de 1050 a 550 RPM y marca si una corrida no la cubre. Un barrido nominal de veinte parejas de Kp y Ki selecciona entre las probadas P con Kp 0,04 y PI con Kp 0,04 y Ki 0,01. Kd cero. Los MAE a 6 segundos son aproximadamente 204,53, 139,23, 10,75, 9,01 y 6,34 RPM. No son ganancias fisicamente validadas ni resultado de optimizacion global.

El PI nominal cambia de grado 115 veces en unos 2,77 segundos. La sensibilidad con constante supuesta de 0,25 segundos pide angulos menores que 28 y se interrumpe por salir del modelo. No se declara robustez ni inestabilidad fisica con estos resultados. La recta de 20 segundos requiere 65 RPM/s, menos que el rozamiento natural calculado a 1100 RPM, por lo que el principio del tramo exige un aporte negativo imposible solo con freno. Los casos fijos de 20 segundos dejan la banda antes de cubrir la comparacion completa.

Se exportan barrido, metricas, sensibilidad, alcanzabilidad, trayectorias, PNG y JSON con parametros y huellas de las fuentes. La solucion analitica libre se contrasto con su formula cerrada y el sistema velocidad-contacto con una integracion RK4 independiente refinada, con discrepancia maxima de unos 0,000000000006. Se reviso la figura y la compilacion nativa usa advertencias como errores. Falta representar una marca por vuelta y reconsiderar la frecuencia de cambios del servo. No se modifican la app, el firmware, las ganancias o la habilitacion del PID. No hay commits ni pushes.


## 28 de noviembre de 2026 — Nuevas mediciones de frenado fuerte

El usuario confirma que el rango de trabajo es de 45 a 25 grados y que 26 frena de golpe. Se distingue ese rango del limite de modelo a 28 utilizado en la simulacion anterior. La configuracion del firmware aun conserva minimo de 15 y queda pendiente alinear ese rango antes de habilitar PID fisico. No se modifica ahora.

Se analizan los ensayos 36 a 39 de las capturas 20261127_235851_459064, 20261127_235944_106032, 20261128_000037_647391 y 20261128_000124_438590. Hay una a 25, dos a 26 y una a 27. Las duraciones configuradas son 6, 6, 10 y 6 segundos. Todas terminan con FALLO_MEDICION. Las ultimas RPM validas son 510,86, 500,87, 508,40 y 417,53, por encima de 400. El criterio de posible parada no llega a armarse. No se confunde este fallo con prueba de giro persistente ni con confirmacion de parada.

Se agrega caracterizar_frenado_fuerte.m, reutilizando el analizador por intervalos y manteniendo a y b anteriores. En la banda de 500 a 1100 RPM y con inicio fisico posterior a 0,25 segundos hay 6, 6, 6 y 8 intervalos unicos. Los aportes estimados son aproximadamente 1027,732076 RPM/s a 25, 1007,248683 a 26 y 780,508334 a 27. Los ajustes individuales de 26 son 1001,438819 y 1013,173442. Ninguno tiene corrida reservada y todos son ajustes exploratorios de tramos parciales. La nueva estimacion a 25 no reemplaza la anterior y la de 27 no respalda monotonia respecto del grupo anterior de 28. No se actualiza aun el mapa de simulacion.

No aumentan los contadores de rechazos durante los ensayos y no hay perdidas de cola. El contador acumulado de saltos permanece en cuatro. Se conserva el diagnostico y cada captura original. Se guardan resumen, corridas, intervalos, graficas y MAT en resultados_reales/frenado_fuerte_25_26_27. Se contrastan calculos con Python y se ejecutan en MATLAB. No se cambia firmware, no se habilita PID y no se hacen commits ni pushes.


## 28 de noviembre de 2026 — Configuracion de dos marcas por vuelta

El usuario agrega una segunda marca para evaluar la medicion durante frenados rapidos. Se cambia marcasPorVuelta de uno a dos en configuracion.h. El calculo de RPM validada y cruda ya divide el periodo por ese factor. El filtro minimo se deriva del numero de marcas y conserva el limite exclusivo de 3000 RPM, pasando de veinte a diez milisegundos. No se cambia el detector de una marca completa, el periodo de registro, el timeout de señal ni las ganancias.

Las marcas deben estar aproximadamente separadas media vuelta. Una separacion desigual puede generar RPM alternas aun con velocidad real constante. La comprobacion manual pasa a veinte conteos en diez vueltas. Las nuevas capturas deben registrarse por separado e identificarse con dos marcas. Los analisis historicos mantienen una marca y las opciones de nuevas reconstrucciones deben indicar dos.

Se adapta verificar.py para mantener los casos historicos con una marca explicita y ejecutar las variantes de marcas con uno, dos y seis. La sustitucion de configuracion usa una expresion regular para no depender del numero actual. La prueba por variante comprueba 1500 RPM, el rechazo de 4500 RPM y la recuperacion despues de ausencia de señal. No se cambian los valores esperados de los casos historicos para ocultar diferencias.

Se actualiza la guia de pruebas fisicas. La precision y continuidad con las dos marcas quedan pendientes de comprobar en la maqueta despues de cargar. No se carga firmware automaticamente, no se habilita PID y no se hacen commits ni pushes.

La verificacion final termino correctamente. Todas las secuencias de verificar.py pasaron, incluidas las variantes de una, dos y seis marcas con calculo de RPM, filtro y recuperacion. PlatformIO compilo esp32dev con exito, con 26068 bytes de RAM y 300229 bytes de flash. El binario esta generado pero no se cargo en la ESP32.


## 28 de noviembre de 2026 — Primeros resultados fisicos con dos marcas

Se revisan las capturas 20261128_005740_418983 a 28 grados, 20261128_010024_258929 a 27 y 20261128_010110_023010 a 26. Son ensayos 1, 2 y 3 de ocho segundos. Los tres terminan con ENSAYO_FIN_DURACION_SIN_SENAL y emiten antes FIJO_POSIBLE_PARADA_SIN_PULSOS. Ninguno llega a FALLO_MEDICION. El final por tiempo y la posible parada no se convierten en instante medido de detencion.

Las ultimas RPM validas son 262,39 a 28, 224,83 a 27 y 268,69 a 26. Las filas aparecen aproximadamente a 1,657, 1,810 y 1,477 segundos desde inicio. Frente a las muestras anteriores de una marca a 26 y 27 se observa mayor cobertura de velocidades bajas. No se declara exactitud absoluta ni se atribuye toda variacion al numero de marcas. No aumentan los rechazos durante los frenados ni hay perdidas de cola. A 26 el acumulado de saltos permanece en tres y los otros ensayos en cero.

Se agrega caracterizar_dos_marcas.m con marcasPorVuelta igual a dos, salida separada y una corrida exploratoria por angulo. Se mantiene el modelo libre anterior. En 500 a 1100 RPM hay seis intervalos unicos a 26 y ocho a 27 y 28. Los aportes ajustados son aproximadamente 929,819888, 700,968614 y 722,282669 RPM/s respectivamente. No hay comprobaciones reservadas y la diferencia de orden entre 27 y 28 impide declarar una ley monotona exacta. Se conservan los modelos anteriores y no se actualiza aun el simulador.

Se comprueba la conversion de todas las RPM recientes finitas contra periodo y dos marcas, con discrepancia menor de 0,006 RPM. Los parametros se contrastan con un calculo independiente en Python y se ejecuta MATLAB. Se exportan resumen, corridas, intervalos, PNG, FIG y MAT a primeras_pruebas_dos_marcas. No se modifica firmware, no se habilita PID y no se hacen commits ni pushes.

El primer intento de lectura detecto falsamente un reinicio en la captura de 28 grados porque RPM_INICIO usa cero literal y se emitio despues de ESTADO_MEDICION con tiempo 465. Se corrige el lector de analisis para omitir ese aviso y filas sin tiempo de origen al construir epocas. No se cambia el registro original ni el firmware. Se repite el analisis y se comprueba tambien la captura historica con dos ensayos separados por un reinicio real.

La ejecucion corregida de MATLAB termino con exito. Se verificaron las tres corridas completas por duracion, el factor de dos marcas y la ausencia de metricas reservadas. Los tres aportes coinciden con Python con diferencia menor de 0,001 RPM/s. La comprobacion de las trece corridas suaves historicas tambien paso, incluida la separacion del reinicio real y la conservacion de c34. Se reviso el PNG y git diff --check no reporto errores.


## 28 de noviembre de 2026 — Comprobacion libre con dos marcas

Se revisan las corridas a 45 grados y veinte segundos de 20261128_010755_149886 y 20261128_010906_181118, ensayos 4 y 5. La captura intermedia 20261128_010900_470325 no inicia un ensayo y se excluye. Ambas usadas terminan por duracion, con lecturas recientes de unas 145 y 122 RPM al final. No aumentan los rechazos durante el ensayo y no hay perdidas de cola. Los saltos acumulados permanecen en seis y once respectivamente.

Se agrega validar_giro_libre_dos_marcas.m, manteniendo intactos a y b del modelo libre anterior. Cada prediccion es el promedio del modelo en el intervalo fisico de media vuelta observado. Solo la primera media fija la condicion inicial. Las demas no realimentan la prediccion. Hay 97 y 96 intervalos unicos en 500 a 1100 RPM y se excluye el primero de cada corrida de las metricas.

Los MAE son 9,508765 y 9,322390 RPM, RMSE 13,941533 y 13,474136 y maximos absolutos 26,510544 y 26,362613. La tendencia global resulta cercana, con un residuo periodico por paridad del contador. Los intervalos pares quedan aproximadamente veinte RPM sobre la prediccion y los impares mas cerca. Es compatible con separacion desigual entre marcas, sin identificar la geometria ni demostrar una causa unica. No se reajusta el modelo para absorber esa alternancia.

El lector de intervalos se extrae a leer_intervalos_frenado.m y se comparte con caracterizar_angulos_freno. Se preservan los filtros, origen temporal, seleccion de reinicios y deduplicacion. Se conserva el modelo anterior y el firmware no cambia. Se exportan tablas, diagnostico por paridad, PNG, FIG y MAT a validacion_libre_dos_marcas. Se contrastan las metricas mediante Python y se ejecuta MATLAB. Queda pendiente revisar separacion angular y simular el ritmo de actualizacion antes de recomendar ganancias fisicas. No se hacen commits ni pushes.


## 28 de noviembre de 2026 — Preparacion del primer PID fisico proporcional

El usuario decide avanzar hacia PID conservando temporalmente la separacion imperfecta entre marcas. Se agrega simular_pid_dos_marcas.py para estudiar el ritmo de dos marcas, muestras retenidas con su fecha real y sectores ligeramente desiguales. Se integra el avance angular y se localizan los cruces de marca por biseccion. La planta usa el modelo libre anterior, los nuevos aportes de dos marcas a 26, 27 y 28 y el aporte parcial a 25, junto con los nodos anteriores de 30 a 35. Interpolacion, frontera de contacto y dinamica de contacto siguen siendo hipotesis no validadas.

Se comparan Kp de 0,0025, 0,005, 0,0075, 0,01, 0,015 y 0,02 con Ki y Kd cero. Hay dieciocho casos por ganancia y todos cubren la banda comun en este estudio local. Se elige 0,005 para el primer ensayo por limitar la amplitud de cambios. El peor MAE verdadero simulado es de 103,30 RPM, el error positivo maximo de 126,94 y el salto angular maximo de tres grados. El caso nominal supuesto cambia de grado 106 veces. Ganancias mayores reducen error pero aumentan los saltos. No se declara una sintonia final ni robustez fisica garantizada.

Se habilita actuacionPIDHabilitada con pidKp de 0,005, Ki y Kd cero y se cambia el minimo automatico de 15 a 25. Se conservan dos marcas, periodo de 20 ms, criterio final de baja velocidad, cancelacion, liberacion al quedar debajo de referencia y fallos por medicion o tiempos. La app nativa, el formulario web y el backend limitan los ensayos fijos a 25 a 45. El rango manual no cambia. Cada inicio PID registra ganancias escaladas por un millon, numero de marcas y extremos angulares para identificar la configuracion en sus eventos.

El puente nativo añade calcularMuestra sin romper la llamada anterior y toma los tiempos del filtro y PID de configuracion.h. El estudio ideal inicial conserva su rango historico en una copia temporal. Los nuevos estudios no cambian la placa ni abren puertos. Se actualizan README y guia fisica para una primera recta de seis segundos con el boton Iniciar ciclo PID. Se informa que aun puede haber un final sin confirmar baja velocidad cuando faltan pulsos al detenerse.

Los tests historicos fijan explicitamente una marca y PID bloqueado con ganancias cero, independientes del ajuste fisico actual. Se añade pid_config_actual_test.cpp, compilado contra la configuracion real sin sustituciones, para comprobar inicio, limites de actuacion, telemetria, cancelacion, liberacion bajo referencia y perdida de señal con dos marcas. Se ajustan las pruebas de rango del panel y conversion angular a 25 a 45. No se carga firmware automaticamente y no se hacen commits ni pushes.

La verificacion final paso todas las secuencias host, incluidas las tres pruebas contra la configuracion fisica actual, y las treinta pruebas de la aplicacion. PlatformIO genero el binario esp32dev con exito, con 26068 bytes de RAM y 300633 bytes de flash. El sensor simulado se comprobo por separado a 1200 RPM constantes, cuarenta pulsos por segundo con dos marcas, periodos de sectores desiguales y retencion de la fecha entre pulsos. Se reviso el PNG y se reprodujo el estudio inicial con su rango historico. git diff --check no reporto errores. La prueba real con estas ganancias queda pendiente de cargar el firmware y ejecutar el ensayo.


## 28 de noviembre de 2026 — Primer ensayo fisico de control proporcional

Se revisa 20261128_014245_541966. Los eventos confirman Kp 0,005, Ki y Kd cero, dos marcas, rango 25 a 45 y referencia lineal de seis segundos. El corte automatico se registra a 1400,23 RPM y el inicio a 1296,68. El seguimiento se analiza sin reajustar parametros ni modificar el controlador.

Se agrega evaluar_ensayo_pid.py para una sola corrida por captura, con configuracion y final identificados en sus eventos. Exporta trayectorias y metricas sin completar huecos. En 59 lecturas validas durante la referencia, entre 0,044 y 5,833 segundos, el MAE medido es 107,249153 RPM y RMSE 110,338691. Los errores quedan entre 7,13 y 151,10 RPM sobre la referencia. En la banda comun de referencia de 1050 a 550 hay 23 lecturas y MAE 108,212609. Las lecturas repetidas siguen contando como registros temporales y no como nuevas muestras independientes. No son errores respecto de una velocidad verdadera externa.

Se registran 204 ordenes de servo incluyendo la inicial y la liberacion final, con extremos 28 y 45. El maximo dt PID observado es 20016 microsegundos y no hay periodos omitidos. El tiempo maximo de calculo registrado es 82 microsegundos, sin convertirlo en medida de toda la latencia. No aumentan rechazos ni hay perdidas de cola. El seguimiento muestra un sesgo positivo sostenido, compatible con la ganancia proporcional inicial.

El final es FALLO_MEDICION alrededor de 7,4 segundos. La ultima estimacion valida de 187,19 RPM se repite en varias filas y tiene antiguedad cercana a 390 milisegundos en la ultima. Cuando la medicion se invalida se libera a 45 y la falta persistente de señal termina con fallo. Se conserva ese estado, sin afirmar parada exacta ni giro persistente. No se cambia el criterio para ocultarlo.

Se guardan metricas, seguimiento, ordenes, diagnostico JSON y PNG en evaluacion_pid_20261128_014245_541966. Se revisa por separado seguimiento y final. Queda como siguiente ajuste posible estudiar una integral pequena para reducir sesgo con Kd cero. La evaluacion no modifica ganancias, firmware ni capturas. No hay commits ni pushes.


## 28 de noviembre de 2026 — Preparacion de PI exploratorio

El usuario pide dejar el cambio de ganancias listo para build, conservando el ajuste mediante firmware. Se mantiene Kp en 0,005 y Kd en cero y se cambia Ki de cero a 0,0005. Se actualiza la prueba de configuracion real para comprobar Ki y su evento escalado a 500. No cambia la app ni el criterio de finalizacion. Ki sigue pendiente de validacion por simulacion de pulsos y prueba fisica. No se carga firmware ni se hacen commits o pushes.

La verificacion host completa paso, incluidas las tres secuencias de configuracion PI actual y la comprobacion del evento Ki con valor 500. PlatformIO compilo correctamente esp32dev con 26068 bytes de RAM y 300637 bytes de flash. git diff --check paso. El binario queda preparado sin cargar en la placa.


## 28 de noviembre de 2026 — Primera corrida fisica PI

Se evalua 20261128_020032_114925 con Kp 0,005, Ki 0,0005 y Kd cero confirmados por eventos. Se conserva referencia lineal de seis segundos, dos marcas y rango de 25 a 45. Inicio a 1297,02 RPM, comparable con 1296,68 del ensayo proporcional 20261128_014245_541966.

El MAE de lecturas validas durante la referencia es 85,638 RPM frente a 107,249 del proporcional. En la banda comun de referencia de 1050 a 550 RPM, ambas con 23 registros, baja de 108,213 a 90,000 RPM, aproximadamente 17 por ciento. Es comparacion de una corrida por configuracion, no prueba de repetibilidad ni de causalidad exclusiva del ajuste. Las estimaciones retenidas tambien cuentan entre registros. La integral crece hasta cerca de 0,25 de accion normalizada antes de invalidarse la medicion.

Final FALLO_MEDICION alrededor de 7,445 segundos. Ultima estimacion valida 156,37 RPM en fila 5,933 segundos con antiguedad 566688 microsegundos. No demuestra esa velocidad instantanea ni confirma momento de parada. No hubo nuevos pulsos cortos rechazados, saltos rechazados, perdidas de cola ni periodos PID omitidos. Se conserva el criterio de finalizacion y no se cambian ganancias tras esta revision. Se guardan metricas, seguimiento, ordenes, diagnostico y PNG en evaluacion_pid_20261128_020032_114925. Figura revisada visualmente.


## 28 de noviembre de 2026 — Tamano del titulo de escritorio

Se reduce el titulo Sistema de control de frenado de 23 a 12 pixeles para igualar el tamano de ESP32 conectada. Se conserva la negrita del titulo. No cambia el firmware ni las ganancias.


## 28 de noviembre de 2026 — Dos repeticiones del PI

Se revisan 20261128_020345_514910 y 20261128_020451_045680. Ambas confirman Kp 0,005, Ki 0,0005, Kd cero, referencia de seis segundos, dos marcas y rango de 25 a 45. MAE en banda comun de referencia de 1050 a 550 RPM de 90,5252 y 92,6870 RPM, frente a 90,0004 de la primera corrida PI. Cada corrida tiene 23 registros en la banda. Promedio de las tres 91,0709 RPM, frente a 108,2126 de una sola corrida proporcional. Las tres PI muestran comportamiento semejante en esta banda, sin demostrar repetibilidad de la configuracion proporcional ni sintonia definitiva.

Ambas terminan en FALLO_MEDICION, alrededor de 7,188 y 7,454 segundos. Ultimas estimaciones validas retenidas de 208,63 y 138,06 RPM. No hay incrementos de rechazos ni perdidas de cola y no se omiten periodos PID. En la segunda repeticion hay medicion ANTIGUA a 5,532 y 5,632 segundos, liberacion temporal y recuperacion a 5,732 con integral reiniciada. Los pulsos escasos a baja velocidad siguen afectando el cierre. No se completa con cero medido ni se afirma el instante de parada. Se revisan las dos figuras y se conservan resultados en evaluacion_pid de cada captura. No se cambian ganancias, firmware ni capturas originales.


## Pendiente de comprobar con seis marcas precisas

Las tres corridas PI con dos marcas muestran seguimiento semejante, pero el tramo final presenta mediciones antiguas, liberaciones temporales y FALLO_MEDICION por ausencia de pulsos. Por decision del usuario se continua el desarrollo con dos marcas y se pospone esta revision hasta disponer de seis marcas uniformemente espaciadas.

Se espera que seis marcas precisas reduzcan el intervalo entre mediciones y el efecto de los sectores desiguales, mejorando la medicion a baja velocidad y reduciendo las interrupciones del control. Es una mejora esperada, pendiente de verificacion fisica. No garantiza confirmar la parada cuando dejan de llegar pulsos ni resolver por si sola todo FALLO_MEDICION.

Al cambiar el disco a seis marcas, configurar marcasPorVuelta en seis y comprobar seis pulsos aceptados por vuelta. Repetir la referencia lineal de seis segundos y revisar antiguedad, liberaciones, error y final registrado antes de dar el pendiente por resuelto. De momento no se cambian el numero de marcas, las ganancias ni los criterios de finalizacion del firmware.


## 28 de noviembre de 2026 — Candidato PI con Ki de 0,001

Se amplía simular_pid_dos_marcas.py para seleccionar Kp y Ki desde argumentos, conservando por defecto el estudio proporcional anterior. Se comparan Kp 0,005 y Ki cero, 0,0005 y 0,001 con Kd cero. Dieciocho escenarios por ajuste, con variacion de contacto, fuerza de frenado y desigualdad de sectores. Todos cubren la banda de referencia de 1050 a 550 RPM. Peor MAE real simulado de 103,3031, 93,2908 y 84,3408 RPM respectivamente. Salto maximo de tres grados en los tres ajustes. Los errores no cambian de signo en la banda evaluada. Se revisa la figura y se guardan resultados en comparacion_pi_0005_001.

Es un estudio local desde 1100 RPM con integral y contacto iniciales cero. No reproduce la integral acumulada antes del tramo ni los fallos del firmware completo o la parada. Se prepara Ki 0,001 como candidato fisico autorizado, conservando Kp 0,005 y Kd cero, dos marcas y referencia de seis segundos. La prueba de configuracion real comprueba Ki 0,001 y su evento escalado 1000. No cambia la app ni el criterio final. No se carga firmware ni se hacen commits o pushes.

Verificacion completada. Pasan todas las secuencias host, incluidas las tres de configuracion real con Ki 0,001. PlatformIO genera esp32dev con 26068 bytes de RAM y 300637 de flash. Se verifica por separado que los dieciocho pares de escenarios reducen el MAE al pasar de Ki 0,0005 a 0,001 y que se conserva el resultado proporcional de referencia. git diff --check no reporta errores. Binario listo para Upload, sin cargar en la ESP32.


## 28 de noviembre de 2026 — Dos corridas con Ki de 0,001

Se revisan 20261128_021202_017479 y 20261128_021255_173621. Ambas confirman Kp 0,005, Ki 0,001, Kd cero, referencia lineal de seis segundos, dos marcas y rango de 25 a 45. En banda comun de referencia de 1050 a 550 RPM, con 23 registros por corrida, MAE medido de 76,001739 y 78,710870 RPM. Promedio 77,356304 RPM frente a 91,070870 de las tres corridas con Ki 0,0005, reduccion descriptiva de aproximadamente 15 por ciento. Las curvas medidas quedan por encima de la referencia en las lecturas validas. No se atribuye todo cambio exclusivamente a Ki ni se afirma validacion de todo el frenado.

Durante las lecturas validas de referencia, MAE 71,307222 y 74,352075 RPM, pero las ventanas terminan a 5,332 y 5,289 segundos. No comparar esas metricas globales como si tuvieran cobertura temporal identica a las anteriores. La integral alcanza 0,3824 y 0,3857 de accion normalizada y la orden minima es 27 grados. No hay nuevos rechazos, perdidas de cola ni periodos PID omitidos.

Ambas terminan en FALLO_MEDICION alrededor de 6,915 y 6,872 segundos. Ultimas estimaciones validas retenidas de 227,79 y 228,43 RPM, con antiguedad cercana a 312 milisegundos. No demuestran velocidad instantanea ni tiempo de parada. Se conserva el pendiente de revision con seis marcas precisas, sin frenar el avance autorizado con dos. Figuras revisadas visualmente y resultados guardados por captura. No se cambian ganancias ni firmware tras esta revision.


## 28 de noviembre de 2026 — Prueba directa de Ki 0,004

El usuario interrumpe la comparacion simulada y solicita preparar directamente Ki de 0,004 para probar en la maqueta. Se mantiene Kp de 0,005, Kd cero, dos marcas, referencia de seis segundos y rango de 25 a 45. Se actualiza la comprobacion de configuracion real y su evento Ki escalado a 4000. No se afirma validacion simulada ni fisica del nuevo candidato. No cambia la app ni la logica de control o finalizacion. No se carga firmware ni se hacen commits o pushes.

Verificacion completada. Pasaron todas las secuencias host, incluidas las pruebas contra la configuracion actual con Ki 0,004 y evento 4000. Build esp32dev correcto, RAM 26068 bytes y flash 300641 bytes. git diff --check paso. El binario queda listo para Upload, sin cargar en la placa.


## 28 de noviembre de 2026 — Revision de quiebres con Ki de 0,004

Se evaluan 20261128_021904_990831 y 20261128_022016_138549. La conexion 20261128_022009_157450 no tiene ensayo PID y se excluye. Ambas corridas confirman Kp 0,005, Ki 0,004, Kd cero y referencia de seis segundos. En banda comun de referencia de 1050 a 550 RPM, 23 registros por corrida, MAE de 37,156522 y 41,679130 RPM. Promedio 39,417826 frente a 77,356304 de las dos corridas Ki 0,001. Las dos nuevas cubren sesenta registros validos durante la referencia, MAE global 46,636333 y 55,157667, pero no se usa esa metrica para comparar ventanas diferentes.

La revision visual y el codigo pid.cpp muestran un comportamiento relevante para los quiebres. Cuando error medido menos referencia es negativo se libera toda la accion y se pone integral_ a cero. Con Ki 0,004 aparecen ciclos de acumulacion, cruce bajo referencia, liberacion a 45 grados y reconstruccion de integral. En la primera corrida se observan liberaciones cerca de 2,7 y 5 segundos. En la segunda, cerca de 2,6 y 4,6 segundos. Por ejemplo, alrededor de 2,6 a 2,7 segundos la integral pasa de aproximadamente 0,5 a cero. Hay errores negativos pequenos, hasta -2,29 y -5,33 RPM en la banda comun. Las filas de diagnostico y PID tienen un desfase, por lo que no se igualan como un solo calculo instantaneo.

Esto identifica una contribucion concreta de la logica del controlador a las oscilaciones de orden. No demuestra que toda irregularidad mecanica provenga de ella ni separa por completo el efecto de las marcas imprecisas. No se debe atribuir exclusivamente a Ki o esperar que seis marcas corrijan por si solas el reinicio de integral. Proximo punto a discutir es conservar la liberacion bajo referencia y revisar por separado la gestion de integral, sin aumentar ganancias a ciegas. No se modifica el controlador durante esta revision.

La primera corrida registra ENSAYO_PID_FIN_BAJA_RPM a unos 6,301 segundos, con estimacion retenida de 98,73 RPM. Es cumplimiento del criterio actual de fin a baja velocidad, no confirmacion de parada exacta. La segunda termina FALLO_MEDICION a 7,446 segundos, ultima estimacion retenida 195,70 RPM. Ambas sin nuevos rechazos, perdidas de cola o periodos PID omitidos. Se revisan figuras y se guardan evaluaciones por captura. No se cambian ganancias, firmware ni originales.


## 28 de noviembre de 2026 — Descarga gradual de integral bajo referencia

El usuario aprueba probar la correccion discutida. En pid.cpp se sustituye el borrado de integral al tener error negativo por limitar la integral candidata, que disminuye segun Ki por error por dt. Se permite esa descarga aunque la peticion total quede negativa. La salida al freno permanece en cero bajo referencia. La integral no baja de cero ni supera uno. No se agregan parametros nuevos ni se cambian Kp 0,005, Ki 0,004 y Kd cero. Cancelacion, reinicio y errores de medicion conservan el reinicio completo del controlador.

La prueba PID verifica que una integral de 0,02 baja a 0,018 con una desviacion negativa pequena y salida cero. Comprueba conservacion con error cero, recuperacion al volver sobre referencia, descarga hasta cero con error negativo grande y borrado al reiniciar o invalidar la medicion.

Se compara antes y despues en dieciocho escenarios locales de pulsos usando el mismo modelo y ganancias. Cinco mejoran el MAE, uno empeora aproximadamente 0,117 RPM y doce no cambian. Promedios 42,480075 y 42,406876 RPM. Todos cubren la banda de referencia de 1050 a 550 RPM. El salto maximo de orden sigue siendo doce grados en el conjunto, por lo que no se afirma que el cambio elimine movimientos bruscos. El estudio arranca a 1100 RPM con integral cero, sin reconstruir la historia de las corridas reales ni la parada. Resultados guardados en integral_gradual_ki004 con antes, despues y comparacion JSON. El efecto fisico queda pendiente de dos nuevas corridas de seis segundos. No se carga firmware ni se hacen commits o pushes.

Verificacion completada. Todas las secuencias host pasan, incluidas descarga gradual, antiacumulacion, liberacion, configuracion actual y fallos. PlatformIO compila esp32dev con RAM 26068 bytes y flash 300665 bytes. git diff --check pasa. Firmware listo para Upload, pendiente de prueba fisica.


## 28 de noviembre de 2026 — Alternancia de marcas antes del PID

Se revisa 20261128_022756_582980 tras la descarga gradual de integral. Eventos confirman Kp 0,005, Ki 0,004 y Kd cero. La captura no registra una version de algoritmo, por lo que la carga de la nueva logica depende de lo informado por el usuario. MAE en banda comun 31,309130 RPM y final FALLO_MEDICION. La ultima estimacion valida de 286,49 RPM se retiene hasta 4,959 segundos, se invalida a 5,059 y se libera el freno. El fallo se registra hacia 6,55 segundos. El tramo final sigue sin confirmar parada.

Se examina especificamente la oscilacion previa al PID, cuando el motor permanece encendido y el unico SERVO_CMD anterior es 45 grados. Se seleccionan 98 estimaciones distintas por contador, recientes y entre 1000 y 1390 RPM, desde 15,375 a 25,275 segundos originales. Al ajustar una tendencia cubica temporal mas la paridad de pulsos, aparece contraste impar menos par de 29,9606 RPM. RMS residual sin paridad 14,5167 RPM y con paridad 1,2621. Se aproxima el instante al centro del intervalo medido usando antiguedad y periodo. El patron es consistente con sectores desiguales de las dos marcas y no se puede atribuir al PID porque este no actuaba. No demuestra que toda irregularidad durante el frenado sea geometrica.

Se explica como alternativa medir sobre una vuelta completa usando dos intervalos consecutivos, con actualizacion por marca y mayor intervalo de promedio. Se requiere considerar la demora y los controles de calidad antes de implementarlo. No se cambia aun el estimador, las ganancias ni el firmware. Se conservan evaluacion y diagnostico de alternancia junto a los resultados de la captura.


## 28 de noviembre de 2026 — Medicion sobre una vuelta completa

El usuario aprueba medir una vuelta completa para reducir la alternancia ligada a marcas aproximadamente opuestas. En medicion.cpp se agrega una ventana circular de los ultimos marcasPorVuelta intervalos aceptados. RPM validada es 60000000 dividido entre la suma de esos intervalos. La ventana se actualiza por marca completa y necesita marcasPorVuelta mas una detecciones al arrancar. Con una marca se conserva el comportamiento anterior y con seis se suman seis intervalos. El calculo queda fuera de la ISR.

Se conserva el detector de marcas completas, los conteos, el rechazo de pulsos cortos y la comprobacion de saltos sobre los intervalos individuales. La ventana se vacia al reanclar, ante perdida de cola y al rechazar un salto sospechoso, para no unir tramos discontinuos. La antiguedad sigue referida a la ultima marca validada y su limite usa el ultimo sector aceptado, sin ampliarlo artificialmente por sumar una vuelta. El reinicio borra toda la ventana.

La RPM cruda conserva la estimacion por sector para diagnostico. periodo_us del diagnostico nuevo representa la duracion completa usada por la RPM validada. Se agregan MARCAS_POR_VUELTA, MEDICION_INTERVALOS y MEDICION_VUELTA_COMPLETA antes del inicio de cada ensayo fijo o PID. leer_intervalos_frenado.m distingue mediante el metadato las capturas antiguas por sector y las nuevas por vuelta completa. No se modifican las capturas existentes ni se agregan columnas seriales incompatibles.

Las pruebas incluyen arranque sin publicar RPM parcial, actualizacion de vuelta con sectores de 16 y 24 ms que deben dar 1500 RPM en ambas marcas, diferencia conservada en RPM cruda, recuperacion tras silencio y desbordamiento y configuraciones de una, dos y seis marcas. Pasan todas las secuencias host. PlatformIO compila esp32dev con RAM 26092 bytes y flash 300933 bytes. Las ganancias siguen en Kp 0,005, Ki 0,004 y Kd cero, incluida la descarga gradual de integral. El firmware queda sin cargar y su resultado fisico pendiente.

La comprobacion MATLAB final pasa con una captura antigua real de dos marcas y una copia sintetica temporal con periodo de vuelta y su metadato. Se verifican ambos caminos de lectura y la formula de RPM sin modificar el origen real. git diff --check pasa. No se hacen commits ni pushes.


## 28 de noviembre de 2026 — Primer PID registrado con vuelta completa

Se evalua 20261128_023755_797038, con eventos MEDICION_INTERVALOS 2 y MEDICION_VUELTA_COMPLETA 1 que confirman el nuevo estimador. Kp 0,005, Ki 0,004 y Kd cero. La figura de orden angular muestra menor alternancia rapida que las anteriores, aunque siguen cambios bruscos a liberado al cruzar bajo referencia. No se atribuye toda diferencia al estimador a partir de una sola corrida.

A 4,243 segundos de ensayo se registra RPM validada 337,84 contra referencia 380,58, diferencia -42,74 RPM. La accion aplicada es cero y la integral 0,5796, conservada y en descenso. Desde 4,043 hasta 4,543 segundos las filas validas quedan bajo referencia, con salida cero. Los campos de PID y medicion no son una misma actualizacion instantanea. La medida promedia una vuelta y no es velocidad instantanea independiente. El comportamiento es compatible con frenada previa excesiva y demoras de medicion y contacto, pero esta captura no permite separar sus contribuciones.

El MAE en banda comun 1050 a 550 RPM es 27,929130 con 23 registros y error minimo -6,17 RPM. El mayor sobrepaso medido esta fuera de esa banda. Las lecturas validas de referencia terminan a 5,143 segundos, por lo que no se confunde un buen promedio parcial con validacion del cierre completo. Final FALLO_MEDICION alrededor de 6,7 segundos. Se conserva el registro y la figura, sin cambiar ganancias o firmware.


## 28 de noviembre de 2026 — Accion inicial para la recta de seis segundos

El usuario aprueba probar una accion inicial para reducir el retraso de frenado al entrar cerca de 1300 RPM. Se implementa una precarga de integral de 0,55 de accion normalizada, equivalente a unos 34 grados con el rango de 45 a 25. Es una accion inicial aproximada, no una compensacion anticipada continua obtenida de un modelo completo. Se conservan Kp 0,005, Ki 0,004, Kd cero, estimador por vuelta completa y descarga gradual de integral. No se frena antes del inicio del ensayo.

La eleccion usa como orientacion la recta de aproximadamente 1300 RPM a cero en seis segundos, pendiente 216,7 RPM por segundo, y la desaceleracion libre estimada cerca de 75,8 RPM por segundo. El aporte necesario seria cercano a 141 RPM por segundo. El ajuste local a 34 grados estima 157,2 y a 35 grados 53,0, por lo que 34 es un primer candidato entero. Es extrapolacion al arranque de un modelo ajustado principalmente en 500 a 1100 RPM y queda pendiente de validacion fisica. No se presenta como torque conocido ni ajuste universal para otras velocidades o duraciones.

La precarga solo se aplica al iniciar un PID de seis segundos, con actuacion habilitada y Ki positivo. Otras duraciones y los ensayos fijos conservan su comportamiento. Se agrega PID_PRECARGA_X1000000 con 550000 cuando se aplica y cero si se omite. La salida inicial mueve el servo sin esperar a que se acumule error y despues se actualiza mediante el controlador. La precarga no se restaura automaticamente tras una medicion invalida. Cancelacion y reinicio la borran.

Se agregan comprobaciones de precarga antes del primer calculo, rechazo de valores invalidos o cambios en marcha, liberacion bajo referencia y borrado al reiniciar. La bateria host completa pasa. La prueba de configuracion actual comprueba inicio a 34 grados, cancelacion, perdida y que el ensayo de veinte segundos omita la precarga. Los cuatro casos especificos pasan por separado. Build esp32dev correcto, RAM 26092 y flash 301161 bytes. La respuesta fisica del primer segundo sigue pendiente. No se carga firmware ni se hacen commits o pushes.

El evaluador PID conserva como configuracion opcional la precarga y los metadatos de ventana de medida para distinguir nuevas corridas de las antiguas sin cambiar las formulas de error.


## 28 de noviembre de 2026 — Dos ensayos con precarga inicial

Se revisan 20261128_025010_018741 y 20261128_025102_166785. Ambas confirman Kp 0,005, Ki 0,004, Kd cero, medicion de vuelta completa con dos intervalos, referencia de seis segundos y PID_PRECARGA_X1000000 550000. Se revisan las dos figuras y se conservan resultados por captura.

En el primer segundo hay diez registros recientes por corrida. MAE segun error_rpm de 8,419 y 9,772 RPM, frente a 59,582 de la corrida previa sin precarga y con estimador de vuelta completa 20261128_023755_797038. Maximo absoluto inicial 19,87 y 20,84 RPM, frente a 92,79 previo. Son resultados medidos de estas corridas, no exactitud fisica independiente ni validacion universal de la precarga.

En banda comun de referencia 1050 a 550 RPM, con 23 registros cada una, MAE 14,257826 y 12,845217 RPM, frente a 27,929130 de la corrida previa sin precarga. El seguimiento medido mejora visiblemente desde el arranque. Aun hay cruces de referencia y liberaciones completas periodicas, visibles en ordenes al servo, por lo que no se declara control perfecto ni fin del ajuste. Se registran 95 y 92 ordenes hasta el final. No hay incrementos de rechazos o perdidas de cola ni periodos PID omitidos.

Ambas terminan FALLO_MEDICION aproximadamente a 7,340 y 6,888 segundos. Ultimas estimaciones retenidas 146,08 y 225,02 RPM, con validez hasta 5,743 y 5,289 segundos respectivamente. La grafica de cero estimado no confirma el instante de parada. Se conserva el pendiente de baja velocidad. No se cambian ganancias ni firmware tras esta revision.


## 28 de noviembre de 2026 — Investigacion del cierre del PID

El usuario pide investigar si el cierre requiere mas tiempo o refleja un problema de marcas o firmware. Se revisan de nuevo las dos corridas con precarga 20261128_025010_018741 y 20261128_025102_166785 y la logica de ensayos.cpp. La finalizacion exige que termine la referencia y que RPM valida sea menor o igual a 100 durante 300 ms. Independientemente, una medicion invalida persistente por 1500 ms produce FALLO_MEDICION. El PID libera al invalidarse la medida. Por tanto el fallo de medicion puede ocurrir antes del limite extra de dos segundos para confirmar el final.

En la primera corrida, el extremo final de la ultima medida se estima cerca de 5,195 segundos usando tiempo de ensayo menos antiguedad. La ventana completa dura 0,410744 s y estima 146,08 RPM. La ultima fila reciente aparece a 5,743 s; a 5,843 ya indica ANTIGUA. El contador permanece en 893 hasta el final del archivo, que continua varios segundos despues del fallo. En la segunda el extremo final se estima cerca de 4,987 s, ventana 0,266641 s y 225,02 RPM. La fila de 5,389 indica ANTIGUA y el contador permanece en 1826 hasta terminar la captura, tambien despues del fallo. No hay evidencia de que otro pulso aceptado solo estuviera llegando tarde dentro de esas ventanas posteriores.

El detector cuenta una marca completa al salir del nivel de marca y conserva como instante la entrada. Si el disco se detiene dentro de ese nivel no se completa la deteccion. Aun con la ventana de vuelta completa, una vez llena cada marca adicional actualiza la medida, no hace falta esperar una nueva vuelta entera para cada salida. El periodo medido es un promedio pasado, no la velocidad del disco cuando deja de haber señal.

Los datos no distinguen parada fisica entre marcas, marca incompleta y perdida de deteccion o fallo electrico sostenido. Se pregunta al usuario si el disco estaba fisicamente detenido al aparecer cero o fallo. Un mayor timeout puede servir para giro lento continuo, pero no genera pulsos tras una parada. Antes de modificar el cierre se requiere distinguir falta de medicion de fallo de sensor y, si se introduce un final por parada estimada, identificarlo explicitamente sin afirmar cero medido ni desactivar fallos durante giro alto. Seis marcas reducen el angulo entre detecciones, pero no garantizan una medicion de cero. No se cambia firmware ni umbrales durante esta investigacion.


## 28 de noviembre de 2026 — Referencia exponencial en ESP32

El usuario autoriza probar exponencial. Se conserva la referencia lineal y se agrega Exponencial normalizada con forma dos, n_ref=n0 por (exp(-2t/T) menos exp(-2)) dividido entre (1 menos exp(-2)). Los extremos son n0 y cero y se mantiene cero al finalizar. El factor dos sustituye al tres anterior del simulador para que ambos generadores coincidan y para evitar una cola mas lenta que el rozamiento estimado en esta primera prueba de seis segundos. El coseno sigue solo en simulacion.

Se agrega seleccion mediante curva_lineal y curva_exponencial, bloqueada durante cualquier etapa activa. Ensayos conserva el tipo seleccionado al preparar y lo aplica al iniciar. Registra REFERENCIA_TIPO 0 o 1, REFERENCIA_FORMA_X1000 0 o 2000 y el evento de duracion especifico. La app nativa y el panel permiten aplicar ambas figuras a ESP32. El backend no afirma figura fisica inicial al conectar y solo cambia la figura activa con la confirmacion del firmware. El selector muestra el coseno deshabilitado con ESP32.

La recta de seis segundos conserva la precarga 0,55. La exponencial de seis segundos usa pidAccionInicialExponencial 0,70, aproximadamente 31 grados, como candidato inicial separado. Kp 0,005, Ki 0,004 y Kd cero se mantienen. Otras duraciones omiten estas precargas. No se implementa aun una accion anticipada general continua ni se cambia el cierre por ausencia de señal.

Comprobacion orientativa cerca de 1300 RPM y T de seis segundos. La pendiente inicial es 501,16 RPM por segundo y la final 67,82. Al restar el modelo libre, el aporte adicional necesario permanece positivo, aproximadamente 425,40 a 28,78 RPM por segundo en 1201 puntos. Esto usa extrapolaciones del modelo fuera de su banda validada y no garantiza la dinamica fisica o el seguimiento de todo el ensayo. El angulo inicial se aproxima desde la tabla de freno y queda pendiente de ensayo real.

Pasaron las pruebas host completas, incluidas monotonia, extremos, escala temporal, reloj y rechazo de tipo invalido de la exponencial. La configuracion actual comprueba inicio a 31 grados, precarga 700000, tipo 1, forma 2000 y rechazo de cambio de curva en marcha. Pasaron 31 pruebas de la app, incluidas transmision serial de curva, confirmacion, seleccion de escritorio y bloqueo durante ensayo. Comparacion independiente entre C++ y Python en 1201 puntos, diferencia maxima 0,000132 RPM. PlatformIO compila esp32dev con RAM 26108 y flash 302453 bytes. git diff --check pasa. No se carga firmware ni se hacen commits o pushes.


## 28 de noviembre de 2026 — Tres primeras corridas exponenciales

Se revisan 20261128_031836_882376, 20261128_031934_975449 y 20261128_032138_486026. La conexion previa 031748_459244 corresponde a recta y no se mezcla con este grupo. Las tres exponenciales confirman tipo 1, forma 2000, precarga 700000, Kp 0,005, Ki 0,004 y Kd cero. Se revisan las tres figuras y se guardan evaluaciones por captura.

No aparecen periodos PID omitidos. Maximos de intervalo registrados 20019, 20019 y 20024 microsegundos frente al nominal 20000. Maximos de tiempo de calculo 71, 9 y 27 microsegundos. Esta instrumentacion no mide toda la carga del programa ni el retardo fisico, pero no aporta evidencia de que calcular la exponencial agote el tiempo disponible. No hay incrementos de pulsos cortos o saltos rechazados ni perdidas de cola.

Los quiebres coinciden con ciclos de orden angular fuerte, cruce de medida bajo referencia, liberacion a 45 y vuelta a frenado. En banda comun de referencia de 1050 a 550 RPM, MAE de 26,0675, 23,560667 y 25,076250 RPM, con 16, 15 y 16 registros. Fuera de esa banda hay errores negativos de hasta -77,40, -74,50 y -75,83 RPM. Las figuras y los terminos I muestran accion acumulada cercana a 0,7 durante varios cruces. El mecanismo es compatible con una precarga fija que no sigue la desaceleracion decreciente de la exponencial, junto a la liberacion dura, retardos y promedio de medicion. Los registros no separan las contribuciones mecanicas o del sensor.

Todas terminan FALLO_MEDICION. Tiempos aproximados de final 5,192, 7,116 y 5,212 segundos. Ultimas filas validas a 3,653, 5,578 y 3,666 segundos, con estimaciones retenidas 277,38, 80,16 y 273,43 RPM. La segunda cronologica es la que mantiene mediciones mas cerca del final, pero ni ella confirma el cierre. No se confunde el cero estimado de la app con cero medido. Las ventanas parciales no se comparan como MAE de todo el ensayo de seis segundos.

La referencia registrada coincide con la formula de forma dos dentro de 0,006 RPM salvo la primera fila de la primera corrida, cuya diferencia es 5,411 RPM y es compatible con campos tomados en distintos instantes alrededor del arranque. No se atribuyen a ese unico desajuste los ciclos de todo el frenado.

Proximo punto propuesto es evaluar una accion anticipada continua que reduzca la accion base segun la pendiente de la referencia, dejando al PID corregir. Antes de implementarla se debe representar el estimador por vuelta completa y los limites del modelo. No se cambian ganancias, algoritmo, cierre ni capturas originales en esta revision.
