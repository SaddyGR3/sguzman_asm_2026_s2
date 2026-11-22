# Tarea 2: guía de medición y seguimiento de los puntos extra 6 y 7

Fuente de requisitos: [Tareas_ASM_Tarea2_v5.pdf](documentos/Tareas_ASM_Tarea2_v5.pdf), apartados 6 y 7. Este plan se limita a la **Tarea 2**; no incluye el PID ni los puntos extra del Proyecto Grupal 2.

## Estado conocido

| Elemento | Estado | Evidencia o límite |
| --- | --- | --- |
| ESP32 con SG90 y KY-033 | Implementado según el equipo | [Firmware actual](../firmware/freno%20abs/src/main.cpp): GPIO18 para servo y GPIO34 para sensor. |
| Registro `tiempo_ms,rpm,servo_cmd_grados` | Firmware y capturador ejecutados en banco; revisada una referencia con el filtro de 20 ms | La captura conserva RPM y eventos de apagado. `servo_cmd_grados` es **posición ordenada**, no posición ni fuerza medida. |
| Motor DC pequeño | Conectado directamente a fuente externa según el equipo | Fuente ajustada o indicando **1 V** durante las corridas; no es una medición de tensión en terminales bajo carga. Se apaga la fuente con los cables conectados y se frena mientras el disco sigue girando. No es el motor de 12 V con reductora de la propuesta inicial. |
| Mini L298N AD70178 | Disponible, sin implementar | No se necesita para el ensayo de frenado sobre el disco que gira por inercia. |
| Disco MDF y mecanismo de frenado | Disco confirmado: diámetro **12 cm**, espesor **3 mm**; el brazo del SG90 lleva hule unido a una esponja que toca la cara superior del disco; acople provisional y disco oscilante | El escalón usado en las capturas principales fue 90°→40°. Primer contacto marcado a 47° en calibración; comprobar visualmente que el SG90 no se fuerce. |
| Datos de respuesta al escalón | Tres corridas nuevas con orden directa de 90° a 40° | Dos corridas comparables al ordenar el freno cerca de 1300 RPM; una tuvo demora al enviar la orden y se separa de esa comparación. Comprobar que el SG90 no se fuerce. |
| Resultados MATLAB y video | Scripts preparados; ejecución con datos reales y video pendientes | El commit `02fcb3c` aporta ejemplos simulados para motor alimentado continuamente. [El análisis de las cinco corridas reales](analisis/README.md) usa el protocolo con motor apagado. El informe ya incorpora resultados de los CSV; conserva una curva teórica claramente identificada y señala las evidencias pendientes. |

Última prueba manual comunicada por el equipo: `RPM_INICIO` apareció y `PULSOS=5` tras el reinicio; el servo permaneció en 90° y las RPM mostradas fueron cero después de detener el disco. Esto confirma que la captura funciona en el montaje, pero falta comparar el contador **antes y después** de un número conocido de vueltas y revisar los archivos CSV. Los archivos de esa corrida no están disponibles en este repositorio.

Calibración comunicada y revisada: `CONTACTO_INICIAL=47°` y `CONTACTO_UTIL=19°`, ambos con `t=-1` porque el disco no giró. El CSV numérico solo tenía encabezado, como corresponde a una calibración sin RPM. Los 19° son un candidato marcado por el equipo, no una reducción de RPM demostrada. Los archivos de esa calibración ya no están en esta carpeta.

Primera referencia de giro libre revisada con el firmware anterior: servo fijo a 90°, `MOTOR_OFF_MANUAL=53463 ms`, mediana de RPM en los 3,5 s previos ≈1674, primera fila con `RPM=0` después del apagado a 72499 ms: **19,036 s hasta cero indicado por el firmware**, que incluye su espera de hasta un segundo sin pulso y no mide el instante exacto de parada. La curva cae de forma general, pero hay picos falsos de 4278 a 19330 RPM; equivalen a intervalos entre pulsos de 3,1 a 14,0 ms, frente a unas 34–38 ms por vuelta antes del apagado. Los CSV originales de esta corrida ya no están en esta carpeta.

