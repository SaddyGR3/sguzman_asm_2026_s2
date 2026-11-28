# MATLAB para la Tarea 2: capturas reales

## Alinear las curvas del montaje reorganizado

Ejecutar esta funcion para comparar el giro libre y las dos frenadas seleccionadas, conservando sus velocidades originales.

```matlab
resultado = alinear_ensayos_frenado;
```

Las capturas predeterminadas son las siguientes.

| Captura | Condicion |
|---|---|
| 20261127_200435_402416 | Giro libre a 45 grados |
| 20261127_200152_802180 | Freno fijo a 30 grados, corrida 1 |
| 20261127_200642_850954 | Freno fijo a 30 grados, corrida 2 |

La alineacion seleccionada no incluye la captura 20261127_200805_778882, que inicialmente solo tenia movimientos manuales. Mas tarde se agrego un giro libre completo a esa misma captura, utilizable en el analisis del modelo desde su evento de inicio. Las capturas anteriores a la reorganizacion tampoco se mezclan con estas.

La alineacion resta el tiempo de ENSAYO_FIJO_INICIO a cada tiempo original. Un registro a 27564 ms en un ensayo iniciado a 27519 ms queda a 0,045 segundos del inicio. Su RPM no cambia. El tiempo alineado se contrasta con tiempo_ensayo_ms con tolerancia de 20 ms. En estas capturas difieren hasta 11 ms porque el firmware lee los campos en momentos distintos durante la impresion serial. Ambos se conservan, sin afirmar que fueron adquiridos simultaneamente. Las primeras muestras pueden aparecer unas centesimas despues de cero por el registro a 10 Hz, sin inventar una muestra en cero.

Conserva NaN donde no hay medicion valida y rechaza capturas con filas temporales ausentes, motor encendido durante el ensayo, angulo incompatible o perdidas de cola. No normaliza velocidades, no interpola, no estima pendientes y no identifica un modelo. La referencia dibujada corresponde a la primera frenada seleccionada y las velocidades iniciales de cada corrida se conservan en el resumen.

Guarda PNG, FIG editable, MAT, resumen CSV y un CSV alineado por captura bajo resultados_reales/alineacion_montaje_reorganizado. Cada CSV conserva el tiempo original, el inicio usado, ambos tiempos relativos, las RPM y su estado. Los archivos fuente se mantienen intactos.

Para analizar otras muestras se puede pasar un arreglo de configuracion. Cada elemento contiene carpeta, nombre y angulo. Por ejemplo, partir de resultado.configuracion, modificar las rutas o agregar otra corrida y ejecutar lo siguiente.

```matlab
configuracion = resultado.configuracion;
% Modificar o agregar elementos antes de ejecutar.
resultado = alinear_ensayos_frenado(configuracion, fullfile(pwd, 'resultados_reales', 'otro_grupo'));
```

El analizador acepta una cantidad variable de ensayos completos. Un cambio de disco o montaje debe quedar como un grupo experimental separado. Varias capturas permiten observar variacion, pero esta grafica sola no demuestra repetibilidad ni precision del sensor.


## Estimar pendientes en una ventana comun

Despues de alinear, ejecutar lo siguiente.

```matlab
pendientes = estimar_pendientes_frenado(resultado);
```

Sin argumentos, la funcion carga el archivo alineacion.mat generado por alinear_ensayos_frenado. Tambien admite una ventana distinta como segundo argumento, por ejemplo [0.5 1.5]. La ventana predeterminada es de 0,5 a 1,5 segundos y exige suficientes datos validos en todas las curvas. No elimina huecos para forzar el ajuste.

Ajusta una recta de velocidad frente a tiempo con polyfit de grado uno. La pendiente describe el cambio aproximado de RPM por segundo en ese tramo. El intercepto solo ubica esa recta y no debe tomarse como una nueva medicion inicial. No deriva los escalones muestra a muestra ni extrapola a la parada.

La grafica muestra los registros originales y sus rectas en paneles con la misma escala vertical. La tabla conserva ventana solicitada, primer y ultimo registro realmente usado, numero de registros, pendiente, aceleracion equivalente en rad/s² y error de la recta en RPM. Los tiempos de los registros no coinciden exactamente entre corridas y no se interpolan. Los registros seriales pueden repetir una estimacion y no son necesariamente independientes.

Para estas capturas las pendientes son aproximadamente -76,053, -544,109 y -530,425 RPM/s. La diferencia respecto del giro libre es de 468,056 y 454,372 RPM/s de perdida adicional. Es una comparacion descriptiva del mismo tramo temporal. Las curvas recorren velocidades distintas y el rozamiento puede depender de la velocidad, por lo que esa resta no aisla un torque constante ni identifica una ganancia del freno.

Guarda CSV, PNG, FIG y MAT en una subcarpeta de la alineacion segun la ventana seleccionada. El analisis se ejecuto y verifico con MATLAB R2026a. No requiere Control System Toolbox.

## Comparar la desaceleracion natural a distintas velocidades

```matlab
libre = analizar_desaceleracion_libre;
```

Usa la captura libre 20261127_200435_402416. La captura continuo despues del final del ensayo a los seis segundos. Antes de usar esos registros posteriores, la funcion comprueba que siguen en FIJO o FINALIZADO, el motor permanece apagado, no hay fallos ni perdidas de cola y las ordenes del servo se mantienen en 45 grados.

Compara ventanas de igual duracion de 0,5 a 2,5 segundos, de 8,5 a 10,5 y de 15,5 a 17,5. Cada ventana contiene veinte registros validos y se ajusta con una recta. Las velocidades medias son aproximadamente 1183, 664 y 289 RPM. Las pendientes son -74,304, -57,646 y -50,236 RPM/s. Los registros pueden repetir una estimacion entre marcas y no representan veinte mediciones independientes.

Se pueden pasar otra carpeta y una matriz de ventanas de dos columnas como argumentos. El analizador exige cobertura y ausencia de huecos en las ventanas seleccionadas. No rellena valores ni modifica la captura. Guarda tabla CSV, PNG, FIG y MAT en resultados_reales/desaceleracion_libre seguido del identificador de captura.

