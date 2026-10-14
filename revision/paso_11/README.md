# Paso 11 — notebook ejecutable y paquete portable

Se preparó `entrega/tarea1/`, con la estructura mínima del enunciado y dependencias, documentación, pruebas y manifiesto adicionales. El ZIP de revisión se encuentra junto a esa carpeta. El nombre del grupo y la portada todavía deben completarse; no se creó la etiqueta Git.

## Qué se integró

- Notebook de 15 celdas, siete Python ejecutadas en orden y ocho explicativas: fundamentos, generación/caracterización, FIR, espectral/ablación, comparación y propuesta.
- Funciones/celdas de generación de 2.2, preservando señales y semillas. Se exportan configuraciones agregadas y se corrige la leyenda de fase vacía.
- Módulos FIR, espectral y métricas copiados sin cambios de algoritmo; evaluadores, gráficos y pruebas con rutas adaptadas al paquete.
- Informe PDF actualizado para identificar el notebook ya integrado. Se recompiló con latexmk, sin desbordamientos ni referencias indefinidas; se revisó la página modificada.
- CSV/figuras del informe conservados. Las ejecuciones nuevas se escriben en `resultados/regenerados/` para no mezclar benchmarks de distinta ejecución.

## Comprobación desde cero

`verificar_notebook.py` utiliza nbclient e ipykernel con un kernel nuevo y una carpeta temporal. Eliminó todos los resultados, las tres carpetas de señales NPZ/WAV/metadatos y el archivo agregado de configuraciones antes de ejecutar. El notebook regeneró todos esos archivos y no importó módulos del repositorio original. Se compararon huellas de arreglos para verificar los casos congelados antes de actualizar hashes del contenedor NPZ.

Pasaron los ocho scripts temporales, las cuatro pruebas espectrales y las nueve pruebas de comparación. El ZIP se comprueba por CRC, lectura de cada entrada y SHA-256; su manifiesto enumera los archivos incluidos. La calidad común coincide con las mediciones del informe; tiempos y picos se conservan como nuevas mediciones. Los registros son `verificacion_notebook.json`, `ejecucion_notebook.log` y `verificacion_entrega.json`.

La prueba usa puertos locales internos de Jupyter. Fue necesario ejecutar fuera del sandbox restringido, que impide crear sockets, e instalar nbformat/nbclient/ipykernel en `.venv/`. No se instaló un kernel global; su especificación y configuración temporales se eliminan al terminar.

## Reconstruir desde la raíz

Con las dependencias de Jupyter instaladas en `.venv/`:

```bash
.venv/bin/python revision/paso_11/preparar_entrega.py
.venv/bin/python revision/paso_11/crear_notebook.py
.venv/bin/python revision/paso_11/verificar_notebook.py
.venv/bin/python revision/paso_11/cerrar_entrega.py
```

La primera orden reconstruye/adapta la carpeta; la segunda crea un notebook limpio; la tercera regenera desde cero y guarda el notebook ejecutado; la cuarta verifica calidad y cierra el ZIP. Ejecutar después de actualizar y compilar `informe/informe.tex` si cambia el PDF. Los scripts originales no se modifican.

El paso 12 corresponde a completar los datos personales, revisión cruzada, integración Git, etiqueta aprobada y cierre final de entrega.
