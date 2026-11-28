# Herramientas del banco de frenado

La aplicación de escritorio se abre con un solo archivo Python, sin navegador ni puerto web.

```fish
python3 '/home/saddygr/Documentos/GitHub/sguzman_asm_2026_s2/proyecto2/tarea2/herramientas/banco_frenado.py'
```

El lanzador prepara y selecciona el entorno local automáticamente. Conserva la simulación, los ciclos, la conexión a la ESP32 y los formatos de captura. Consulta [la guía de escritorio](ESCRITORIO.md) para los controles, dependencias y cierre de pruebas activas. El panel web y la terminal anteriores siguen disponibles.

## Capturador serial anterior

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

## Dos modos de interfaz

`python3 panel_frenado.py --modo panel` abre la interfaz gráfica. `python3 panel_frenado.py --modo terminal --simular` abre una pantalla de terminal con métricas, minigráficas, eventos y comandos. Para la placa, usar `--modo terminal --puerto-serial /dev/ttyUSB0` con el puerto real. Los dos modos comparten protocolo y captura. La guía completa está en [TERMINAL.md](TERMINAL.md).


## Estudio local del controlador con modelo medido

El archivo simular_modelo_medido.py ejecuta un estudio separado de la simulacion ficticia del panel. No cambia la aplicacion de escritorio ni abre el puerto de la ESP32. Se puede ejecutar desde cualquier carpeta con

```fish
/usr/bin/python3 '/home/saddygr/Documentos/GitHub/sguzman_asm_2026_s2/proyecto2/tarea2/herramientas/simular_modelo_medido.py'
```

Necesita Python y g++ para compilar el PID existente como biblioteca temporal. Las tablas se generan con la biblioteca estandar. Matplotlib es opcional para el PNG y no se instala automaticamente. La opcion --salida permite elegir otra carpeta para los resultados.

Usa los parametros a y b del modelo libre y los aportes de 28, 30, 33, 34 y 35 grados de las tablas MATLAB. El codigo PID y la conversion angular se compilan directamente desde pid.cpp y freno.cpp mediante el puente nativo existente. El periodo del puente es 20 ms y su filtro derivativo es 0,1 segundos. Kd permanece en cero. Se comprueba que la conversion sigue correspondiendo a 45 grados para accion cero y 15 para accion uno. La planta ficticia de la clase utilizada como puente no se propaga.

La planta del estudio usa dn/dt = -a - b*n - c, con n en RPM y tiempo en segundos. Comienza con 1100 RPM y contacto liberado, reiniciando el controlador en ese punto. Solo representa el tramo correspondiente a referencias lineales de 1300 a cero en 6 o 20 segundos. No simula el arranque, el intervalo anterior a 1100 ni la parada completa.

Se supone ausencia de contacto desde 36 grados y se interpolan linealmente los aportes entre los nodos medidos. La frontera de contacto y esas interpolaciones no estan validadas. La captura de 38 no se utiliza como nodo del control. El aporte de contacto sigue una dinamica de primer orden con constante de tiempo supuesta de 0,12 segundos. No es un retardo puro ni una constante medida del SG90. La solucion acoplada de velocidad y contacto se propaga de forma analitica bajo cada orden constante. El algoritmo termina si la velocidad sale de 500 a 1100 RPM o si se pide un angulo menor que 28. No recorta una orden demasiado fuerte para aparentar seguimiento. Un final por salida de banda representa limite del analisis, no parada fisica.

La medicion es ideal y nueva cada 20 ms. No reproduce los pulsos del KY-033, su antiguedad, el tiempo de recorrido de la marca ni los estados y fallos del firmware completo. Por eso todavia no se deben transferir las ganancias a la maqueta. Una sola marca por vuelta recibe actualizaciones mas espaciadas que esta medicion ideal.

El barrido compara Kp de 0,002, 0,005, 0,01, 0,02 y 0,04 con Ki de cero, 0,001, 0,003 y 0,01. Conserva el mejor P y el mejor PI de ese conjunto por error medio nominal, usando solo candidatos que cubren la banda comun de referencia. No encuentra un optimo global ni penaliza el movimiento del servo. No utiliza una herramienta de sintonia automatica, Laplace o respuesta en frecuencia. Es una comparacion temporal inicial con un modelo no lineal por zonas y orden angular entera.

