# Paso 5: generación y revisión de resultados

Fecha local: 12 de octubre de 2026. Estado: completado.

Se añadieron seis figuras, con versiones PNG de 300 dpi y SVG, y cuatro
tablas de presentación. Los datos proceden del evaluador del paso 4. No se
repitieron sus filtros ni mediciones de rendimiento.

## Verificación numérica

El generador `seccion_2_5/src/graficar_comparacion.py` comprueba antes de
producir figuras:

- Las nueve filas y todas las columnas del CSV coinciden con el JSON.
- Los hashes del protocolo, el código evaluado y los casos oficiales coinciden.
- Las fuentes exportadas coinciden exactamente con los NPZ oficiales.
- Cada curva principal usa las mismas 8174 muestras de referencia y su
  compensación de retardo declarada.
- MSE, SNR, ΔSNR, energía útil/total, atenuación y ganancias por tono
  coinciden con las muestras exportadas, con diferencia menor que `1e-10`.
- Las métricas directas conservadas sobre 8192 muestras también coinciden.
- La componente útil más el ruido residual reconstruye la salida con error
  máximo menor que `1e-12`.
- Las estadísticas temporales corresponden a las 30 repeticiones guardadas.

Las diferencias y los hashes de las figuras se registran en
[`revision_figuras.json`](../../seccion_2_5/resultados/revision_figuras.json).
No se alteraron las métricas del paso 4.

## Revisión visual

Se inspeccionaron las seis figuras PNG. Se verificaron títulos, leyendas,
ejes, unidades, límites de presentación y correspondencia con las tablas.
Se ajustó la posición de las etiquetas de mediana en la figura de tiempos
para evitar solapamiento con las marcas del percentil 95; luego se revisó
esa figura nuevamente. Las otras cinco versiones PNG no cambiaron, lo que
se confirmó mediante sus hashes. Las versiones SVG proceden de las mismas
figuras Matplotlib.

| Figura | Contenido revisado |
|---|---|
| `caso_1_comparacion` | Tiempo 100–120 ms, espectro y error de la interferencia tonal separada |
| `caso_2_comparacion` | Tiempo, espectro y error del ruido blanco |
| `caso_3_comparacion` | Tiempo, espectro y error de la superposición parcial |
| `resumen_calidad` | SNR, MSE logarítmico, ΔSNR y atenuación del ruido total |
| `energia_y_tonos` | Conservación útil con eje ampliado y ganancias de 300/700/1100 Hz |
| `recursos_pc` | Tiempo amortizado y pico adicional trazado, con límites de interpretación |

Los espectros son periodogramas Hann unilaterales en amplitud²/Hz. El piso
de −160 dB se usa solo para visualizar; el eje mostrado llega a −140 dB.
La curva de error incluye distorsión y ruido residual. Las señales temporales
ilustran un tramo interior fijo; no ocultan que las métricas incluyen los
extremos del intervalo principal. Algunas curvas se superponen porque sus
valores son prácticamente iguales, particularmente entrada y FIR en el caso 3.

## Productos y observaciones

Las tablas completas y enlaces a figuras están en
[`resumen_2_5.md`](../../seccion_2_5/resultados/resumen_2_5.md).

- El FIR alcanza mayor SNR en el caso 1; el espectral en los casos 2 y 3.
- La mejora del FIR en el caso 3 es solo 0.061 dB, frente a 11.667 dB del
  espectral, con el mismo intervalo de referencia.
- La energía total de una salida puede superar 100 % por ruido residual;
  no se debe confundir con la conservación de la componente útil.
- El tiempo de PC compara implementaciones Python/NumPy distintas y no
  valida desempeño, latencia o uso de RAM en ESP32.

El análisis de decisiones y condiciones de fallo corresponde al paso 6.
La inclusión de las figuras en LaTeX corresponde a la integración del informe.

Para regenerar desde la raíz:

```bash
.venv/bin/python seccion_2_5/src/graficar_comparacion.py
```

El comando vuelve a marcar la inspección visual como pendiente. Si se
regenera después de cambiar datos, código o estilo, deben revisarse las
figuras nuevas antes de declarar completa su revisión.

Se utilizó asistencia de IA para crear el generador, organizar las tablas,
inspeccionar las figuras y documentar estas comprobaciones.
