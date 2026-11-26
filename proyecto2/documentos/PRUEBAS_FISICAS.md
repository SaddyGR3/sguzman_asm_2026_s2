# Guía de pruebas físicas del banco de frenado

Guía preparada el 25 de noviembre de 2026 a partir del firmware de la rama `dg/feat/control-frenado-pid`.

Esta guía permite comprobar el montaje por etapas. Tener pruebas de software aprobadas no significa que la maqueta ya haya sido validada. Completa cada etapa antes de avanzar a la siguiente y conserva los registros de los intentos fallidos.

## Índice

1. [Estado actual y alcance](#1-estado-actual-y-alcance)
2. [Preparar la sesión y el registro](#2-preparar-la-sesión-y-el-registro)
3. [Revisar el montaje sin giro](#3-revisar-el-montaje-sin-giro)
4. [Comprobar el servo y sus límites](#4-comprobar-el-servo-y-sus-límites)
5. [Comprobar el sensor y los pulsos](#5-comprobar-el-sensor-y-los-pulsos)
6. [Verificar el mando del motor](#6-verificar-el-mando-del-motor)
7. [Comprobar preparación y cancelación](#7-comprobar-preparación-y-cancelación)
8. [Medir el giro libre](#8-medir-el-giro-libre)
9. [Medir el frenado fijo](#9-medir-el-frenado-fijo)
10. [Comprobar diagnóstico y finalización](#10-comprobar-diagnóstico-y-finalización)
11. [Preparar y probar el PID](#11-preparar-y-probar-el-pid)
12. [Realizar la comparación final](#12-realizar-la-comparación-final)
13. [Ficha para cada corrida](#13-ficha-para-cada-corrida)
14. [Interpretar eventos frecuentes](#14-interpretar-eventos-frecuentes)
15. [Cerrar la sesión](#15-cerrar-la-sesión)

## 1. Estado actual y alcance

La configuración está en `proyecto2/firmware/freno abs/include/configuracion.h` dentro del repositorio.

| Elemento | Configuración actual | Qué implica |
|---|---|---|
| Servo SG90 | GPIO18 | La posición inicial ordenada es 45 grados. |
| Sensor KY-033 | GPIO34 | Se observan ambos bordes y se cuenta una marca completa. |
| Marcas por vuelta | 1 | Es una suposición que se debe comprobar. |
| Señal del motor | GPIO25 hacia IN1 | El equipo comunicó IN2 a tierra en el AD70178. |
| Control del motor | `controlMotorHabilitado = false` | El firmware no configura ni escribe GPIO25. |
| Actuación PID | `actuacionPIDHabilitada = false` | El comando `pid` no inicia control del servo. |
| Ganancias PID | Kp, Ki y Kd en cero | No hay ganancias ajustadas para la maqueta. |
| Rango automático provisional | 15 a 45 grados | Hay que comprobar contacto, liberación y esfuerzo mecánico. |
| Periodo PID provisional | 20 ms | Hay que comprobar su cumplimiento en la placa. |
| Registro nominal | Cada 100 ms | Son unas diez publicaciones por segundo, sin garantizar diez mediciones nuevas. |

El firmware de la ESP32 solo genera la referencia lineal. El panel permite elegir lineal, exponencial normalizada y coseno suave en la simulación. Estas dos últimas siguen pendientes de integración y validación en la placa. La selección en la PC no cambia la referencia del firmware físico.

Los campos de ganancias y velocidad objetivo de la simulación no ajustan el firmware físico. El motor real se enciende o apaga mediante un GPIO y no regula unas RPM objetivo por sí mismo.

Esta guía no modifica configuraciones ni carga programas automáticamente.

## 2. Preparar la sesión y el registro

### Antes de conectar

- [ ] Anotar quién hace la prueba y quién observa el montaje.
- [ ] Registrar la rama y el commit del firmware que realmente se cargará.
- [ ] Anotar cualquier modificación local de configuración que aún no tenga commit.
- [ ] Identificar el corte físico de alimentación del motor y del actuador.
- [ ] Cerrar PlatformIO Serial Monitor y cualquier programa que ocupe el puerto.

Los comandos siguientes se escriben en una terminal fish.

```fish
cd '/home/saddygr/Documentos/GitHub/sguzman_asm_2026_s2'
git status --short --branch
git log -1 --oneline
```

Registrar por separado qué programa está en la ESP32. Que el repositorio tenga una versión reciente no demuestra que esa versión se haya cargado a la placa.

### Alternativa de terminal

Si se prefiere trabajar sin navegador, ejecutar desde la carpeta de herramientas `python3 panel_frenado.py --modo terminal --puerto-serial /dev/ttyUSB0`, sustituyendo el puerto por el real. La terminal muestra métricas y eventos y permite escribir los mismos comandos con Enter. La guía está en `proyecto2/tarea2/herramientas/TERMINAL.md`. Usar una sola interfaz sobre el puerto serial. Las etapas físicas y los criterios de esta guía son los mismos para las dos interfaces.

### Abrir el panel

```fish
cd '/home/saddygr/Documentos/GitHub/sguzman_asm_2026_s2/proyecto2/tarea2/herramientas'
python3 panel_frenado.py
```

Si falta pyserial, preparar un entorno virtual y usarlo para ejecutar la herramienta.

```fish
python3 -m venv /tmp/asm-panel-venv
/tmp/asm-panel-venv/bin/python -m pip install -r requirements.txt
/tmp/asm-panel-venv/bin/python panel_frenado.py
```

1. Seleccionar ESP32 como fuente, no Simulación.
2. Elegir el puerto correcto y conectar a 115200 baudios.
3. Comprobar que aparezca la fuente ESP32 y que lleguen eventos o diagnóstico.
4. Copiar la ruta de captura que muestra la interfaz.

Abrir el puerto puede reiniciar la placa y llevar el servo a la posición inicial. Hacer esta conexión con el motor apagado y el mecanismo preparado para ese movimiento.

La captura comienza al conectar. Para separar archivos por corrida, cancelar, verificar el estado final, desconectar y volver a conectar antes de la siguiente. La reconexión también puede reiniciar la ESP32. Si se mantiene una conexión para varias corridas, usar los eventos de inicio y final para identificar cada una y anotar esa decisión.

Se guardan `datos_1.csv`, `eventos_1.csv`, `diagnostico_1.csv`, `serial.txt` y `metadatos.json` en una carpeta única bajo `proyecto2/tarea2/capturas/panel/reales`. El sufijo 1 se repite dentro de carpetas distintas y no significa sobrescritura.

## 3. Revisar el montaje sin giro

### Qué hacer

1. Mantener desconectada la alimentación del motor mientras se inspecciona el montaje.
2. Verificar sujeción del disco, eje, acople y mecanismo de frenado. Medir y anotar el diámetro real y su unidad.
3. Revisar que no haya cables ni piezas sueltas en la trayectoria del disco.
4. Comprobar las fuentes y conexiones reales del motor, servo, sensor y driver según sus especificaciones y el módulo físico. No deducir la alimentación a partir de diagramas antiguos propuestos.
5. Confirmar las masas comunes necesarias para las señales de control y la compatibilidad de la salida del sensor con la entrada de la ESP32.
6. Verificar que la alimentación del servo no se tome de la salida de 3,3 V de la ESP32.
7. Identificar físicamente GPIO18, GPIO34, GPIO25, IN1, IN2 y los terminales de alimentación del AD70178.

### Qué registrar

Fotografías del montaje, diámetro, número de marcas, tensiones medidas, fuentes utilizadas y conexiones reales. El documento inicial de componentes contiene propuestas y no sustituye esta comprobación.

### Criterio para continuar

El disco está sujeto, el movimiento tiene espacio libre y las conexiones y alimentaciones están identificadas. No energizar para compensar una conexión dudosa por ensayo y error.

## 4. Comprobar el servo y sus límites

Hacer primero esta prueba con el motor apagado y el freno sin carga mecánica. Si el acople obliga al servo, separarlo para verificar el movimiento antes de aplicar presión al disco.

### Qué hacer

1. Conectar la placa y observar la posición inicial ordenada de 45 grados.
2. En Control manual y calibración, enviar `g45`.
3. Mover hacia el contacto en pasos pequeños. Por ejemplo, `g89`, observar, después `g88` y continuar únicamente mientras el recorrido sea seguro.
4. Identificar el primer contacto y enviar `c` para dejar una marca en los eventos.
5. Identificar un contacto útil sin forzar el mecanismo y enviar `f`.
6. Volver a `g45` y comprobar que el freno realmente se libera.

No saltar directamente a 15 grados solo porque figure como extremo provisional. El recorrido manual admite 0 a 90 grados y no protege automáticamente los límites físicos del montaje.

### Qué registrar

Ángulo que libera, ángulo de primer contacto, ángulo de contacto útil, comportamiento del mecanismo y cualquier vibración o reinicio de la ESP32.

### Criterio para continuar

Las órdenes tienen el sentido esperado y la liberación es real. Si el rango útil cambia, actualizar y documentar la configuración antes de usar ensayos automáticos. La conversión actual supone que 45 grados libera y que bajar el ángulo aumenta el frenado.

## 5. Comprobar el sensor y los pulsos

### Prueba manual de marcas por vuelta

1. Mantener el motor sin alimentación y el freno liberado.
2. Enviar `r` para reiniciar la medición. Este comando no apaga un motor ni libera un servo y solo se usa con el montaje ya en esa condición.
3. Enviar `v` y anotar los contadores iniciales.
4. Girar manualmente diez vueltas completas y terminar en la misma posición angular.
5. Enviar `v` y restar el contador inicial al final.
6. Repetir la comprobación.

Si existe una sola marca detectada por vuelta, se esperan diez pulsos adicionales. Si el resultado no corresponde, revisar marcas, alineación, contraste, vibración y conexión antes de aceptar las RPM. No cambiar `marcasPorVuelta` para ocultar pulsos falsos.

A velocidad manual muy baja, la medición puede aparecer antigua o sin señal. Para esta primera comprobación se usan los contadores, no la validez continua de las RPM.

### Prueba durante giro

Después de validar el mando del motor en la etapa siguiente, observar una condición de giro estable y comparar RPM cruda, RPM validada, rechazos y pérdidas de cola.

Una publicación cada 100 ms puede repetir una medición anterior. El sensor solo entrega una velocidad nueva cuando llega otro intervalo útil entre marcas.

### Criterio para continuar

Se conoce el número real de pulsos por vuelta y hay una zona de RPM con mediciones recientes y consistentes. Los picos grandes deben investigarse con los registros, no borrarse sin explicación. Si se dispone de tacómetro independiente, usarlo para contrastar las RPM y anotar su incertidumbre.

## 6. Verificar el mando del motor

Esta etapa requiere verificar el driver antes de conectarle el motor y conservar deshabilitada la actuación PID.

### Primera comprobación con motor desconectado

1. Confirmar la conexión comunicada, GPIO25 hacia IN1 e IN2 a tierra.
2. Verificar con instrumentos los niveles y el estado de las salidas según el módulo real, sin conectar todavía la carga mecánica.
3. Una vez comprobada la compatibilidad, cambiar únicamente `controlMotorHabilitado` a `true` en la configuración de la versión de prueba. Mantener `actuacionPIDHabilitada` en `false`.
4. Compilar y cargar esa versión identificada con el motor desconectado. Esta guía no realiza la carga por sí sola.
5. Comprobar que `motor_off` ordene apagado y `motor_on` ordene encendido. La polaridad inicial configurada usa HIGH para encendido y necesita verificación física.
6. Probar arranque y reinicio de la ESP32 sin la carga conectada. El driver no debe encender inesperadamente el motor cuando se conecte después. Revisar el circuito si su entrada queda flotante durante arranque o desconexión.

### Comprobación con giro

Con el montaje listo y el freno liberado, conectar el motor con la alimentación apagada. Encender brevemente mediante `motor_on`, observar y enviar `motor_off`.

Comprobar si el apagado deja girar por inercia o introduce frenado eléctrico. No asumir que equivale a desconectar físicamente los cables del motor. Esa condición deberá mantenerse igual en las comparaciones.

### Criterio para continuar

El encendido y apagado reales corresponden a las órdenes. El evento `MOTOR_CMD` registra una orden y no demuestra por sí solo que la alimentación haya cambiado.

Con `controlMotorHabilitado = false`, `motor_off` tampoco puede actuar sobre GPIO25. Si el motor tiene alimentación externa independiente, hace falta cortar esa alimentación físicamente.

## 7. Comprobar preparación y cancelación

Mantener la actuación PID deshabilitada.

### Qué hacer

1. Con el motor apagado, enviar `tiempo6000`. Es un ejemplo de seis segundos, no una duración final ya validada.
2. Enviar `preparar` o usar Preparar en el panel.
3. Comprobar que el servo se libera, el motor se enciende y el modo cambia a `PREPARACION`.
4. Observar la velocidad y la calidad de medición. La preparación no regula unas RPM elegidas.
5. Antes de iniciar otro modo, enviar `cancelar`.
6. Comprobar apagado del motor, liberación del freno, evento `ENSAYO_CANCELADO` y estado `CANCELADO`.

La preparación tiene un límite de 60 segundos. Durante sus primeros tres segundos se concede un margen para obtener pulsos. Después, una medición inválida persistente puede terminarla con fallo.

Si la orden no llega o los actuadores no responden, usar el corte físico previsto. El botón Cancelar no sustituye ese corte.

### Criterio para continuar

La cancelación funciona físicamente y queda registrada. No iniciar ensayos automáticos si solo se ha comprobado el mensaje en pantalla.

## 8. Medir el giro libre

El giro libre deja el freno liberado. Los efectos del motor y driver al apagarlo forman parte de la condición que se está midiendo.

### Qué hacer

1. Elegir una duración de observación. Para observar una desaceleración lenta puede usarse `tiempo30000`, que son treinta segundos, antes de preparar.
2. Elegir la duración en el panel.
3. Pulsar Ciclo libre · sin freno o enviar `auto_fijo45`. El motor se apaga a 1400 RPM y el ensayo empieza al bajar a 1300 RPM.
4. Comprobar `MOTOR_CMD` con valor cero, ángulo de 45 grados y modo `FIJO`.
5. Observar y guardar la caída de velocidad. La línea azul y los cálculos PID son solo comparación y no mueven el freno.
6. Conservar la captura hasta cubrir el tramo de velocidad que interesa estudiar.

Al terminar la duración configurada, el modo pasa a `FINALIZADO` y aparece `ENSAYO_FIN_DURACION`. Eso no demuestra una parada. El motor sigue apagado, el servo liberado y la captura continúa.

Si aparece un fallo antes de ese momento, conservarlo y explicar su causa observada. La ausencia de pulsos al detenerse también puede activar el fallo de medición y no debe convertirse en un éxito inventado.

### Qué aprender

Cuánto desacelera el sistema sin contacto de freno, qué velocidades se pueden medir y qué referencias serían demasiado lentas para seguirlas sin volver a encender el motor.

## 9. Medir el frenado fijo

### Qué hacer

1. Elegir un ángulo ya comprobado físicamente. Empezar con contacto leve antes de probar el extremo de mayor frenado.
2. Configurar la duración antes de preparar.
3. Elegir el ángulo en el panel.
4. Pulsar Iniciar ciclo fijo. El comando es `auto_fijoN`, sustituyendo N por ese ángulo. Inicia toda la secuencia y aplica el freno al bajar a 1300 RPM después del corte a 1400 RPM.
5. Comprobar `ENSAYO_FIJO_INICIO`, apagado del motor y una orden angular constante durante el ensayo.
6. Anotar vibraciones, desplazamiento del contacto, ruido del sensor y cambios visibles en la mecánica.
7. Comprobar liberación al terminar o cancelar.

La orden directa al servo es un cambio de consigna, pero el mecanismo tarda en moverse. El instante de orden no garantiza contacto instantáneo ni torque conocido. La rampa del comando `0` no sirve como un escalón de identificación.

### Qué aprender

Cómo cambia la respuesta con distintos ángulos, si el frenado es repetible y si un modelo local representa los datos bajo esas condiciones. Reservar mediciones distintas para validar el modelo, en vez de evaluar solo los datos usados para ajustarlo.

El registro `u_aplicada` pertenece a órdenes del modo PID y queda NaN en FIJO. En este ensayo la entrada conocida es el ángulo ordenado. Conservarlo y no inventar una medición de fuerza o torque a partir de ese campo.

## 10. Comprobar diagnóstico y finalización

### Qué observar durante las pruebas anteriores

| Señal | Qué revisar |
|---|---|
| RPM cruda y validada | Picos, huecos y diferencias entre ambas. |
| Estado de medición | Cuándo es reciente, antigua, sospechosa o sin señal. |
| Rechazos y último periodo rechazado | Si coinciden con vibraciones o interferencias observadas. |
| Pérdidas de cola | Si aumentan durante la prueba. |
| Antigüedad | Si la velocidad mostrada está basada en una marca demasiado vieja. |
| Eventos y modo | Si una orden fue aceptada o solo enviada. |

No desconectar cables de potencia ni mover el sensor junto al disco en giro para provocar un fallo. Si se quiere comprobar pérdida de señal, preparar una forma de bloquear ópticamente la detección desde fuera de las partes móviles y verificarla primero con el sistema detenido.

Una lectura inválida durante 1500 ms continuos en un ensayo puede producir `FALLO_MEDICION`, apagar el motor y liberar el freno. El intervalo se cuenta desde que la lectura se vuelve inválida, no necesariamente desde el último pulso. El apagado y la liberación también deben comprobarse físicamente.

La indicación histórica de cero después de más de un segundo sin pulsos no localiza el instante exacto de parada. Distinguir ausencia de señal de una detención observada por otro medio.

## 11. Preparar y probar el PID

No avanzar a esta etapa únicamente porque la simulación se vea bien.

### Requisitos previos

- [ ] Servo y rango de contacto comprobados.
- [ ] Mando y apagado del motor verificados.
- [ ] Pulsos por vuelta comprobados y medición utilizable.
- [ ] Cancelación física comprobada.
- [ ] Datos de giro libre y frenado fijo guardados.
- [ ] Modelo y condiciones de validez documentados.
- [ ] Referencia y duración compatibles con la capacidad del freno.
- [ ] Ganancias iniciales justificadas para la planta real.

Las ganancias se eligen mediante el modelo, análisis y ajuste experimental. El firmware actual no las sintoniza automáticamente. Los valores 0,005 o 1 usados en la planta ficticia no son una recomendación para la maqueta.

### Preparar la configuración de prueba

Configurar `pidKp`, `pidKi` y `pidKd`, el filtro y el periodo según el diseño. Habilitar `actuacionPIDHabilitada` solo después de las comprobaciones anteriores. El motor también debe estar habilitado. Compilar y cargar la versión identificada y registrar exactamente los valores utilizados.

La primera comprobación de órdenes del PID puede hacerse con el mecanismo de freno desacoplado y el disco sujeto. Sin contacto, el controlador puede pedir frenado máximo al no conseguir desacelerar. Esa prueba verifica órdenes y límites, no demuestra seguimiento.

### Primera prueba con contacto

1. Configurar duración antes de preparar y verificar los valores cargados.
2. Preparar el disco y registrar una velocidad inicial dentro de la condición elegida.
3. Pulsar Iniciar PID.
4. Comprobar `ENSAYO_PID_INICIO`, motor apagado, modo `PID` y estado `CONTROLANDO` cuando la medición sea válida.
5. Observar referencia y velocidad, error, orden angular y acción limitada.
6. Si la velocidad válida queda por debajo de la referencia, comprobar que se ordene liberar el freno.
7. Cancelar ante un movimiento mecánico inadecuado, pérdida de fijación o comportamiento que requiera revisar el montaje. Si falla la comunicación, usar el corte físico.
8. Comparar el registro antes de cambiar un parámetro. Mantener iguales las demás condiciones.

### Final de PID y temporización

El criterio provisional exige completar la referencia y confirmar 100 RPM o menos, con medición válida, durante 300 ms. Hay un máximo de dos segundos adicionales para lograrlo. Si no se confirma aparece `PID_FIN_NO_CONFIRMADO`.

Esto indica baja velocidad estimada y no parada exacta. El sensor puede quedarse sin pulsos al parar y no confirmar el criterio. Es una limitación que se debe estudiar con las pruebas físicas, sin modificar umbrales solo para ocultar fallos.

Revisar `pid_dt_us`, `pid_omitidos` y `pid_tiempo_calculo_us`. El periodo nominal es 20 ms y un intervalo superior a 100 ms entre cálculos termina el modo PID con fallo. La duración del cálculo no incluye toda la latencia del servo o de impresión serial. Registrar resultados reales antes de afirmar que el muestreo es adecuado.

## 12. Realizar la comparación final

El enunciado pide comparar frenado fijo y frenado con PID, con dos velocidades iniciales y al menos tres repeticiones por condición. Para una referencia temporal definida, la matriz mínima es la siguiente.

| Condición | Repetición 1 | Repetición 2 | Repetición 3 |
|---|---|---|---|
| Frenado fijo desde velocidad A | A-F1 | A-F2 | A-F3 |
| PID desde velocidad A | A-P1 | A-P2 | A-P3 |
| Frenado fijo desde velocidad B | B-F1 | B-F2 | B-F3 |
| PID desde velocidad B | B-P1 | B-P2 | B-P3 |

Son doce corridas. Las pruebas de puesta en marcha, el giro libre y los intentos descartados no sustituyen automáticamente estas repeticiones. No se requiere una corrida distinta por cada señal registrada.

### Definir antes de medir

Elegir velocidades A y B dentro del rango validado, una tolerancia para aceptar la velocidad inicial, ángulo fijo de comparación, referencia, duración, ganancias y criterios de fallo. La tolerancia debe quedar documentada y mantenerse entre repeticiones.

El motor actual no tiene regulación de velocidad por PWM. Para obtener dos velocidades iniciales hay que acordar un procedimiento reproducible compatible con el montaje, por ejemplo dos ajustes permitidos de alimentación. Verificar su compatibilidad antes de usarlos. Iniciar mientras acelera también cambia la condición inicial y no se debe presentar como un régimen estable sin comprobarlo.

No usar `motor_off` durante preparación esperando iniciar después el PID, porque ese comando cancela el ensayo activo. El inicio de FIJO o PID ya ordena apagar el motor.

Mantener acople, geometría de contacto, condición del driver al apagar, alimentación, calentamiento y procedimiento tan equivalentes como sea posible. Documentar los cambios y los descartes. Para FIJO conservar el mismo ángulo entre repeticiones. Para PID conservar curva, duración, ganancias y filtro.

Las tres curvas elegidas para el futuro no implican que las doce corridas cubran automáticamente una comparación completa de cada curva. El mínimo indicado corresponde a una comparación con una referencia definida. Si se amplía la evaluación, documentar la matriz adicional.

### Qué comparar

Registrar referencia, velocidad medida, error y acción de control en cada corrida. Usar ángulo y eventos en FIJO, y distinguir acción solicitada, limitada y orden al servo en PID. No confundir orden normalizada con torque medido.

Comparar error de seguimiento mediante una métrica definida, tiempo de frenado bajo un criterio explícito, oscilaciones, saturación y variación entre repeticiones. Elegir la misma ventana de análisis y explicar qué se hace con mediciones inválidas. No convertir huecos o NaN en cero para mejorar la métrica.

El eje de la interfaz usa tiempo de recepción en la PC. Para cálculos usar los tiempos registrados, el tiempo de ensayo y sus eventos de inicio. Un menor tiempo de frenado no demuestra por sí solo mejor seguimiento.

## 13. Ficha para cada corrida

Copiar esta ficha a un archivo junto a los CSV de la corrida.

| Dato | Valor |
|---|---|
| Identificador de corrida | |
| Fecha, hora y participantes | |
| Objetivo de la prueba | |
| Rama, commit y cambios locales | |
| Firmware realmente cargado | |
| Ruta completa de captura | |
| Motor y fuente utilizados | |
| Alimentación medida y ajuste de fuente | |
| Driver y comportamiento de apagado | |
| Diámetro del disco y acople | |
| Marcas por vuelta verificadas | |
| Ángulos de liberación, contacto y ensayo | |
| Modo utilizado | |
| Velocidad inicial objetivo y tolerancia | |
| Velocidad inicial registrada | |
| Referencia y duración configurada | |
| Kp, Ki, Kd y filtro | |
| Periodo de control | |
| Inicio y final identificados por eventos | |
| Motivo de finalización | |
| Observación física del final | |
| Picos, rechazos o pérdidas observadas | |
| Resultado aceptado, descartado o pendiente | |
| Motivo de descarte si corresponde | |
| Cambios para la siguiente prueba | |

`RPM_INICIAL_X100` registra la velocidad inicial multiplicada por cien. Dividir su valor entre cien para recuperar RPM. El valor del panel después de finalizar puede corresponder a una lectura posterior y no a la velocidad exacta de finalización.

## 14. Interpretar eventos frecuentes

| Evento o estado | Interpretación y siguiente comprobación |
|---|---|
| `MOTOR_NO_HABILITADO` | La configuración no permite actuar sobre el GPIO del motor. Revisar la versión cargada y completar la verificación del driver. |
| `REQUIERE_PREPARAR` | No se inició la preparación requerida para comenzar FIJO o PID. |
| `MEDICION_INICIO_INVALIDA` | No hay medición inicial utilizable. Se requieren RPM positivas y válidas, antigüedad de hasta 250 ms y al menos dos pulsos aceptados desde preparar. |
| `PID_ACTUACION_DESHABILITADA` | La versión cargada no permite que el PID mueva el servo. |
| `PID_GANANCIAS_NO_CONFIGURADAS` | No hay configuración PID utilizable con alguna ganancia positiva. |
| `COMANDO_BLOQUEADO_ENSAYO` | La orden interfiere con un ensayo activo. Cancelar antes de cambiar condiciones. |
| `FALLO_TIEMPO_PREPARACION` | Se superó el límite de preparación de sesenta segundos. |
| `FALLO_MEDICION` | La medición inválida persistió. Investigar sensor y estado físico sin asumir avería ni parada. |
| `PID_FALLO_TIEMPO` | El cálculo no se ejecutó dentro del intervalo máximo permitido. Revisar también `PID_RETRASO_US`. |
| `ENSAYO_FIN_DURACION` | Terminó el intervalo de FIJO. No certifica detención. |
| `ENSAYO_PID_FIN_BAJA_RPM` | Se confirmó el criterio provisional de baja velocidad. No certifica parada exacta. |
| `PID_FIN_NO_CONFIRMADO` | Se agotó el tiempo adicional sin confirmar el final de PID. |
| `ENSAYO_CANCELADO` | Se solicitó apagado del motor y liberación del freno. Comprobar la respuesta física. |

## 15. Cerrar la sesión

1. Enviar Cancelar y observar su evento y el estado `CANCELADO`.
2. Verificar físicamente que el motor no recibe la orden de giro y el freno se libera, siempre que esa condición sea segura para el montaje.
3. Esperar a que el disco se detenga antes de tocarlo o ajustar piezas. Si necesita corte físico de energía, usarlo.
4. Desconectar el panel para cerrar los archivos.
5. Completar la ficha y revisar que los CSV y metadatos existan.
6. Conservar fallos y observaciones junto a la captura.

Cerrar el navegador, pausar la vista o desconectar el USB no garantiza cancelar una prueba. El comando `s` solo detiene una rampa manual y no es una parada general del sistema.

## Documentos de apoyo

El enunciado original está en `proyecto2/documentos/Proyectos_ASM_Proyecto_Grupal2_v7.pdf`. La guía del panel está en `proyecto2/tarea2/herramientas/panel/README.md`. La bitácora está en `proyecto2/firmware/freno abs/BITACORA.md`. El archivo `plan.md` con acuerdos se conserva en la carpeta externa de documentos del proyecto.

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