En la recta de 6 segundos resultaron Kp de 0,04 para P y Kp de 0,04 con Ki de 0,01 para PI. Son candidatos de simulacion, no recomendaciones de carga. En la banda comun de referencia de 1050 a 550 RPM, el MAE nominal es aproximadamente 204,53 RPM libre, 139,23 a 35 fijo, 10,75 a 34 fijo, 9,01 con P y 6,34 con PI. Estas cifras usan el mismo intervalo de comparacion y todos esos casos lo cubren. El PI cambia de grado 115 veces en el tramo de unos 2,77 segundos, por lo que su menor error no basta para recomendarlo.

Se prueban ademas constantes supuestas de contacto de cero, 0,12 y 0,25 segundos y factores del aporte de freno de 0,8, 1 y 1,2. No son intervalos de confianza ni valores medidos. Con constante de 0,25 segundos el PI seleccionado pide angulos fuera de la zona modelada y el estudio interrumpe esos casos. No demuestra inestabilidad fisica, pero impide declararlo robusto con este analisis.

La recta de 20 segundos necesita desacelerar 65 RPM/s. El modelo libre pierde unos 70,11 RPM/s a 1100 RPM. El aporte requerido seria negativo al principio del tramo, algo que el freno no puede producir con el motor apagado. El umbral del modelo es aproximadamente 919 RPM. Que ambas curvas se vean cercanas no significa seguimiento exacto alcanzable. Los frenados fijos de 20 segundos salen antes de la banda medida y sus errores parciales no se comparan como si cubrieran el intervalo completo.

Los resultados quedan en tarea2/matlab/resultados_reales/simulacion_modelo_medido. Incluyen los CSV por condicion, barrido.csv, metricas.csv, sensibilidad.csv, alcanzabilidad_recta.csv, comparacion.png y modelo_y_limites.json. El JSON guarda los parametros y las huellas SHA256 de sus tablas fuente. Las columnas de estado y cubre_1050_a_550 deben revisarse antes de comparar errores. La figura termina cada curva al alcanzar los limites del analisis.

El siguiente paso es representar el ritmo de actualizacion de una marca por vuelta y evaluar cambios menos bruscos de orden antes de proponer ganancias para una prueba fisica. La aplicacion conserva por ahora su simulacion ficticia y las ganancias de la ESP32 siguen intactas.


## Simulacion por pulsos y primer ajuste proporcional

El estudio nuevo se ejecuta con

```fish
/usr/bin/python3 '/home/saddygr/Documentos/GitHub/sguzman_asm_2026_s2/proyecto2/tarea2/herramientas/simular_pid_dos_marcas.py'
```

Reutiliza pid.cpp y freno.cpp, con rango propuesto de 45 a 25 grados en una copia temporal. No abre puertos ni carga firmware. La funcion adicional calcularMuestra del puente nativo conserva el instante del ultimo pulso, en lugar de tratar cada calculo como medida nueva. Las llamadas antiguas del panel siguen compatibles y los tiempos del puente proceden ahora de configuracion.h.

La planta incorpora los aportes locales nuevos de 26, 27 y 28 y la estimacion parcial a 25. Conserva el modelo libre anterior y los aportes de 30, 33, 34 y 35. Se interpola entre nodos y se supone ausencia de contacto desde 36, sin usar 38 como nodo. Las diferencias no monotonas entre 27 y 28 se conservan como incertidumbre de los datos, sin forzar una ley angular exacta.

El sensor ideal por pulsos integra el avance angular de la velocidad del modelo, localiza el paso de cada marca y calcula RPM como treinta dividido entre el ultimo periodo en segundos. Conserva la muestra entre pulsos. No representa el ancho de la marca, el detector completo, ruido electrico o fallos de hardware. El tramo comienza a 1100 RPM con una lectura inicial compatible asumida y termina cuando la referencia llega a 500 o la planta sale de la banda. No se predice la parada completa.

Se comparan seis valores de Kp con Ki y Kd en cero. Por cada ganancia se ejecutan dieciocho casos, combinando constante de contacto supuesta de 0,12 o 0,25 segundos, sectores de media vuelta con desigualdad de cero o mas o menos 0,006 vueltas y factor de aporte de freno de 0,8, 1 o 1,2. No son limites estadisticos ni geometria medida. Los resultados quedan en resultados_reales/pid_dos_marcas con CSV, PNG y JSON de fuentes y limitaciones.