Esta comparacion describe una sola desaceleracion. La variacion de pendiente orienta la eleccion de un modelo, pero no demuestra que el rozamiento dependa solamente de la velocidad ni permite separar mecanismos fisicos. No se ajusta una ecuacion diferencial en esta funcion.

## Primera ecuacion de giro libre y comprobacion reservada

```matlab
modelo = modelar_giro_libre;
```

La funcion ajusta con las capturas 20261127_200435_402416 y 20261127_200805_778882. Reserva 20261127_210612_886523 para comprobar las predicciones. Aunque se inspeccionaron previamente las pendientes de las tres, los parametros se calculan solo con las dos primeras. La ventana comun de 0,5 a 17,5 segundos se fija antes del ajuste, sin optimizarla con la tercera. Las condiciones son motor apagado y servo liberado a 45 grados.

El modelo es dn/dt = -a - b*n. n representa RPM, a se expresa en RPM/s y b en 1/s. Se obtuvo a aproximadamente 39,049 y b aproximadamente 0,028239. No se interpreta a como torque ni b como una constante de friccion mecanica aislada. Incluyen los efectos del montaje bajo estas condiciones. No es la funcion de transferencia entre servo y velocidad.

Se ajustan las predicciones de velocidad de la solucion de la ecuacion diferencial mediante fminsearch, disponible en MATLAB base. Se minimiza la suma de errores cuadrados de las dos corridas de ajuste, sin derivar las mediciones. La primera RPM valida de cada ventana fija la condicion inicial y no se ajusta como parametro. Para la tercera se usa solo esa primera medida y se predice el resto sin correccion con medidas posteriores. Las metricas excluyen el punto inicial impuesto.

Tambien se ajusta una alternativa de desaceleracion constante con las mismas dos corridas. En la tercera, el error RMS fue aproximadamente 2,813 RPM con el modelo mixto y 27,683 RPM con el constante. El error absoluto medio del mixto fue 2,309 RPM y el maximo 7,374 RPM. Esto evalua prediccion frente al sensor, sin certificar exactitud metrologica ni generalizacion a otras condiciones.

Los registros abarcan aproximadamente de 1254 a 246 RPM en las pruebas de ajuste y hasta 255 RPM en la reservada. No se valida el comportamiento de parada, el motor encendido, otros discos, el servo aplicado ni velocidades fuera del rango observado. Los registros seriales pueden repetir estimaciones y no se usan como replicas experimentales independientes ni para intervalos estadisticos de confianza.

Guarda parametros, metricas, predicciones por captura, PNG, FIG y MAT en resultados_reales/modelo_libre seguido del identificador reservado. Se pueden pasar otras carpetas de ajuste, otra de validacion y una ventana. La funcion rechaza repetir una misma captura entre ajuste y validacion. Se ejecuto en MATLAB R2026a y se contrastaron los parametros con un calculo independiente en Python.

## Primera hipotesis para frenado fijo a 30 grados

```matlab
freno = modelar_frenado_30;
```

Carga los parametros ya calculados del giro libre, sin reajustarlos. Ajusta un unico termino c30 con las nuevas frenadas 20261127_211944_350811 y 20261127_212026_949598 y reserva 20261127_212109_143576 para comprobarlo. La ventana fijada es de 0,5 a 2 segundos, con quince registros validos por corrida. Deja fuera el inicio del movimiento del servo y el tramo sin señal. Verifica la orden de 30 grados durante la ventana, motor apagado, ensayo completo y ausencia de perdidas de cola. La liberacion terminal puede preceder al evento de fin por un milisegundo y no forma parte de esa ventana.

La hipotesis es dn/dt = -a - b*n - c30 con n en RPM. Se conservan a aproximadamente 39,048666 RPM/s y b aproximadamente 0,028239020 inversos de segundo. El aporte c30 ajustado es aproximadamente 439,090141 RPM/s. Se calcula minimizando errores cuadrados de la solucion temporal con las dos corridas de ajuste. La primera lectura del tramo fija la condicion inicial y se excluye de las metricas. No se mide torque ni se obtiene una relacion entre angulo y fuerza.

En la tercera frenada el error absoluto medio es 32,353 RPM, el RMSE 44,384 RPM y el maximo 105,763 RPM. En las dos de ajuste los RMSE son 25,103 y 28,130 RPM. El modelo es una primera aproximacion, sin declararlo validado para el frenado completo ni para diseñar el PID fisico. La figura incluye el error con signo para revisar desviaciones sistematicas.

La comparacion actual usa el tiempo del registro, pero el sensor entrega una estimacion entre marcas que puede repetirse y quedar retrasada. Por ejemplo, la lectura final de la ventana reservada es de 436,32 RPM con antiguedad de 273591 microsegundos y periodo de 137515 microsegundos. Por tanto, el error no separa deficiencias de la ecuacion de efectos del proceso de medicion. Se debe revisar esa sincronizacion antes de atribuirlo a un aporte de freno variable o agregar complejidad al modelo. Los parametros y errores son exploratorios bajo esta comparacion temporal.

Guarda parametros, metricas y predicciones CSV, PNG, FIG y MAT en resultados_reales/modelo_freno30 seguido del identificador reservado. Se pueden pasar otro modelo libre, otras carpetas y otra ventana. Rechaza usar la misma captura para ajuste y comprobacion. Se ejecuto en MATLAB R2026a y se contrastaron parametro y metricas con Python. No se modifican firmware, ganancias o capturas.

## Comparar el freno con los intervalos fisicos del sensor

```matlab
intervalos = comparar_frenado_por_intervalos;
```

Conserva las mismas capturas de ajuste y comprobacion del modelo a 30 grados y la ventana de registros de 0,5 a 2 segundos. Conserva los parametros libres. No sustituye el analisis instantaneo anterior ni cambia RPM originales. La cantidad de marcas fisicas es un argumento explicito y por defecto es una. Se valida que RPM, periodo y marcas sean coherentes, con tolerancia por redondeo de dos decimales.

