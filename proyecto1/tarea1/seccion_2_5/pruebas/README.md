# Verificaciones de la comparación

`test_comparacion.py` contiene nueve pruebas automáticas implementadas y
ejecutadas correctamente en el paso 4.

Desde la raíz:

```bash
.venv/bin/python -m unittest discover -s seccion_2_5/pruebas -p 'test_*.py' -v
```

Se comprueban los siguientes comportamientos:

1. Los tres casos coinciden con los hashes, metadatos y dimensiones del
   protocolo; una incompatibilidad se informa y detiene la evaluación.
2. Todos los métodos usan la misma referencia y el mismo tramo principal
   de 8174 muestras, con retardo fijo de 18 muestras únicamente para el FIR.
3. La identidad da energía útil conservada 100 %, atenuación 0 dB y ΔSNR 0 dB.
4. La salida se reconstruye como componente útil más ruido residual con
   error máximo menor que `1e-12`, congelando las ganancias de la mezcla.
5. La energía total con ruido no se usa como energía útil conservada.
6. Se mantienen los resultados directos y alineados como criterios distintos.
7. Las exportaciones distinguen datos no aplicables e infinitos, producen
   JSON válido y conservan valores numéricos sin redondeo de presentación.

Se usan casos sintéticos con resultado conocido y comprobaciones
contra las fuentes oficiales; no se fijan tiempos de PC como umbrales
de cumplimiento de tiempo real en ESP32.

Los controles incluyen Parseval para longitudes pares e impares, ganancias
tonales conocidas entre bins, rechazo de hashes o metadatos alterados,
linealidad del operador con ganancias congeladas y equivalencia FIR con
`scipy.signal.lfilter`. Una comprobación por caso confirma que el estimador
espectral solo recibe la mezcla y se ejecuta una vez durante la evaluación
de calidad. Las pruebas escriben las exportaciones en directorios temporales.