Para el primer ensayo fisico se elige Kp de 0,005. En esos casos el peor MAE verdadero simulado es de 103,30 RPM, el error positivo maximo de 126,94 RPM y el salto angular maximo de tres grados entre calculos. El caso nominal supuesto cambia de grado 106 veces en el tramo, asi que no se afirma que el servo deje de hacer correcciones frecuentes. El criterio es moderar su amplitud antes de aumentar la ganancia. Los valores mayores reducen error pero llegan a saltos de seis, diez o catorce grados en el estudio. No se declara una sintonia final ni estabilidad fisica garantizada.

El firmware queda preparado con actuacion habilitada, dos marcas, rango automatico 25 a 45 y Kp de 0,005, Ki y Kd cero. La interfaz de escritorio, el formulario web y la validacion de ordenes fijas usan ese rango. La calibracion manual conserva 0 a 90 grados. Los campos K de la app siguen afectando solo a su simulacion. La guia PRUEBAS_FISICAS.md contiene el protocolo de seis segundos con Iniciar ciclo PID y la interpretacion de un final sin confirmacion de baja velocidad.

El estudio inicial simular_modelo_medido.py conserva su rango historico de 45 a 15 en una copia temporal para reproducir las cifras anteriores. La aplicacion y el firmware actuales no toman ese rango historico. No se altera la configuracion real al ejecutar ninguno de los dos estudios.


## Evaluar una captura fisica de PID

Se agrega evaluar_ensayo_pid.py para analizar una captura con una sola corrida PID y configuracion registrada en sus eventos. No modifica firmware ni ganancias. El comando para la primera prueba es

```fish
/usr/bin/python3 '/home/saddygr/Documentos/GitHub/sguzman_asm_2026_s2/proyecto2/tarea2/herramientas/evaluar_ensayo_pid.py' '/home/saddygr/Documentos/GitHub/sguzman_asm_2026_s2/proyecto2/tarea2/capturas/escritorio/reales/20261128_014245_541966'
```

Para otra prueba se sustituye solo la carpeta de captura. La opcion --salida permite elegir otro directorio. El analisis exporta metricas.csv, seguimiento.csv, ordenes_servo.csv, diagnostico.json y seguimiento.png si matplotlib esta disponible. Los CSV se generan con Python estandar. Se conservan NaN al faltar señal y no se reemplazan por ceros medidos.

La primera corrida fisica confirma Kp de 0,005, Ki y Kd cero, dos marcas y rango de 25 a 45. El motor se ordeno apagar alrededor de 1400 RPM y el ensayo comenzo alrededor de 1296,68 RPM, con referencia lineal de seis segundos. En las 59 lecturas recientes validas durante la referencia, entre 0,044 y 5,833 segundos de los campos de ensayo registrados, el MAE medido es 107,249153 RPM y el RMSE 110,338691. El error medido queda positivo, entre 7,13 y 151,10 RPM. En la banda comun de referencia de 1050 a 550 hay 23 lecturas y MAE de 108,212609 RPM. No se presentan esos errores como velocidad verdadera independiente del sensor ni como prueba de repetibilidad.

El servo recibio 204 eventos de orden durante el ensayo, incluyendo la orden inicial y la liberacion final. Los extremos ordenados fueron 28 y 45, dentro del rango. El periodo PID maximo registrado fue 20016 microsegundos, sin periodos omitidos. El tiempo maximo de calculo registrado fue 82 microsegundos y no incluye toda la latencia de lazo o de impresion. No aumentaron rechazos y no se perdieron elementos de la cola. Los registros muestran un error sostenido compatible con la accion proporcional elegida, sin demostrar que toda su magnitud se deba a una causa unica.

El ensayo termino con FALLO_MEDICION alrededor de 7,4 segundos. La ultima estimacion valida fue 187,19 RPM y se repitio en varias filas mientras no llegaban nuevas marcas. En la ultima fila valida su antiguedad era de unos 390 milisegundos. Al volverse invalida se ordeno liberar el freno y la ausencia persistente termino el ensayo con fallo. No se afirma con esos datos que el disco siguiera girando ni que estuviera detenido exactamente en un instante determinado.