El firmware calcula antiguedad_us respecto del inicio de la ultima marca validada. Por tanto, final del intervalo equivale al tiempo del registro menos la antiguedad. El inicio es ese final menos periodo_us. La velocidad medida es un promedio angular sobre ese intervalo. Los tiempos reconstruidos son aproximados por resolucion de milisegundos del registro y lecturas realizadas en instantes cercanos, sin afirmar precision de microsegundos.

Agrupa las filas repetidas de la misma marca mediante pulsos_aceptados y verifica que periodo y final reconstruido sean coherentes. Cada captura tiene quince registros y trece intervalos unicos en esta ventana. Las metricas usan doce intervalos, excluyendo la primera media que fija la condicion inicial. No elimina RPM distintas para mejorar el ajuste ni convierte datos ausentes en cero. Los registros originales permanecen en sus CSV y los intervalos elegidos se exportan con su tiempo original.

Calcula la integral temporal de la solucion del modelo sobre cada intervalo, dividida entre su duracion. La primera media medida se usa como condicion inicial promedio, sin tratarla como velocidad instantanea. El estado inicial compatible depende de los parametros de la ecuacion y no se ajusta como parametro adicional. Solo c30 se estima con las dos capturas de ajuste. La tercera no cambia parametros ni corrige estados, pero sus tiempos y duraciones observados se usan para calcular que media se habria medido. Es una comprobacion condicionada a esos intervalos, no una prediccion ciega de los proximos tiempos de paso.

Para comparar metodos sin cambiar la ponderacion, tambien recalcula el metodo instantaneo sobre los mismos trece intervalos unicos. Su c30 es aproximadamente 451,027879 RPM/s y el c30 por intervalos es 490,024589 RPM/s. En la tercera, MAE de 29,645 RPM frente a 17,547, RMSE de 38,307 frente a 23,345 y maximo de 82,728 frente a 48,781. No comparar esas cifras directamente con el resultado anterior que contaba quince filas y tenia MAE de 32,353 RPM sin aclarar el cambio de ponderacion.

La correccion mejora la comparacion, pero deja error con tendencia negativa en la reservada. No valida un aporte constante universal del freno, otros angulos, la parada ni otro montaje. El modelo libre permanece fijo con las limitaciones de su ajuste previo. La sincronizacion de su propio ajuste no se recalculo en esta funcion.

La funcion termino correctamente en MATLAB R2026a y se reviso el PNG. Se contrastaron parametros y metricas mediante Python. Una integracion numerica independiente de las trayectorias verifico las medias analiticas con discrepancia menor que 0,000001 RPM. Se comprobo que cada RPM exportada coincide con el CSV original y que cada intervalo termina antes de su registro. Guarda tablas de intervalos, parametros, metricas, PNG, FIG y MAT en resultados_reales/freno30_intervalos seguido del identificador reservado.

## Diagnostico de diferencias entre las tres frenadas

```matlab
revision = revisar_repeticiones_freno;
```

Lee el resultado de comparar_frenado_por_intervalos y conserva su modelo comun de aproximadamente 490,024589 RPM/s. Calcula por separado un c30 descriptivo para cada corrida, sin añadir terminos ni actualizar parametros o metricas de la comprobacion reservada. La tercera se usa aqui en un diagnostico posterior, por lo que su ajuste individual no constituye validacion independiente.

Los aportes individuales aproximados son 494,483, 485,390 y 456,604 RPM/s. Las diferencias respecto del modelo comun son +0,91, -0,95 y -6,82 por ciento. El error absoluto medio individual es 7,258, 6,680 y 5,233 RPM, pero estos errores se calculan sobre datos usados en esos mismos ajustes y son descriptivos. No sustituyen el error reservado del modelo comun de 17,547 RPM.

La tercera corrida es compatible con un aporte menor bajo este modelo, sin identificar su causa fisica. Los errores individuales de las tres conservan una curvatura semejante. Por tanto, una diferencia entre corridas y una simplificacion comun del modelo pueden coexistir. No se concluye que el torque varie necesariamente con la velocidad ni se identifica un mecanismo de desgaste o contacto.

La funcion exporta tabla, detalles por corrida, PNG, FIG y MAT en diagnostico_repeticiones dentro de la carpeta del analisis por intervalos. Se ejecuto en MATLAB R2026a, se verificaron los resultados con Python y se reviso el PNG. No modifica las capturas originales, la ecuacion comun o el firmware. Si este diagnostico se usa despues para elegir otro modelo, conviene comprobar esa nueva eleccion con datos nuevos.

## Caracterizar varios angulos con corridas completas o tramos parciales

```matlab
angulos = caracterizar_angulos_freno;
```

Los grupos predeterminados son los siguientes. Las dos primeras capturas de cada fila ajustan el aporte comun y las restantes lo comprueban sin reajuste.

| Angulo | Capturas en orden cronologico | Resultado del protocolo |
|---|---|---|
| 33 grados | 20261127_220904_313271, 20261127_221025_334470, 20261127_221108_074927 | Tres completas por duracion |
| 30 grados | 20261127_211944_350811, 20261127_212026_949598, 20261127_212109_143576 | Tres completas anteriores, como referencia |
| 28 grados | 20261127_221826_686696, 20261127_221914_060863, 20261127_221959_439179 | Tres completas por duracion |
| 25 grados | 20261127_221348_439279, 20261127_221444_959171, 20261127_221525_825693, 20261127_221607_093612 | Cuatro parciales, terminadas con FALLO_MEDICION |

El programa conserva a y b del modelo libre y estima un c por angulo en dn/dt = -a-b*n-c. Usa una banda permitida comun de 500 a 1100 RPM medidas, descarta los intervalos fisicos que comienzan antes de 0,25 segundos y conserva solo intervalos validos. No interpola ni rellena huecos. No todos los grupos recorren exactamente el mismo rango medido ni durante el mismo tiempo. Los rangos efectivos, tiempos, numero de intervalos y motivo de finalizacion se exportan por corrida.

Reutiliza la media integral del modelo en cada intervalo reconstruido mediante antiguedad y periodo. Cada intervalo registrado se usa una vez, agrupando repeticiones por pulsos_aceptados. La primera media fija la condicion inicial y se excluye de las metricas. El ajuste minimiza la suma de errores cuadrados de los intervalos disponibles de las dos capturas iniciales, sin afirmar que todas las corridas pesan igual o que sean mediciones independientes. El aporte individual de cada captura es un diagnostico posterior y no cambia el aporte comun.