Segunda referencia con el firmware anterior: `PULSOS` pasó de 0 a 1066, servo fijo a 90°, `MOTOR_OFF_MANUAL=36945 ms`, mediana de RPM en los 6,9 s previos ≈1696, primera fila con `RPM=0` a 58199 ms: **21,254 s hasta cero indicado**. La curva de desaceleración es mayormente continua, pero conserva picos falsos de hasta 10631 RPM; uno equivale a 16,2 ms entre pulsos. El equipo confirmó que esta captura se hizo con el firmware anterior. Estos CSV también fueron retirados de la carpeta; ambas referencias anteriores se conservan solo como observaciones exploratorias.

Referencia con el filtro de 20 ms (CSV originales retirados de esta carpeta): servo fijo a 90°, `PULSOS=0` al inicio y 1170 al final; `PULSOS_RECHAZADOS=517` al final. `MOTOR_OFF_MANUAL=49266 ms`, mediana de RPM en los 4,3 s previos ≈1550, primera fila con `RPM=0` a 67199 ms: **17,933 s hasta cero indicado**, con el mismo límite temporal del firmware. La caída es mayormente continua; persiste un pico aislado de 2372 RPM cerca del apagado. El gran número de pulsos rechazados y la oscilación visible del disco limitan la precisión. Esta corrida histórica no entra en el análisis MATLAB; las tres referencias libres posteriores sí conservan sus CSV.

Primer ensayo piloto de frenado (CSV originales retirados de esta carpeta): el motor se marcó apagado a `38771 ms` y el comando directo `g40` se envió a `45133 ms` (**6,362 s después**), cuando la mediana de las últimas cinco lecturas era ≈1024 RPM. La primera fila con `RPM=0` llegó a `47299 ms`, **2,166 s desde el comando**; antes había bajado de 500 RPM en 0,866 s. El capturador registró 988 pulsos aceptados y 378 rechazados. El servo había estado ordenado a 90° antes del escalón. La captura posterior `020824_448898` solo contiene un comando a 47° sin RPM; no es otro ensayo de frenado.

Comparación exploratoria anterior a velocidad parecida: la referencia libre con filtro registró ≈1019 RPM a `54099 ms` y desde ahí tardó **6,100 s** en bajar de 500 RPM y **13,100 s** en indicar cero. Frente al piloto con `g40`, la reducción es grande y visible, aunque el indicador de cero incorpora hasta un segundo sin pulso y no marca el instante mecánico exacto. La orden al servo se registra antes del contacto físico; este retardo tampoco se mide. Como se retiraron los CSV originales, esta comparación no reemplaza una referencia libre conservada para MATLAB.

### Corridas de frenado nuevas conservadas (22 de noviembre)

| Captura (`datos_` y `eventos_`) | Apagado → orden `g40` | RPM antes de `g40`¹ | Orden → menos de 500 RPM | Orden → cero indicado | Uso |
| --- | ---: | ---: | ---: | ---: | --- |
| [021346_890235](capturas/datos_20261122_021346_890235.csv) | 2,943 s | 1296 | 1,168 s | 2,768 s | Corrida principal. |
| [021437_725528](capturas/datos_20261122_021437_725528.csv) | 6,388 s | 1006 | 0,778 s | 1,978 s | La orden tardó en enviarse; hay `COMANDO_INVALIDO` antes de `SERVO_CMD`. Separar de las dos corridas a ~1300 RPM; sirve como evidencia adicional si el freno sí hizo contacto. |
| [021527_884972](capturas/datos_20261122_021527_884972.csv) | 2,789 s | 1352 | 1,178 s | 2,378 s | Corrida principal. |

¹ Mediana de las cinco muestras previas al comando. El cero es el que informa el firmware tras esperar sin pulsos, no el instante exacto de parada física. Los eventos de cada captura están en el archivo [primero](capturas/eventos_20261122_021346_890235.csv), [segundo](capturas/eventos_20261122_021437_725528.csv) y [tercero](capturas/eventos_20261122_021527_884972.csv). Las corridas primera y tercera muestran una desaceleración similar tras `g40`; no atribuir diferencias pequeñas a la mecánica sin repetir más veces. Conservar estos seis CSV originales para MATLAB y el video.

### Referencias libres conservadas (22 de noviembre)

Tres corridas completas con el SG90 ordenado a 90° y `MOTOR_OFF_MANUAL` registrado. Para compararlas con las dos frenadas principales, el tiempo cero de esta tabla es la primera muestra posterior al apagado entre 1250 y 1350 RPM, no el instante en que se apagó el motor.

