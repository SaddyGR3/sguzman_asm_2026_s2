# Informe de la Tarea 2

Fuente principal: [ASMTarea2.tex](ASMTarea2.tex). El [PDF compilado](ASMTarea2.pdf) tiene ocho páginas. Las tres figuras que referencia están en esta misma carpeta:

| Figura | Archivo | Procedencia |
| --- | --- | --- |
| Arquitectura funcional | [diagrama_sistema.jpeg](diagrama_sistema.jpeg) | Imagen de WhatsApp del 18 de noviembre, 11:31:06 p. m. |
| Conexión eléctrica general | [diagrama_electrico.jpeg](diagrama_electrico.jpeg) | Imagen de WhatsApp del 18 de noviembre, 11:31:11 p. m. |
| Escalón de frenado | [simulacion_escalon_frenado.png](simulacion_escalon_frenado.png) | Generada por [generar_figura_escalon.py](generar_figura_escalon.py) usando los parámetros hipotéticos escritos en el informe. |

Para regenerar la curva se necesita Python con PySide6: `python generar_figura_escalon.py`. Para compilar desde esta carpeta, con una instalación de LaTeX que incluya `extarticle` y los paquetes declarados en el preámbulo:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error ASMTarea2.tex
```

El PDF actual se compiló con Tectonic 0.17.0. El `.tex` no usa rutas externas y ya tiene sus tres imágenes. Las secciones de resultados experimentales contienen marcadores pendientes; no deben presentarse como mediciones reales.
