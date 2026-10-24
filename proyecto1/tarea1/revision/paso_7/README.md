# Paso 7: propuesta de procesamiento embebido

El diseño está en
[2_5_diseno_esp32.md](../../seccion_2_5/docs/2_5_diseno_esp32.md), con una
síntesis en [la sección 2.5](../../seccion_2_5/docs/2_5_comparacion_propuesta.md).

Se proponen 8000 Hz, FFT de 1024 muestras, avance de 512, sqrt-Hann
con 50 % de solapamiento, procesamiento float32 y FIR de orden 36
con estado continuo. Se define una estimación espectral causal de ocho
tramas recientes, tratamiento de DC y extremos, calentamiento,
presupuesto de memoria y plazos de cálculo/reproducción.

## Cálculos reproducibles

Desde la raíz del repositorio:

```bash
.venv/bin/python revision/paso_7/calcular_presupuesto.py
```

El script lee muestreo, FFT, avance y orden FIR del protocolo existente.
No modifica la configuración evaluada. Registra su SHA-256 y deriva
resolución, tiempos, conteos algorítmicos y memoria propuesta en
[presupuesto_esp32.json](presupuesto_esp32.json).

- DSP espectral y buffers de aplicación: 67245 bytes.
- Con una provisión auxiliar de 16384 bytes: 83629 bytes, 81.67 KiB.
- Objetivo de reserva de 96 KiB: margen provisional de 14675 bytes.
- FIR especializado: 292 bytes para coeficientes/estado float32; 9508
  bytes incluyendo buffers de aplicación y reserva de control.
- Avance de 64 ms; objetivo de DSP de 48 ms.
- Retardo espectral programado de reproducción: 192 ms, antes de enlace
  y otras colas; retardo de grupo FIR de 2.25 ms.

Se verificaron las sumas de bytes, la consistencia con el protocolo,
fórmulas de tiempos, tamaño de descriptores del ejemplo I2S y enlaces
locales. No se ejecutó un nuevo benchmark ni se cambiaron resultados
o figuras de la comparación.

## Fuentes y alcance

Se revisaron el apartado 2.5 de la tarea, las funciones de nodos y
restricciones del proyecto, las decisiones y pruebas numéricas de 2.3,
y las operaciones no causales de 2.4. Las afirmaciones sobre el chip,
FPU y DMA se contrastaron el 12 de octubre de 2026 con la ficha y guías
oficiales de Espressif, enlazadas en el diseño.

La placa exacta y los convertidores aún no están especificados. Las
bibliotecas se analizarán en el paso 8 y la arquitectura/enlaces en el
paso 9. La memoria es una provisión de diseño con reservas, no una
medición ni una garantía de cabida en la RAM libre. La causalidad,
precisión float32 completa, calidad, plazos y latencia deben verificarse
al implementar; se proponen criterios concretos para esas pruebas.
