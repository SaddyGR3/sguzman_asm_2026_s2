# Tarea 2: guía de medición y seguimiento de los puntos extra 6 y 7

Fuente de requisitos: [Tareas_ASM_Tarea2_v5.pdf](documentos/Tareas_ASM_Tarea2_v5.pdf), apartados 6 y 7. Este plan se limita a la **Tarea 2**; no incluye el PID ni los puntos extra del Proyecto Grupal 2.

## Estado conocido

| Elemento | Estado | Evidencia o límite |
| --- | --- | --- |
| ESP32 con SG90 y KY-033 | Implementado según el equipo | [Firmware actual](../firmware/freno%20abs/src/main.cpp): GPIO18 para servo y GPIO34 para sensor. |
| Registro `tiempo_ms,rpm,servo_grados` | Implementado | Una fila cada 200 ms. `servo_grados` es **posición ordenada**, no posición ni fuerza medida. |
| Motor DC pequeño | Conectado directamente a fuente externa según el equipo | La tensión real y su estabilidad durante el ensayo están pendientes de registrar. No es el motor de 12 V con reductora que figura en la propuesta inicial. |
| Mini L298N AD70178 | Disponible, sin implementar | No se necesita para aplicar un escalón de **frenado** con el servo mientras el motor mantiene una alimentación fija. |
| Disco MDF y mecanismo de frenado | Disco comunicado: diámetro 12 mm, espesor 3 mm | Confirmar si el diámetro es 12 mm o 12 cm; confirmar que la zapata realmente toca y frena el disco. |
| Datos de respuesta al escalón | Pendiente | La muestra recibida mantiene el servo en 90°; su variación de RPM no identifica un cambio de frenado. |
| Resultados MATLAB y video | Pendiente | El informe contiene una curva teórica, no datos experimentales. |

## Decisión de montaje para esta tarea

Mantener el motor conectado a su fuente externa a una tensión fija durante cada prueba. La ESP32 solo necesita controlar el SG90 y medir con el KY-033. La entrada experimental será **el ángulo ordenado al servo**; la salida será **la velocidad del disco**. El resultado será un modelo experimental local de orden de servo a RPM/rad/s, que incluye el retardo del servo y el contacto mecánico. No equivale a conocer el torque de frenado.

El driver AD70178 podría usarse si se decide cambiar la alimentación del motor mediante la ESP32. Eso es otro experimento y no es requisito para los puntos 6 y 7. Antes de conectarlo habría que comprobar el voltaje real de la fuente y la corriente de arranque/bloqueo del motor frente a los límites del módulo; la descripción comercial no aporta la corriente de este motor.

## Cómo obtener los datos con el montaje actual

1. **Confirmar la medición.** Girar el disco manualmente y verificar cuántas transiciones de salida produce cada vuelta completa. El código asume **una transición `FALLING`**. Para contarlas hace falta una lectura diagnóstica del pin o un contador temporal en el firmware actual, que solo imprime RPM; el LED del módulo puede ayudar a comprobar el paso de la marca, pero no sustituye el conteo digital. Comprobar que las RPM sean plausibles con una medición independiente sencilla, si está disponible. Registrar el número de marcas, su ubicación y la orientación del KY-033.
2. **Calibrar el freno con el motor apagado.** Identificar el ángulo sin contacto y el ángulo en que la zapata empieza a tocar el disco. Elegir un ángulo final moderado que produzca una reducción visible sin bloquear o forzar el SG90. Documentar ambos ángulos y fotografiar el mecanismo. No asumir que 0° equivale a un torque conocido.
3. **Registrar la fuente del motor.** Anotar el valor ajustado o indicado por la fuente. Si se dispone de multímetro, medir la tensión **en paralelo con los terminales del motor**, mientras gira, antes y después del escalón. No se necesita medir corriente para identificar la respuesta entrada–salida. Si solo se conoce el valor nominal de la fuente, registrarlo como nominal, no como tensión medida.
4. **Preparar un comando de escalón.** El comando actual `0` desplaza el servo gradualmente desde 90° y toma alrededor de 1,1 s para todo el recorrido; es una rampa. Agregar al firmware una orden de posición directa a un ángulo elegido y registrar el instante `t0_ms` con el mismo reloj `millis()` usado en el CSV. Mantener el comando gradual disponible si resulta útil para calibrar, pero no usarlo como la entrada escalón.
5. **Ejecutar el ensayo.** Con el motor alimentado de modo constante, arrancar la captura, dejar varios segundos de RPM aproximadamente estables sin contacto, aplicar una sola vez el escalón de frenado y continuar hasta un nuevo régimen aproximadamente estable o hasta detenerse. No cambiar la fuente durante la corrida. Guardar **todo** el registro, no solo un fragmento del descenso.
6. **Repetir y comparar.** Hacer al menos tres corridas con igual tensión, ángulos y velocidad inicial parecida. Guardar también una corrida de referencia con el motor girando sin tocar el freno. Si el motor se desconecta para medir desaceleración libre, etiquetar eso como una prueba distinta: el corte de alimentación cambia también la entrada del sistema.
7. **Revisar la resolución temporal.** Los 200 ms actuales pueden ser insuficientes si el frenado dura cerca de un segundo. Probar un registro más frecuente y, si es posible, guardar los tiempos de los pulsos del sensor. Una sola marca por vuelta limita la rapidez real con que se puede actualizar la estimación de velocidad; imprimir más filas no crea pulsos nuevos. Documentar el intervalo final utilizado.