La grafica usa tiempo_ensayo_ms para referencia y mediciones. Los eventos se colocan mediante una base temporal estimada a partir del diagnostico y conservan su tiempo original en otra columna. Esa alineacion tiene una diferencia de lectura e impresion de varios milisegundos y no debe usarse como precision de temporizacion fisica.

El seguimiento y el final se evaluan por separado. La primera corrida muestra control activo siguiendo la bajada con sesgo positivo. Todavia no demuestra seguimiento completo hasta cero ni una sintonia final. Un proximo ajuste puede estudiar una integral pequena para reducir el error sostenido, manteniendo Kd en cero. En esta evaluacion no se cambian las ganancias ni el criterio de finalizacion.


### Comparacion de ganancias integrales con pulsos

`simular_pid_dos_marcas.py` admite `--kp` y `--ki` con uno o varios valores. Por defecto conserva el estudio proporcional. Para comparar los ajustes integrales usar `--kp 0.005 --ki 0 0.0005 0.001` y elegir una carpeta nueva mediante `--salida` para conservar los resultados previos. Los archivos PI incluyen Kp y Ki en el nombre y el resumen distingue ambos. El estudio conserva el controlador C++ real, pero arranca el tramo a 1100 RPM con integral cero. No reproduce toda la historia del ensayo de seis segundos ni su cierre sin pulsos.

El firmware actual queda preparado con Kp 0,005, Ki 0,004 y Kd cero para la siguiente comparacion fisica. La app conserva las ganancias simuladas independientes y no modifica las de la placa.


### Medicion validada por vuelta completa

El firmware nuevo calcula la RPM validada con el tiempo de marcasPorVuelta intervalos consecutivos y actualiza por marca. RPM cruda sigue siendo por sector. El campo periodo_us de las nuevas capturas contiene el tiempo total de esa vuelta y antiguedad_us se refiere a su extremo final. Los eventos MEDICION_INTERVALOS y MEDICION_VUELTA_COMPLETA identifican la nueva interpretacion. Las capturas antiguas conservan su significado y sus archivos. No aplicarles la formula nueva sin comprobar los metadatos.

El estudio historico simular_pid_dos_marcas.py conserva su sensor por sector y no reproduce aun el nuevo estimador de vuelta completa. Sus resultados anteriores no validan este cambio.


### Arranque PID con precarga exploratoria

El firmware configura pidAccionInicial en 0,55, equivalente a unos 34 grados. Solo se precarga la integral al iniciar PID con la duracion pidDuracionPrecargaMs de 6000, actuacion habilitada y Ki positivo. No es una nueva ganancia ni una compensacion continua del modelo. Cambiar la duracion omite esta precarga y registra cero. Los datos nuevos incluyen PID_PRECARGA_X1000000 para distinguir la comparacion. El evaluador conserva ese metadato y los de ventana completa cuando existen.


### Exponencial fisica de seis segundos

El firmware acepta curva_lineal y curva_exponencial entre ensayos. La app de escritorio y el panel web permiten aplicarlas a ESP32 y actualizan la figura activa al recibir REFERENCIA_TIPO del dispositivo. La figura queda sin confirmar al conectar hasta recibir un evento, evitando asumir la configuracion de la placa. La seleccion se bloquea durante preparacion, descenso y ensayo. El coseno sigue solo en simulacion.

La exponencial normalizada usa forma dos tanto en Python como en C++, comienza en la velocidad inicial y termina en cero al completar la duracion. Antes el simulador usaba forma tres. Los registros incluyen REFERENCIA_TIPO, REFERENCIA_FORMA_X1000 y REFERENCIA_EXPONENCIAL_MS. El evaluador conserva el ultimo tipo confirmado previo al inicio y la forma para identificar cada corrida. Las capturas antiguas sin tipo se interpretan como lineales.

Para la prueba fisica de seis segundos se conserva Kp 0,005, Ki 0,004 y Kd cero. pidAccionInicialExponencial es 0,70, aproximadamente 31 grados, como candidato de arranque. La recta conserva su precarga 0,55. Ambas se omiten en otras duraciones. No es una accion anticipada general para cualquier curva o velocidad. La guia de pruebas contiene la secuencia de Upload, reinicio de app, Aplicar figura e Iniciar ciclo PID.
