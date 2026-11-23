# MATLAB para la Tarea 2: capturas reales

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
