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

## Próximo avance

Paso 6 del plan. Conectar la acción limitada con el servo usando el rango calibrado, integrar el modo de lazo cerrado y comprobarlo físicamente. Antes de activarlo deben confirmarse el driver, la medición, los límites y el tratamiento de fallos del controlador.