| Captura (`datos_` y `eventos_`) | RPM de referencia | Hasta menos de 500 RPM | Hasta cero indicado |
| --- | ---: | ---: | ---: |
| [022222_989250](capturas/datos_20261122_022222_989250.csv) | 1320 | 11,5 s | 20,1 s |
| [022329_134136](capturas/datos_20261122_022329_134136.csv) | 1350 | 11,4 s | 20,0 s |
| [022428_691694](capturas/datos_20261122_022428_691694.csv) | 1348 | 11,6 s | 20,0 s |

Sus eventos se conservan en [corrida 1](capturas/eventos_20261122_022222_989250.csv), [corrida 2](capturas/eventos_20261122_022329_134136.csv) y [corrida 3](capturas/eventos_20261122_022428_691694.csv). La captura [022203_392191](capturas/datos_20261122_022203_392191.csv) no tiene marca de apagado ni giro útil; no incluirla en el análisis. Desde RPM iniciales comparables (~1300), las frenadas tardaron ~1,17 s en bajar de 500 RPM y las libres ~11,5 s. Es una comparación de velocidad, no una medida de torque. Las cinco corridas útiles están suficientes para iniciar MATLAB y el equipo indicó que debe devolver la fuente; no se programan más ensayos.

Si ya se grabó el montaje físico y la aplicación del freno, conservar ese material para el video único del punto 7 y las fotos del punto 6. Si la fuente ya se devolvió, documentar con honestidad la evidencia visual disponible; no hace falta repetir las mediciones. El análisis en computadora se puede grabar después e integrar en el mismo video final. La lectura de 1 V de la fuente no debe presentarse como tensión medida en los terminales del motor.

## Decisión de montaje para esta tarea

Usar como protocolo principal el montaje que el equipo ya emplea: acelerar el disco con la fuente externa, **desconectar la alimentación del motor** y aplicar después un cambio definido al SG90 mientras el disco aún gira. La ESP32 controla el SG90 y mide con el KY-033. No es obligatorio frenar con el motor alimentado para demostrar un escalón de freno en esta tarea.

La desconexión y el frenado son **dos eventos distintos**: hay que registrar el instante de cada uno. La entrada que se quiere estudiar es **el ángulo ordenado al servo**; la salida es **la velocidad del disco**. Hacer una prueba de giro libre tras apagar la fuente permite distinguir la desaceleración natural de la adicional causada por el freno. Si ambos cambios ocurren a la vez, la curva mezcla sus efectos y no identifica la acción del freno por sí sola.

En este protocolo, el disco termina en cero RPM tanto con freno como sin él. Por eso no se debe calcular una ganancia estática a partir de RPM finales ni presentar un equilibrio positivo como resultado experimental. Se pueden comparar los tiempos de parada y las curvas de desaceleración, y ajustar un modelo dinámico local **antes de que el disco se detenga**, si los datos lo permiten. El ángulo ordenado no equivale a conocer el torque de frenado. El informe ya distingue la figura teórica, que supone torque motor constante, de los ensayos reales con la fuente apagada.

El driver AD70178 podría usarse si se decide automatizar la alimentación del motor mediante la ESP32. No se requiere para este protocolo. Antes de conectarlo habría que comprobar el voltaje real de la fuente y la corriente de arranque/bloqueo del motor frente a los límites del módulo; la descripción comercial no aporta la corriente de este motor.

## Cómo obtener los datos con el montaje actual

