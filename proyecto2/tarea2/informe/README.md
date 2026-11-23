# Informe de la Tarea 2

Fuente principal: [ASMTarea2.tex](ASMTarea2.tex). El [PDF compilado](ASMTarea2.pdf) tiene ocho páginas y corresponde al `.tex` actualizado. Las dos figuras que referencia están en esta misma carpeta:

| Figura | Archivo | Procedencia |
| --- | --- | --- |
| Arquitectura funcional | [diagrama_sistema.jpeg](diagrama_sistema.jpeg) | Imagen de WhatsApp del 18 de noviembre, 11:31:06 p. m. |
| Escalón de frenado | [simulacion_escalon_frenado.png](simulacion_escalon_frenado.png) | Generada por [generar_figura_escalon.py](generar_figura_escalon.py) usando los parámetros hipotéticos escritos en el informe. |

El archivo [diagrama_electrico.jpeg](diagrama_electrico.jpeg) se conserva como esquema preliminar, pero no se incluye en el informe actualizado: muestra un driver y una fuente independiente para el servo que no se utilizaron en los ensayos.

Para regenerar la curva se necesita Python con PySide6: `python generar_figura_escalon.py`. Para compilar desde esta carpeta, con una instalación de LaTeX que incluya `extarticle` y los paquetes declarados en el preámbulo:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error ASMTarea2.tex
```

El PDF se recompiló el 22 de noviembre de 2026 con Tectonic 0.16.9. Documenta el montaje real y las cinco corridas comparables. Las figuras de MATLAB, fotografías y enlace al video aún no se han añadido; habrá que regenerarlo cuando se incorporen.

## Revisión del contenido frente al enunciado

Los puntos obligatorios 1, 4 y 5 tienen desarrollo teórico. El 2 distingue ahora la propuesta de control a 100 Hz del registro real cada 100 ms y de las marcas del KY-033. El 3 incluye un ejemplo de lectura del sensor y orden al servo sin `delay`, pero las ganancias PID siguen sin ajustar y el PID no se ejecutó en el banco. Se retiraron las notas editoriales sueltas.

Los puntos extra 6 y 7 están descritos con el montaje real: motor DC miniatura con la fuente indicando 1 V, disco MDF de 12 cm por 3 mm, KY-033 y SG90 con una esponja que toca la cara superior del disco. Se conservan tres corridas libres y dos frenadas comparables en la carpeta local `../capturas/`; las frenadas bajan de unas 1300 a menos de 500 RPM en ~1,17 s frente a ~11,5 s de giro libre. Para analizarlas en MATLAB usar [ejecutar_analisis.m](../matlab/ejecutar_analisis.m); los ejemplos ideales del compañero siguen separados. Faltan su ejecución en MATLAB y las evidencias visuales.
