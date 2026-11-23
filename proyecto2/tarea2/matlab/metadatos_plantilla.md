# Datos del ensayo

Completar con los valores reales y guardar junto al CSV como `metadatos.md`.

- Identificador del ensayo y fecha pendientes.
- Tipo de datos experimental o simulado pendiente.
- `t0_ms` de la orden de frenado: tomar `SERVO_CMD` del archivo `eventos_*.csv`; en giro libre usar la muestra de RPM de referencia posterior al apagado.
- Ángulo ordenado inicial y final en grados pendientes.
- Ángulo aproximado de primer contacto pendiente.
- Pulsos válidos por vuelta y configuración del sensor pendientes.
- Intervalo de registro en milisegundos pendiente.
- Tensión nominal o indicada por la fuente pendiente.
- Tensión medida bajo carga, si existe, pendiente.
- Instante `MOTOR_OFF_MANUAL` y método de apagado de la fuente pendientes.
- Estado del motor durante el escalón: fuente apagada, cables conectados.
- Diámetro, espesor y material del disco pendientes.
- Contacto del freno, deslizamiento o detención observados pendientes.
- Foto y video asociados pendientes.

Distinguir valores medidos, nominales y supuestos. Este análisis supone que el motor está sin alimentación durante el escalón; las corridas libres y frenadas deben usar el mismo método de apagado. El ángulo es la orden al servo y no representa un torque conocido.