### Archivos que necesita quien haga MATLAB

Una carpeta por corrida, por ejemplo `ensayo_01/`, con:

- `datos.csv`: encabezado y columnas numéricas `tiempo_ms,rpm,servo_cmd_deg`, sin mensajes de depuración intercalados. El tiempo debe ser monótono y continuo dentro de la corrida. Se puede conservar el CSV de tres columnas actual si se agrega el instante exacto del comando en el archivo de metadatos.
- `metadatos.md`: `t0_ms`, ángulo inicial y final, ángulo aproximado de primer contacto, cantidad de marcas/pulsos por vuelta, intervalo de registro, tensión indicada por la fuente, tensión medida bajo carga si existe, estado del motor durante toda la corrida, diámetro/espesor del disco, observaciones sobre contacto, deslizamiento y detención. Aclarar qué valores son medidos y cuáles son nominales.
- Una foto o un segmento de video que identifique el montaje de esa corrida; conservar sin cambios los CSV originales.

No añadir la tensión del motor a cada fila si solo fue leída manualmente una o dos veces: documentarla en `metadatos.md`. Si cambia apreciablemente durante la prueba, registrar esa variación y no tratarla como una entrada constante.

## Trabajo MATLAB que puede empezar antes de medir

Una persona puede preparar ahora un script que importe el CSV, convierta `tiempo_ms` a segundos relativos a `t0_ms`, convierta RPM a rad/s con `2*pi*rpm/60`, grafique orden del servo y velocidad, y marque los intervalos anterior y posterior al cambio. También puede preparar las funciones de cálculo y las figuras usando datos de ejemplo **claramente identificados como simulados**. No debe llenar el informe con parámetros de ejemplo como si fueran medidos.

Con los datos reales se decidirá si hay un régimen inicial y final suficientes para estimar la ganancia local `K = (omega_final - omega_inicial)/(angulo_final - angulo_inicial)` y una constante de tiempo. Si el comportamiento se aproxima bien por primer orden, se puede construir un modelo local `G(s) = K/(tau*s + 1)` y usar la función `impulse` de MATLAB para mostrar su respuesta impulsiva. Esa respuesta al impulso es **del modelo identificado**, no una medición directa de un impulso mecánico. Si hay retardo, saturación, parada o una respuesta no exponencial, documentar esas limitaciones y no forzar el ajuste.

La persona de MATLAB puede trabajar de forma independiente y luego ejecutar el script con los CSV reales durante la grabación del **video único** exigido por el punto 7. Ese mismo video puede mostrar también la planta funcional solicitada en el punto 6. Debe mostrar el montaje físico en funcionamiento, el instante de aplicación del freno, la explicación del equipo y el análisis en computadora; se agregan las fotografías requeridas para el punto 6.

## Seguimiento

### Punto 6: planta y funcionamiento a lazo abierto

- [x] ESP32 adquiere RPM y ordena el SG90 según el código compartido.
- [x] Motor conectado a fuente externa según el equipo.
- [ ] Confirmar diámetro real del disco y fijación mecánica.
- [ ] Confirmar freno funcional, contacto y reducción de RPM reproducible.
- [ ] Registrar materiales, conexión real y tensión de la fuente.
- [ ] Obtener fotografías del banco final y video de funcionamiento a lazo abierto.

### Punto 7: escalón, MATLAB y video único

- [ ] Añadir diagnóstico temporal de pulsos y verificar un pulso válido por vuelta y plausibilidad de las RPM.
- [ ] Calibrar ángulos sin contacto y con frenado efectivo.
- [ ] Implementar orden directa de servo con marca temporal `t0_ms`.
- [ ] Capturar al menos tres corridas completas con fuente constante y metadatos.
- [ ] Preparar y ejecutar script MATLAB con los CSV reales.
- [ ] Graficar escalón medido, estimar parámetros solo si el ajuste es defendible y mostrar `impulse` del modelo.
- [ ] Integrar resultados reales en el informe, sustituyendo los marcadores pendientes.
- [ ] Grabar un solo video con prueba física, explicación y funcionamiento en computadora.

## Datos por confirmar con el equipo

- ¿El disco tiene 12 mm o 12 cm de diámetro?
- ¿Qué tensión nominal y, si se puede medir, qué tensión bajo carga recibe el motor?
- ¿En qué ángulo empieza el contacto y qué ángulo produce un frenado visible sin forzar el servo?
- ¿El KY-033 detecta exactamente una marca por vuelta en todo el rango de velocidad?