Los aportes comunes aproximados son 197,657 RPM/s a 33 grados, 494,277 a 30, 867,453 a 28 y 1150,265 a 25. Los rangos de aportes individuales son 176,417 a 246,376, 469,235 a 501,530, 851,325 a 870,475 y 1105,225 a 1187,682 RPM/s respectivamente. Son rangos descriptivos, no intervalos de confianza. El valor de 30 grados se recalcula para la banda comun y no sustituye el modelo anterior de aproximadamente 490 RPM/s.

A 33 grados se registran entre veinte y veintiseis intervalos por corrida en la banda; a 30, once o doce; a 28, seis o siete; a 25, entre cuatro y seis. Los ajustes a 28 y especialmente a 25 tienen pocos intervalos, por lo que un error pequeño no demuestra precision o buena generalizacion. El MAE de la tercera corrida es aproximadamente 30,002 RPM a 33 grados, 12,266 a 30 y 5,386 a 28. En los dos tramos reservados a 25 los MAE son aproximadamente 4,280 y 9,864 RPM. El resumen muestra su promedio por intervalo evaluado de 7,072 RPM, no un promedio equiponderado de dos corridas completas.

Las cuatro pruebas a 25 terminaron con FALLO_MEDICION. Sus ultimas lecturas validas fueron aproximadamente 430, 528, 503 y 538 RPM. El criterio provisional de posible parada en FIJO exige una ultima velocidad no superior a 400 RPM y no se activo. El usuario observo un frenado fisico muy rapido a 25 grados, aproximadamente 1,5 segundos o incluso menos de uno. Esa observacion cualitativa no es una medida exacta de parada. No se puede certificar solo con CSV si el disco se detuvo o se perdio la señal. Estos datos parciales no completan repeticiones del protocolo final, no validan la parada ni deben presentarse como cuatro ensayos exitosos. La opcion permitirParciales permite estudiar sus intervalos previos al fallo y los marca expresamente. Con false se rechazan.

La grafica no une los angulos ni propone una interpolacion o ley continua del servo. Los puntos y los rangos solo resumen las condiciones observadas. No se habilita PID ni se cambian limites del actuador. El programa acepta otros grupos con campos angulo y capturas, y opciones para bandaRPM, inicioFisicoMinimoS, marcasPorVuelta, permitirParciales, modeloLibre y salida. La cantidad de marcas corresponde a las usadas al capturar.

Guarda resumen, inventario por corrida, tablas de intervalos, PNG y FIG del mapa y de la comprobacion, y MAT en resultados_reales/caracterizacion_angulos_actual. Los resultados se contrastaron mediante Python y se ejecutaron con MATLAB R2026a. Las condiciones y los fallos originales se conservan.

## Comparacion del montaje actual con servo de 45 a 15 grados

Para las capturas del 27 de noviembre de 2026, ejecutar desde esta carpeta lo siguiente.

```matlab
resultado = comparar_giro_y_freno;
```

La funcion nueva compara giro libre a 45 grados de la captura `20261127_190400_799594` y frenado fijo a 30 grados de `20261127_185956_618751`. Lee eventos y diagnostico directamente de `../capturas/escritorio/reales`. No hay que copiar ni renombrar los CSV. Exige un ensayo fijo completado por captura y alinea cada uno a su propio inicio, usando el tiempo de ensayo de la ESP32.

La grafica muestra las dos velocidades y la referencia del ensayo frenado. Conserva los huecos de RPM invalidas y señala la posible parada sin dibujar un cero medido. Las velocidades iniciales reales son ligeramente distintas y se conservan en la tabla. No hay interpolacion, extrapolacion ni ajuste de un modelo de la planta.

La tabla calcula la pendiente media mediante una recta entre 0,5 y 2,5 segundos, con medidas validas en ambas pruebas. Una pendiente negativa indica desaceleracion. La aceleracion equivalente se expresa tambien en radianes por segundo al cuadrado. La ultima RPM valida y el primer registro bajo 500 RPM se refieren solo a la ventana del ensayo. NaN en tiempo_bajo500_s significa que no se observo ese cruce durante esa ventana, no que ocurriera en cero segundos.

Guarda PNG, figura editable de MATLAB, tabla CSV y resultado MAT en una subcarpeta de `resultados_reales`. Los archivos de captura originales se conservan. No requiere Control System Toolbox. Una corrida por condicion permite una comparacion exploratoria, sin establecer repetibilidad ni validar un modelo.

Se pueden seleccionar otras capturas pasando dos rutas, primero libre a 45 grados y despues frenada a 30 grados.

```matlab
resultado = comparar_giro_y_freno(carpetaLibre, carpetaFreno);
```

Las secciones siguientes corresponden al protocolo historico de la Tarea 2, con otros angulos y comandos. Para estas dos capturas actuales se debe usar la funcion nueva.


La entrada de estas pruebas es la **orden al SG90** (`90°` libre, `g40` frenado) y la salida es la **RPM estimada por el KY-033**. El motor recibió alimentación directa de una fuente externa y se apagó antes de aplicar el freno. Por eso ambas condiciones terminan en cero; no se puede obtener una ganancia estática de la diferencia entre velocidades finales.

## Cuántos CSV se necesitan

Para demostrar la comparación de la respuesta al escalón en el punto extra 7 de la **Tarea 2**, el [enunciado](../documentos/Tareas_ASM_Tarea2_v5.pdf) no fija un mínimo de repeticiones. El análisis funciona con **una corrida libre y una frenada comparables**: son dos archivos por corrida, `datos_*.csv` y `eventos_*.csv`, cuatro CSV en total. Los pares 1 y 2 son los usados en el video y el informe. La exigencia de **tres repeticiones por condición y dos velocidades iniciales** pertenece al [Proyecto Grupal 2](../../documentos/Proyectos_ASM_Proyecto_Grupal2_v7.pdf), sección de experimentos finales.

## Cómo cargar los CSV

