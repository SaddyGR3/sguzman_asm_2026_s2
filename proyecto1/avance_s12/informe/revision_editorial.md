# Revisión editorial y de consistencia del 30 de octubre de 2026

Este registro acompaña la revisión del equipo; no se incorpora al PDF.

## Alcance realizado

- Lectura completa de `informe.tex`, sus dos tablas incluidas y los textos de
  los diagramas. Revisión del texto extraído del PDF para detectar notas de
  preparación, marcadores de borrador y diferencias con la fuente.
- Cotejo de las tablas P1–P5 con `simulacion/resultados/comparacion_resumen.csv`;
  DFT y costo con sus archivos JSON/CSV y las tablas generadas.
- Recálculo de respuestas del Sallen-Key, salida ZOH × Sallen-Key, rechazo FIR,
  fase y ganancias notch usando las funciones existentes de `analogico.py` y
  `nodo2.py`, sin alterar algoritmos ni configuraciones.
- Ensayos de alias y de imagen DAC con las mismas funciones auxiliares de
  `pruebas/test_analogico.py`: tonos de pico 0.8 y amplitud por mínimos cuadrados.
- Cotejo de tiempos y espurias del generador con `evidencia_generador.md`, y
  contadores de capturas con `diagramas/salida_n2.txt` y `salida_n3.txt`.

## Correcciones

| Hallazgo | Corrección en el informe |
|---|---|
| Nota sobre compactación y ubicación de archivos en una leyenda | Eliminada; la leyenda describe el flujo del receptor |
| Instrucciones para preparar y compilar el PDF dentro del informe | Conservadas únicamente en el README; la sección de reproducción trata los experimentos |
| Marcador «Completar por el equipo» | Reemplazado por la declaración del uso de Codex observado en estas tareas |
| Promesa de que todas las tablas incluyen un comando que las genera | Sustituida por la procedencia real de resultados simulados y evidencia de placa |
| Banda 100–3000 Hz presentada como rechazo automático de 60 Hz | Aclarada como banda de interés; su definición no constituye un filtro |
| Pico 0.8 presentado como máximo físico del ADC | Identificado como valor de diseño con margen |
| Desfase del notch de P1 indicado como 2.5° | Corregido a −3.07° en 700 Hz; cálculo: −3.07221098° |
| Alias de 7 kHz indicado como aproximadamente −74 dB | Ensayo reproducido: −79.5803 dB; tabla: −79.6 dB |
| Imagen DAC indicada como aproximadamente −42 dB | Ensayo reproducido: −42.6571 dB; tabla: −42.7 dB |
| Atenuación del notch «numéricamente ilimitada» | Descrita como superior a 200 dB y dominada por la precisión numérica |
| «Error real» de detección en una simulación que usa frecuencia exacta | Separada la hipótesis de error de detección de la frecuencia usada en la comparación |
| 922 190 baudios presentados como medición sin evidencia localizada | Retirado el valor; se conserva la configuración comprobable de 921 600 baudios |
| Carga pequeña en ESP32 y exclusividad del nodo 3 para ruido superpuesto | Sustituidas por la comparación observada y la necesidad de medir tiempo y memoria en placa |
| Cero errores junto a un error de reinicio sin clasificación en la tabla | Añadida la fila de errores de transición, separados del veredicto |
| Comparación directa entre espuria y ruido de cuantización sin condiciones | Retirada; se conserva la espuria máxima de la evidencia de placa |

## Valores contrastados

- Sallen-Key a 3 kHz: −1.77132 dB; producto con ZOH: −3.88264 dB.
- FIR de banda protegida: rechazo 46.1066 dB (100–1200 Hz) y 45.2625 dB
  (100–3000 Hz), desde el borde superior más la transición configurada.
- Notch de P1: radio 0.90484679; con error de frecuencia de 3.90625 Hz,
  ganancia −30.2548 dB; con error de 1.5625 Hz, −38.1997 dB.
- Barrido notch: radios 0.957671, 0.852375 y 0.607387 para Q 10, 2.75 y 1;
  ganancias en 300 y 700 Hz coincidentes con el redondeo de la tabla.
- Capturas: N3, 1855 paquetes, cero errores del veredicto, cero pérdidas y una
  transición; N2, 1875 paquetes y cero errores/pérdidas.

## Límites de esta revisión

La revisión comprueba texto, coherencia con el código y evidencia disponible.
No reproduce mediciones físicas ni sustituye una revisión académica externa.
Las referencias bibliográficas y las especificaciones del fabricante no se
revalidaron íntegramente contra sus publicaciones originales en esta revisión.
El equipo debe confirmar nombres, carnés y si hubo herramientas de IA
adicionales a las descritas. No se declara verificado lo que no se comprobó.
