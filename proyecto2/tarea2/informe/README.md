# Informe de la Tarea 2

Fuente principal: [ASMTarea2.tex](ASMTarea2.tex). El informe documenta los pares reales `datos_1` (libre) y `datos_2` (frenado) usados en el video. [ASMTarea2.pdf](ASMTarea2.pdf) es la versión compilada. El diagrama de bloques y la simulación teórica aparecen en sus secciones; las fotografías y gráficas experimentales están al final, en anexos de una columna, con referencias desde el texto principal.

El apartado de anexos incorpora directamente el programa real [main.cpp](../../firmware/freno%20abs/src/main.cpp) del ESP32. Al recompilar el `.tex` desde esta carpeta, el archivo debe permanecer en esa ruta relativa. Cada video se enlaza una sola vez, junto al punto extra correspondiente.

Las figuras y fotografías están reunidas en [imgs/](imgs/). Los nombres de las cuatro fotos describen lo que muestra cada una; se conservaron los archivos originales sin editar.

| Figura | Archivo | Procedencia |
| --- | --- | --- |
| Arquitectura funcional | [diagrama_sistema.jpeg](imgs/diagrama_sistema.jpeg) | Diagrama de la propuesta. |
| Escalón de frenado | [simulacion_escalon_frenado.png](imgs/simulacion_escalon_frenado.png) | Generada por [generar_figura_escalon.py](generar_figura_escalon.py) usando los parámetros hipotéticos escritos en el informe. |
| Comparación real | [comparacion_real.png](imgs/comparacion_real.png) | MATLAB, corrida libre 1 frente a frenada 2. |
| Escalón real | [respuesta_escalon_real.png](imgs/respuesta_escalon_real.png) | MATLAB, comando de 90° a 40° y RPM medidas. |
| Ajuste local | [ajuste_local.png](imgs/ajuste_local.png) | MATLAB, modelo ajustado antes de 500 RPM. |
| Impulso del modelo | [impulse_matlab.png](imgs/impulse_matlab.png) | Salida de `impulse(G)` en MATLAB; no es una prueba de impulso físico. |
| Motor y fuente | [foto_motor_fuente.jpeg](imgs/foto_motor_fuente.jpeg) | Vista de la conexión del motor con la fuente externa. |
| Disco frenado | [foto_disco_frenado.jpeg](imgs/foto_disco_frenado.jpeg) | Disco y zapata de esponja en posición de frenado. |
| Disco girando | [foto_disco_girando.jpeg](imgs/foto_disco_girando.jpeg) | Disco en movimiento. |
| Montaje general | [foto_montaje_general.jpeg](imgs/foto_montaje_general.jpeg) | Vista frontal del conjunto. |

El archivo [diagrama_electrico.jpeg](imgs/diagrama_electrico.jpeg) se conserva como esquema preliminar, pero no se incluye en el informe actualizado: muestra un driver y una fuente independiente para el servo que no se utilizaron en los ensayos.

Para regenerar la curva se necesita Python con PySide6: `python generar_figura_escalon.py`. Para compilar desde esta carpeta, con una instalación de LaTeX que incluya `extarticle` y los paquetes declarados en el preámbulo:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error ASMTarea2.tex
```

Videos entregados por el equipo: [planta completa](https://youtu.be/hc-JIA8kH4Y) y [caracterización con MATLAB](https://youtu.be/BWD1uK7m35k). Las cuatro fotografías del montaje están incorporadas al informe.

## Revisión del contenido frente al enunciado

Los puntos obligatorios 1, 4 y 5 tienen desarrollo teórico. El 2 distingue ahora la propuesta de control a 100 Hz del registro real cada 100 ms y de las marcas del KY-033. El 3 incluye un ejemplo de lectura del sensor y orden al servo sin `delay`, pero las ganancias PID siguen sin ajustar y el PID no se ejecutó en el banco. Se retiraron las notas editoriales sueltas.

Los puntos extra 6 y 7 están descritos con el montaje real: motor DC miniatura con la fuente indicando 1 V, disco MDF de 12 cm por 3 mm, KY-033 y SG90 con una esponja que toca la cara superior del disco. Las corridas del video bajan de unas 1300 a menos de 500 RPM en 11,300 s (libre 1) y 1,317 s (frenada 2). Para reproducirlas en MATLAB, usar [ejecutar_analisis.m](../matlab/ejecutar_analisis.m) con `opciones.ids = {'1','2'}`. `impulse(G)` se ejecutó con Control System Toolbox. Los CSV originales se conservaron localmente fuera de Git; las cuatro gráficas incluidas en este informe son copias de la ejecución.