1. Colocar los pares en `proyecto2/tarea2/capturas/`. Mantener el mismo identificador en ambos nombres. Por ejemplo, una captura anterior:

   ```text
   datos_20261122_021346_890235.csv
   eventos_20261122_021346_890235.csv
   ```

   No cambiar sus encabezados. `datos_` debe tener `tiempo_ms,rpm,servo_cmd_grados`; `eventos_` debe tener `tiempo_ms,tipo,valor`. Los tiempos de ambos archivos pertenecen al mismo reloj de la ESP32. Las capturas y los resultados generados están excluidos de Git para evitar agregarlos por accidente al commit.

   Con el capturador actualizado, los ensayos nuevos se nombran automáticamente `datos_1.csv`/`eventos_1.csv`, luego `datos_2.csv`/`eventos_2.csv`. **ID** significa el texto compartido después de `datos_` y `eventos_`; en esos ejemplos, los ID son `1` y `2`. No hay que escribir ningún ID en los CSV.

2. Abrir MATLAB, seleccionar `proyecto2/tarea2/matlab` como carpeta actual y escribir:

   ```matlab
   ejecutar_analisis
   ```

   El programa lee automáticamente todos los pares de esa carpeta. Si se colocaron los CSV en otra ubicación, se puede cambiar `carpetaCapturas` en [ejecutar_analisis.m](ejecutar_analisis.m) o seleccionar la carpeta cuando MATLAB la solicite.

3. Si la carpeta contiene solo los dos ensayos nuevos, dejar `opciones.ids = {};` y ejecutar sin configurar nada más. Para usar **solo una libre y una frenada** aunque haya más archivos en la carpeta, editar la línea `opciones.ids` en `ejecutar_analisis.m`. Por ejemplo, con los archivos numerados:

   ```matlab
   opciones.ids = {'1', '2'};
   ```

   Dejar `{}` para analizar todos los pares comparables presentes en la carpeta. Con los CSV numerados actuales, incluye la libre `1` y la frenada `2`. En `ejecutar_analisis.m` la banda de inclusión de las frenadas es `[1250 1400]`; las libres se alinean en su primera muestra de `[1250 1350]` tras apagar la fuente. Ambas bandas se pueden ajustar si cambia la velocidad de referencia. Los archivos antiguos se omiten si no están en la carpeta o si se indican únicamente los ID nuevos.

4. Revisar los mensajes **Incluida/Omitida** de la ventana de comandos y `resultado.resumen`. No presentar como ensayo válido una corrida omitida. La columna `rpm_despues_del_primer_cero` avisa si el sensor volvió a reportar RPM después del primer cero; ocurre en la frenada `20261122_021527_884972`, así que ese cero no debe describirse como el instante físico exacto de parada. El programa guarda en `matlab/resultados_reales/`:

   | Archivo | Qué muestra |
   | --- | --- |
   | `resumen_comparacion.csv` | RPM inicial, tiempo a menos de 500 RPM, primer cero indicado y demora entre apagado y `g40`. |
   | `comparacion_real.png` | Curvas originales libres y frenadas, alineadas cerca de 1300 RPM o en la orden `g40`. |
   | `respuesta_escalon_real.png` | Arriba, RPM medidas de las frenadas; abajo, la orden 90°→40° representada como escalón en `t=0`. El contacto físico puede ocurrir después de la orden. |
   | `ajuste_local.png` | Datos y aproximación local del frenado solo antes de 500 RPM. |
   | `impulso_analitico.png` | Impulso matemático del modelo local. |
   | `impulse_matlab.png` | Salida de `impulse(G)` cuando existe Control System Toolbox. |
   | `resumen_modelo.txt`, `resultado.mat` | Parámetros y calidad del ajuste. |

## Qué significa el modelo

El ajuste usa la referencia libre para estimar `k` en `dRPM/dt = -k·RPM` y luego el efecto adicional del freno mediante `dRPM/dt = -k·RPM - c·u`, con `u=0` libre y `u=1` después de ordenar `g40`. En rad/s, la transferencia local es `G(s) = -(c·2π/60)/(s+k)`. El programa informa el coeficiente `R²` de cada frenada. **Revisar las gráficas antes de aceptar el modelo**: el acople oscila, hay pulsos rechazados, el servo tiene retardo físico no medido y la parada en cero no es lineal. `impulse(G)` es la respuesta del modelo, no un impulso físico aplicado al disco.

El video de ejemplo del profesor muestra dos métodos para calcular RPM. Nuestro firmware usa el **tiempo entre pulsos**, como el segundo método del video, y muestra cero tras un intervalo sin flancos. El video también usa PWM, encoder de muchos pulsos, filtro de 25 Hz y control PI; esos valores y componentes corresponden a otro motor. Nuestros CSV se imprimen cada 100 ms, así que no se copia un filtro de 25 Hz: supera la frecuencia de Nyquist de este registro (5 Hz). Para esta tarea el control sigue abierto, sin PID.

El equipo ejecutó `impulse(G)` con Control System Toolbox y las capturas 1 y 2; la imagen `impulse_matlab.png` está copiada en `../informe/imgs/`. Si otra computadora no tiene el complemento, el script genera el impulso analítico, pero no la figura de `impulse` de MATLAB.

## Ejemplos anteriores del compañero

[ejemplo_ideal.m](ejemplo_ideal.m) y [demo_simulada.m](demo_simulada.m) siguen disponibles para practicar con un motor alimentado continuamente y parámetros **hipotéticos**. El [analizador original](analizar_ensayo.m) se adaptó para leer también los pares reales `datos_*.csv`/`eventos_*.csv`: valida cada corrida, reconoce el apagado de la fuente y la orden `g40`, y calcula sus tiempos de caída. `ejecutar_analisis.m` llama a [analizar_frenado_real.m](analizar_frenado_real.m), que usa ese analizador para cada corrida y después compara ambas condiciones, ajusta el modelo local y ejecuta `impulse(G)`. El cálculo anterior para el ejemplo simulado se conserva. No presentar los parámetros de las simulaciones como mediciones del prototipo.

