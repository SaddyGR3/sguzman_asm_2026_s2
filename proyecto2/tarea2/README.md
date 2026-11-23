# Tarea 2 — Modelado de sistemas

| Ruta | Contenido |
| --- | --- |
| [documentos/Tareas_ASM_Tarea2_v5.pdf](documentos/Tareas_ASM_Tarea2_v5.pdf) | Enunciado original de la tarea. |
| [documentos/Distribucion_Tarea2_ASM.md](documentos/Distribucion_Tarea2_ASM.md) | Reparto propuesto por integrante. |
| [herramientas/README.md](herramientas/README.md) | Captura CSV y calibración del SG90 con flechas en la terminal. |
| [analisis/README.md](analisis/README.md) | Script anterior con identificadores fijos de las corridas históricas. |
| [matlab/README.md](matlab/README.md) | Análisis de los CSV reales desde una libre y una frenada; incluye los ejemplos simulados del compañero por separado. |
| [documentos/tareaASM.md](documentos/tareaASM.md) | Borrador de diagramas recibido. |
| [informe/ASMTarea2.tex](informe/ASMTarea2.tex) | Fuente del informe; figuras y fotografías en [informe/imgs/](informe/imgs/). |
| [informe/ASMTarea2.pdf](informe/ASMTarea2.pdf) | PDF para subir a TEC-Digital: respuestas, fotos, enlaces de video y listado del firmware real. |
| [entrega/Tarea2_Modelado_de_Sistemas.zip](entrega/Tarea2_Modelado_de_Sistemas.zip) | Copia comprimida con el PDF; el enunciado pide subir el PDF, no el ZIP. |
| [informe/README.md](informe/README.md) | Recursos y compilación. |

El informe conserva el diagrama funcional y una curva teórica con parámetros hipotéticos; el esquema eléctrico preliminar se excluyó porque no muestra el cableado real. El `.tex` incluye las mediciones de las corridas 1 y 2, las gráficas de MATLAB, cuatro fotografías del montaje y enlaces a los dos videos.

El ejemplo ideal del compañero supone alimentación constante del motor y un equilibrio final. Para las capturas reales donde se apaga la fuente y el disco termina en cero, usar [ejecutar_analisis.m](matlab/ejecutar_analisis.m): detecta los pares de CSV, compara las corridas y calcula un modelo local si los datos lo permiten. `impulse(G)` ya se ejecutó en MATLAB; los videos de la [planta completa](https://youtu.be/hc-JIA8kH4Y) y [caracterización](https://youtu.be/BWD1uK7m35k) están enlazados en el informe.