1. **Confirmar la medición.** Seguir la [prueba de cuatro lecturas `v`](herramientas/README.md#comprobar-que-el-ky-033-cuenta-una-marca-por-vuelta): dos controles con disco quieto y cinco vueltas completas. Verificar que el contador aumente cinco, es decir, **una transición `FALLING` por vuelta**, como supone el firmware. Ajustar el sensor si no ocurre y repetir la prueba tres veces. Comprobar que las RPM sean plausibles con una medición independiente sencilla, si está disponible. Registrar el número de marcas, su ubicación y la orientación del KY-033.
2. **Calibrar el freno con el motor apagado.** Mover el servo por pasos con las flechas del capturador. Identificar el ángulo sin contacto y pulsar `c` cuando la zapata empiece a tocar el disco. Elegir un ángulo final moderado que produzca una reducción visible sin bloquear o forzar el SG90 y pulsar `f` para guardarlo. Documentar ambos ángulos y fotografiar el mecanismo. No asumir que 0° equivale a un torque conocido.
3. **Registrar cómo se prepara y desconecta el motor.** Anotar el ajuste de tensión de la fuente. Si hay multímetro, medir la tensión **en paralelo con los terminales del motor mientras está alimentado y girando**. No se necesita medir corriente para comparar giro libre y frenado. Dejar por escrito si se apaga la fuente con los cables conectados, se abre un interruptor o se desconectan físicamente los terminales; usar siempre el mismo método, porque puede cambiar la desaceleración natural.
4. **Empezar con una prueba de referencia.** Registrar RPM mientras el motor acelera, apagar su fuente sin retirar los cables, pulsar `m` para marcar aproximadamente `t_motor_off_ms` y dejar girar el disco **sin freno** hasta detenerse. Esta curva muestra cuánto se frena por sí solo el montaje. El tiempo de reacción entre apagar y pulsar `m` es una incertidumbre que debe declararse.
5. **Preparar un comando de escalón de freno.** El comando `gN` ya ordena directamente cualquier ángulo de 0° a 90° y registra el evento `SERVO_CMD` como `t_freno_ms`. El comando anterior `0` desplaza gradualmente el servo y toma alrededor de 1,1 s para todo el recorrido; es una rampa, por lo que no se usa para la entrada escalón. Conservar su velocidad para calibración.
6. **Hacer la prueba de frenado.** Acelerar el disco de manera similar a la prueba libre, iniciar la captura, desconectar el motor y, **después**, aplicar una sola vez la orden directa del freno mientras aún haya RPM suficientes para medir. Dejar algunos datos entre desconexión y frenado, si el tiempo de giro lo permite. Registrar ambos eventos por separado y continuar hasta detenerse. Guardar el CSV completo.
7. **Comparar las corridas conservadas.** Usar las tres libres y las dos frenadas principales con RPM parecidas al ordenar el freno. La tercera frenada tuvo orden tardía y se documenta por separado. El equipo debe devolver la fuente, así que el análisis y el video se preparan con los datos actuales.
8. **Revisar la resolución temporal.** El registro imprimió filas cada 100 ms en el banco. Si el frenado es muy rápido, guardar también tiempos de pulsos sería una mejora posterior. Una sola marca por vuelta limita la rapidez real con que se puede actualizar la estimación de velocidad; imprimir más filas no crea pulsos nuevos. Documentar el intervalo utilizado.

### Archivos que necesita quien haga MATLAB

Una carpeta por corrida, por ejemplo `ensayo_01/`, con:

- `datos_*.csv`: columnas numéricas `tiempo_ms,rpm,servo_cmd_grados`, guardadas automáticamente por el capturador. El tiempo debe ser monótono y continuo dentro de la corrida.
- `eventos_*.csv`: `RPM_INICIO`, `MOTOR_OFF_MANUAL` y `SERVO_CMD`, guardados por el capturador con tiempos relativos a la primera RPM válida.
- `metadatos.md`: tipo de corrida (`libre` o `frenada`), precisión aproximada del instante manual de apagado, ángulo inicial y final, ángulo de primer contacto, cantidad de marcas/pulsos por vuelta, intervalo de registro, tensión indicada por la fuente, tensión medida bajo carga si existe, método de desconexión, diámetro/espesor del disco y observaciones. Aclarar qué valores son medidos y cuáles son nominales.
- Una foto o un segmento de video que identifique el montaje de esa corrida; conservar sin cambios los CSV originales.

No añadir la tensión del motor a cada fila si solo fue leída manualmente una o dos veces: documentarla en `metadatos.md`. La tensión de preparación debe ser comparable entre corridas; durante el frenado de este protocolo el motor está desconectado.

## Análisis MATLAB con las capturas disponibles

El [script MATLAB](analisis/analizar_capturas.m) importa los CSV reales, alinea las curvas cerca de 1300 RPM, convierte la velocidad a rad/s para un modelo local, grafica las cinco corridas y calcula tiempos de caída. Si está disponible Control System Toolbox, usa `impulse` sobre el modelo local. Se debe ejecutar en la computadora del equipo o en LAIMI y revisar las figuras antes de incorporarlas al informe. No presentar parámetros de ejemplo como si fueran medidos.

Con los datos reales se decidirá si el tramo con `rpm > 0` y motor desconectado permite ajustar un modelo dinámico local del efecto adicional del freno, usando la curva libre como referencia. **No** se calcula `K` con la diferencia de RPM finales: ambas corridas terminan en cero. Si se identifica un modelo lineal local defendible, se puede usar `impulse` de MATLAB para mostrar su respuesta impulsiva; esa respuesta es **del modelo**, no una medición directa de un impulso mecánico. Si el registro es demasiado corto, ruidoso o no lineal, presentar las curvas y métricas medibles, y explicar por qué el modelo simplificado no ajusta.

La persona de MATLAB puede trabajar de forma independiente y luego ejecutar el script con los CSV reales durante la grabación del **video único** exigido por el punto 7. Ese mismo video puede mostrar también la planta funcional solicitada en el punto 6. Debe mostrar el montaje físico en funcionamiento, el instante de aplicación del freno, la explicación del equipo y el análisis en computadora; se agregan las fotografías requeridas para el punto 6.

## Seguimiento

### Punto 6: planta y funcionamiento a lazo abierto

- [x] ESP32 adquiere RPM y ordena el SG90 según el código compartido.
- [x] Motor conectado a fuente externa según el equipo.
- [x] Confirmar diámetro del disco: 12 cm; documentar fijación mecánica provisional y oscilación.
- [x] Confirmar reducción de RPM reproducible tras ordenar 40° en dos corridas cercanas a 1300 RPM; el contacto físico y el esfuerzo del SG90 aún se verifican visualmente.
- [x] Documentar materiales y conexión conocida: fuente indicando 1 V, motor conectado directamente, SG90 y KY-033 alimentados desde la ESP32, esponja sobre la cara superior del disco. Faltan foto y pines exactos de alimentación.
- [ ] Obtener fotografías del banco final y video de funcionamiento a lazo abierto.

### Punto 7: escalón, MATLAB y video único

- [x] Añadir contador de pulsos consultable con `v` y captura CSV en la computadora; revisados los CSV de tres corridas nuevas de frenado.
- [ ] Verificar un pulso válido por vuelta y plausibilidad de las RPM en el banco.
- [x] Marcar primer contacto a 47° y contacto útil candidato a 19°; eventos de calibración revisados.
- [x] Medir un primer escalón `g40` con el disco girando; reducción de RPM evidente frente al giro libre.
- [ ] Confirmar que el SG90 no se fuerza; dos corridas a RPM comparables ya muestran una reducción semejante.
- [x] Implementar orden directa `gN` y movimiento por pasos con flechas en el capturador; pendiente de probar con hardware.
- [x] Cargar el filtro de 20 ms y repetir la referencia libre; la curva mejora, pero el disco oscila y se rechazaron 517 pulsos.
- [x] Capturar y conservar tres corridas libres y dos frenadas principales comparables; existe una tercera frenada con orden tardía. Los metadatos conocidos están documentados en `analisis/METADATOS_MONTAJE.md`.
- [x] Preparar script MATLAB con los CSV reales; pendiente ejecutarlo en MATLAB y guardar sus figuras.
- [x] Comparar giro libre y frenado con las cinco corridas; falta estimar parámetros solo si el ajuste es defendible y mostrar `impulse` del modelo cuando exista.
- [x] Corregir en el informe la descripción del ensayo para indicar que la fuente del motor está apagada durante el frenado.
- [x] Integrar los resultados medibles de los CSV reales en el informe.
- [ ] Grabar un solo video con prueba física, explicación y funcionamiento en computadora.

## Datos por confirmar con el equipo

- Disco confirmado: 12 cm de diámetro y 3 mm de espesor.
- Alimentación confirmada: fuente ajustada o indicando 1 V; tensión en terminales bajo carga no medida.
- Método de apagado confirmado: fuente apagada con los cables conectados. El tiempo hasta cero indicado tras el tramo de referencia libre fue de aproximadamente 20 s desde 1300 RPM.
- Primer contacto marcado a 47°; la orden `g40` produjo frenado visible. No se midieron el instante físico de contacto ni la fuerza aplicada.
- Contacto confirmado: esponja unida al hule del brazo del SG90 sobre la cara superior del disco; SG90 y KY-033 alimentados por la ESP32. Faltan los pines concretos de alimentación y una fotografía clara.
- ¿El KY-033 detecta exactamente una marca por vuelta en todo el rango de velocidad?