El análisis ya se ejecutó en MATLAB con los pares 1 y 2. Los resultados locales están en `resultados_reales/`, ignorado por Git; las cuatro figuras que usa el informe están copiadas en `../informe/imgs/`.


## Frenado suave con capturas de veinte segundos

Desde esta carpeta se ejecuta el nuevo analisis con

```matlab
suave = caracterizar_frenado_suave;
```

En la primera revision se analizaron nueve corridas nuevas de veinte segundos. La ampliacion a 34 grados se documenta al final de esta seccion y el comando ya la incluye. No se mezclan con las tres pruebas previas de seis segundos a 35 grados. La duracion del ensayo fijo tambien determina la duracion de la referencia dibujada, pero no modifica la orden fija del servo durante la prueba.

| Angulo | Capturas de veinte segundos | Aporte estimado en RPM/s | Alcance |
|---|---|---|---|
| 35 | 223742_465772, 223837_077784, 223932_387862 | 52,972878 | Dos para ajustar y una reservada |
| 34 | 224029_410591, 224130_738496 | 157,215680 | Ajuste con dos, sin comprobacion reservada |
| 36 | 224232_172529 | 8,954416 | Una corrida exploratoria |
| 37 | 224412_621615 | 12,139394 | Una corrida exploratoria |
| 38 | 224513_379441 | 2,746039 | Una corrida exploratoria |
| 45 | 224621_377018 | 1,056225 | Giro libre nuevo, discrepancia respecto del modelo anterior |

Todos los identificadores llevan el prefijo 20261127_. Se conservan completos en el script y los resultados. Las nueve corridas tienen final por duracion. Esto no certifica el instante de parada fisica. Las de 34 a 38 terminan por duracion con ausencia de señal y la de 45 termina por duracion con mediciones aun disponibles.

El calculo reutiliza la banda de 500 a 1100 RPM, intervalos completos posteriores a 0,25 segundos y el operador de promedio de la medicion. Mantiene a y b del modelo libre anterior. No cambia ni interpola las RPM ni usa ceros estimados como medidas validas. Cuenta una vez cada intervalo observado. Los intervalos disponibles son 52 a 54 por corrida a 35 grados, 26 y 29 a 34, y 84, 81, 94 y 95 a 36, 37, 38 y 45 respectivamente.

A 35 grados los ajustes individuales dan 52,062814, 53,982251 y 53,927355 RPM/s. El aporte comun se ajusta solo con las dos primeras. En la tercera, que no modifica el ajuste, el error absoluto medio es 3,308120 RPM, el error cuadratico medio con raiz es 3,576631 RPM y el maximo absoluto es 4,777547 RPM. La comprobacion corresponde a esta banda, usando los tiempos de los intervalos observados. No valida el tiempo de parada ni predice a ciegas los proximos pulsos.

A 34 grados los ajustes individuales dan 170,311736 y 147,656532 RPM/s. Hay diferencia entre ambas corridas y aun falta una tercera reservada para comprobar el modelo comun. Los errores de los demas angulos se calculan dentro de las mismas corridas usadas para ajustar. No deben presentarse como validacion independiente.

El valor de 45 grados no significa que el freno liberado ejerza un frenado adicional medido de 1,056225 RPM/s. Representa la discrepancia que la ecuacion anterior necesita absorber en la nueva corrida libre. Por eso los aportes pequenos de 36 a 38 se consideran exploratorios. La corrida de 45 registra dos saltos rechazados, ningun pulso corto rechazado y ninguna perdida de cola durante el ensayo. Las otras ocho no registran esos rechazos. Se usan solo las medidas aceptadas y se conserva el diagnostico.

El orden entre 36 y 37 no es monotono en estas corridas aisladas. No se impone una recta ni una ley continua entre angulo y aporte. Los parametros son estimaciones locales respecto del modelo libre anterior, no medidas de torque. Tampoco permiten garantizar referencias desde cualquier velocidad inicial.

Los resultados se guardan por separado en resultados_reales/frenado_suave_20s. Incluyen resumen_angulos.csv, corridas.csv, los intervalos por captura, mapa_angulos y comprobacion en PNG y FIG, y caracterizacion.mat. Las opciones permitirExploratorios y permitirAporteNegativo estan desactivadas de forma predeterminada en el analizador general. Este script las activa para permitir uno o dos ensayos por angulo y diagnosticar posibles discrepancias de signo con el modelo libre. Un valor negativo no debe interpretarse como aceleracion producida por el freno. No se ha cambiado el analisis predeterminado de los grupos anteriores.


### Comprobacion ampliada de 34 grados

El mismo comando caracterizar_frenado_suave incorpora ahora cuatro corridas nuevas de veinte segundos a 34 grados. Conserva las dos primeras para ajustar y usa todas las nuevas como comprobaciones reservadas, sin cambiar c34 de 157,215680 RPM/s. Hay seis corridas a 34 y trece corridas en el analisis suave completo. Se mantiene la captura de 38 como evidencia exploratoria, fuera de los angulos propuestos para el control. No se ha cambiado la posicion liberada de 45 grados.

| Captura | Ensayo | Intervalos unicos en banda | Error absoluto medio en RPM | Maximo absoluto en RPM |
|---|---|---|---|---|
| 20261127_233312_551495 | 32 | 28 | 10,049033 | 13,014318 |
| 20261127_233407_607995 | 33 | 29 | 6,162445 | 20,787556 |
| 20261127_233407_607995 | 34 | 27 | 3,116020 | 6,934204 |
| 20261127_233951_894077 | 35 | 29 | 4,869212 | 16,969271 |

El error absoluto medio conjunto es 6,066301 RPM. Se calcula sobre todos los intervalos evaluados de las cuatro corridas, excluyendo el primero de cada una porque fija la condicion inicial. No es una media equiponderada por corrida. Los ajustes individuales diagnosticos de estas cuatro dan 163,549348, 152,233914, 157,102849 y 153,286295 RPM/s. No reemplazan el modelo comun ni se presentan como nueva validacion despues de reajustar.

Los ensayos 33 y 34 comparten una captura con reinicio del contador temporal. El analizador acepta la ruta seguida de #ensayo=33 o #ensayo=34. Primero identifica el ensayo por su evento y numero y despues separa las epocas de tiempo en eventos y diagnostico. Exige que los reinicios de ambas tablas coincidan en cantidad. No ordena juntas las dos epocas ni mezcla ventanas con tiempos reiniciados. Los resultados exportados llevan sufijos _ensayo33 y _ensayo34 para conservar identidades distintas. Una captura con varios ensayos sin selector se rechaza como ambigua.

Los contadores de saltos rechazados de las nuevas corridas son acumulados. Los ensayos 32 y 33 empiezan y terminan con dos y los 34 y 35 con cuatro. No aumentan durante estos ensayos. Tampoco aumentan los pulsos cortos rechazados y no hay perdidas de cola. Se conserva cada diagnostico original.

Las cuatro terminan por duracion con ausencia de señal y no con fallo. Esto no fija un instante de parada medido. La comprobacion sigue limitada a la banda de 500 a 1100 RPM y a este montaje con una marca. Predice medias en intervalos observados y no tiempos futuros de pulsos. No certifica por si sola el seguimiento completo de una referencia con PID.


## Tramos nuevos de frenado fuerte a 25, 26 y 27 grados

El rango de trabajo comunicado por el usuario es de 45 a 25 grados. 26 corresponde a un frenado fuerte dentro de ese rango. El limite de 28 de la primera simulacion era un limite del modelo utilizado y no un limite fisico del servo. El rango configurado actualmente en el firmware aun permite llegar hasta 15 grados y debera revisarse antes de habilitar una prueba PID fisica con el rango de trabajo actualizado. Este analisis no cambia esa configuracion.

Para revisar las nuevas mediciones se ejecuta desde esta carpeta

```matlab
fuerte = caracterizar_frenado_fuerte;
```

| Angulo | Captura | Ensayo | Duracion configurada | Intervalos unicos en banda | Ultima lectura valida |
|---|---|---|---|---|---|
| 25 | 20261127_235851_459064 | 36 | 6 segundos | 6 | 510,86 RPM |
| 26 | 20261127_235944_106032 | 37 | 6 segundos | 6 | 500,87 RPM |
| 26 | 20261128_000037_647391 | 38 | 10 segundos | 6 | 508,40 RPM |
| 27 | 20261128_000124_438590 | 39 | 6 segundos | 8 | 417,53 RPM |

Las cuatro terminan con FALLO_MEDICION. Se aprovechan solo los intervalos validos anteriores al fallo, en la misma banda de 500 a 1100 RPM y con intervalo fisico posterior a 0,25 segundos. Ninguna se cuenta como corrida completa ni como comprobacion reservada. El criterio provisional de posible parada requiere ultima medida de hasta 400 RPM y no se alcanza en estas corridas. El final con fallo no demuestra que el disco siguiera girando. Tampoco demuestra por si solo que se detuviera o que el sensor dejara de funcionar.

Con el modelo libre anterior fijo, el aporte adicional estimado es aproximadamente 1027,732076 RPM/s a 25 grados, 1007,248683 a 26 y 780,508334 a 27. Los dos ajustes individuales de 26 dan 1001,438819 y 1013,173442 RPM/s. El aporte comun de 26 se ajusta con sus dos corridas, sin ninguna reservada. A 25 y 27 se usa una sola corrida por grupo. Los errores mostrados son dentro del ajuste y no validacion independiente. Se conserva la identidad de cada captura y no se rellenan RPM faltantes ni se usan ceros estimados para ajustar.

La nueva estimacion a 25 difiere del aporte exploratorio anterior de unos 1150 RPM/s. La nueva de 27 tambien queda por debajo de la estimacion anterior de 28. Estas diferencias impiden declarar una relacion angular precisa y monotona con todos los grupos actuales. No se impone monotonia, no se identifican causas mecanicas concretas y no se actualiza automaticamente el mapa de la simulacion. Los valores respaldan que es una zona de frenado fuerte, con incertidumbre importante para interpolar.

Durante las cuatro pruebas no aumentan los contadores de pulsos cortos o saltos rechazados y no hay perdidas de cola. El contador de saltos empieza y termina en cuatro. La ultima lectura valida aparece cerca de 1,15 segundos a 25 y 26 y de 1,57 segundos a 27. Es el tiempo de la fila registrada respecto al inicio del ensayo, no el instante de parada ni necesariamente el final fisico del intervalo que produjo esa RPM.

Se exportan tablas, intervalos, PNG, FIG y MAT en resultados_reales/frenado_fuerte_25_26_27. La informacion es util para explorar una ampliacion del modelo hasta 25, pero estos resultados no sustituyen una validacion de la parada ni del PID con una marca por vuelta. No se modifican las capturas, el firmware o sus ganancias.


## Primeras corridas con dos marcas por vuelta

Se agrega caracterizar_dos_marcas.m para mantener separadas las nuevas mediciones de las capturas con una marca. Desde esta carpeta se ejecuta

```matlab
dos = caracterizar_dos_marcas;
```

| Angulo | Captura | Ensayo | Ultima lectura valida | Tiempo de esa fila desde inicio | Intervalos unicos en banda |
|---|---|---|---|---|---|
| 26 | 20261128_010110_023010 | 3 | 268,69 RPM | 1,477 segundos | 6 |
| 27 | 20261128_010024_258929 | 2 | 224,83 RPM | 1,810 segundos | 8 |
| 28 | 20261128_005740_418983 | 1 | 262,39 RPM | 1,657 segundos | 8 |

Los tres ensayos configurados a ocho segundos terminan con ENSAYO_FIN_DURACION_SIN_SENAL y antes emiten FIJO_POSIBLE_PARADA_SIN_PULSOS. No hay FALLO_MEDICION. Son tres condiciones distintas con una corrida cada una, no tres repeticiones de una misma condicion. El final es por tiempo y el evento de posible parada no identifica el instante exacto de detencion.

La reconstruccion usa marcasPorVuelta igual a dos y confirma que RPM y periodo corresponden a 30000000 dividido entre el periodo en microsegundos. Se revisaron todas las filas recientes con RPM finita de las tres capturas y la discrepancia con esa formula es menor de 0,006 RPM, compatible con el redondeo registrado. No se alteran las capturas ni se reutilizan los valores de una marca para interpretar estos periodos.

En 500 a 1100 RPM y con intervalos fisicos posteriores a 0,25 segundos, los aportes adicionales ajustados son aproximadamente 929,819888 RPM/s a 26, 700,968614 a 27 y 722,282669 a 28. Se mantiene a y b del modelo libre anterior. No se reajusta el modelo libre con estos frenados. Cada grupo usa una sola corrida y no tiene comprobacion reservada. Los errores mostrados son de ajuste, no validacion independiente. Los grupos de una marca y sus modelos se conservan.

La nueva estimacion de 27 queda ligeramente por debajo de la de 28. No se fuerza monotonia ni se demuestra una relacion angular exacta a partir de una corrida por angulo. La diferencia frente a estimaciones anteriores puede combinar variacion entre pruebas, el operador de medicion y limites del modelo. No se atribuye a una causa mecanica concreta ni se actualiza automaticamente la simulacion.

Los ensayos contienen 13, 17 y 16 intervalos validos distintos observados por el registro de cien milisegundos a 26, 27 y 28 respectivamente. Ese registro no incluye todos los pulsos del sensor. El contador aceptado aumenta 28, 38 y 34 entre la primera y ultima fila FIJO de cada uno. No aumentan los rechazos de pulsos cortos o saltos y no hay perdidas de cola durante los frenados. El contador de saltos de 26 empieza y termina en tres y los otros en cero.

Las ultimas lecturas validas quedan por debajo de las observadas en las pruebas anteriores de una marca a 26 y 27. Esto muestra mejor cobertura del tramo final en estas capturas, sin demostrar exactitud absoluta ni medir la parada. La separacion angular entre marcas sigue siendo una condicion para interpretar cada periodo como media vuelta. Los CSV a cien milisegundos no bastan para certificar la igualdad geometrica entre ambas marcas.

Las tablas, intervalos, graficas y MAT quedan en resultados_reales/primeras_pruebas_dos_marcas. El firmware y las ganancias no se modifican con este analisis.

El lector distingue ahora el evento RPM_INICIO, cuyo tiempo es cero literal aunque se imprima despues de eventos temporizados, de un reinicio real. Para reconstruir epocas se omiten ese aviso y las filas con tiempo negativo sin origen. Los CSV originales no se editan. Los reinicios reales de tiempo entre ensayos siguen separandose y exigiendo coherencia entre eventos y diagnostico.


## Comprobar el modelo libre anterior con dos marcas

Se agrega validar_giro_libre_dos_marcas.m para las dos corridas completas a 45 grados de veinte segundos. El comando es

```matlab
libre2 = validar_giro_libre_dos_marcas;
```

| Captura | Ensayo | Intervalos unicos en banda | MAE en RPM | RMSE en RPM | Maximo absoluto en RPM |
|---|---|---|---|---|---|
| 20261128_010755_149886 | 4 | 97 | 9,508765 | 13,941533 | 26,510544 |
| 20261128_010906_181118 | 5 | 96 | 9,322390 | 13,474136 | 26,362613 |

La captura 20261128_010900_470325 no contiene ENSAYO_FIJO_INICIO y no participa. Las dos usadas terminan con ENSAYO_FIN_DURACION. Durante los ensayos no aumentan los rechazos ni se pierden elementos de la cola. El acumulado de saltos permanece en seis en la primera y once en la segunda. Al final todavia hay lecturas recientes de 145,21 y 122,20 RPM, respectivamente. No se declara que estuvieran detenidas a los veinte segundos.

Se leen a y b del archivo parametros.csv del modelo libre anterior, sin modificarlos. Se comparan promedios del modelo sobre los intervalos observados de media vuelta, usando dos marcas y solo la banda de 500 a 1100 RPM. La primera media impone una condicion inicial compatible y no se evalua en el error. Las demas medias no corrigen la prediccion ni reajustan parametros. Ambas corridas son comprobaciones del modelo anterior. No se ajusta un nuevo aporte de freno ni una curva sobre estas mediciones.

El modelo describe razonablemente la tendencia general, pero las diferencias se agrupan por paridad del contador. Los intervalos pares presentan aproximadamente veinte RPM mas que la prediccion y los impares quedan mas cerca. La paridad es solo un diagnostico de clases de intervalos y no identifica una marca fisica concreta. Es compatible con sectores angulares desiguales entre marcas, sin demostrar por si sola su separacion ni excluir otras fuentes de error.

Este resultado distingue cobertura temporal de exactitud. Las dos marcas dieron mas lecturas cerca de la parada en las pruebas de freno, pero asumir exactamente media vuelta para sectores desiguales puede generar RPM alternas. No se compensa ajustando a y b ni rellenando datos. Antes de usar ganancias elegidas con medicion ideal, queda pendiente revisar la separacion angular y representar el efecto de estas mediciones en la simulacion. No hace falta ajustar de nuevo todo el modelo solo por agregar una marca.

Se extrae el lector compartido a leer_intervalos_frenado.m. Conserva la seleccion de ensayos, tratamiento de RPM_INICIO y reinicios, validez, deduplicacion y comprobacion de periodo frente al numero de marcas. caracterizar_angulos_freno y este validador utilizan el mismo lector, sin cambiar el significado de sus opciones. La comprobacion por pulsos de la ESP32 no se modifica.

Los resultados se guardan en resultados_reales/validacion_libre_dos_marcas. Incluyen resumen.csv, diagnostico_paridad.csv, intervalos por captura, comprobacion.png, comprobacion.fig y validacion.mat. No reemplazan el modelo anterior ni los resultados de los frenados.


### Capturas con promedio de una vuelta completa

leer_intervalos_frenado distingue las capturas con MEDICION_INTERVALOS de las antiguas por sector. En las nuevas, periodo_us es el tiempo completo de la ventana y la relacion de RPM usa el numero de intervalos registrado. Sin el evento se conserva la interpretacion historica de un solo sector. La configuracion de marcas de las opciones debe coincidir con el metadato. La medida es un promedio de una vuelta, no la velocidad instantanea al final de ella.
