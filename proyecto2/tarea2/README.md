# Tarea 2 — Modelado de sistemas

| Ruta | Contenido |
| --- | --- |
| [documentos/Tareas_ASM_Tarea2_v5.pdf](documentos/Tareas_ASM_Tarea2_v5.pdf) | Enunciado original de la tarea. |
| [documentos/Distribucion_Tarea2_ASM.md](documentos/Distribucion_Tarea2_ASM.md) | Reparto propuesto por integrante. |
| [PLAN_PUNTOS_EXTRA.md](PLAN_PUNTOS_EXTRA.md) | Estado real, protocolo de medición y datos necesarios para MATLAB y los puntos extra 6 y 7. |
| [herramientas/README.md](herramientas/README.md) | Captura CSV y calibración del SG90 con flechas en la terminal. |
| [analisis/README.md](analisis/README.md) | Script anterior con los identificadores fijos de las cinco corridas. |
| [matlab/README.md](matlab/README.md) | Análisis de los CSV reales desde una libre y una frenada; incluye los ejemplos simulados del compañero por separado. |
| [documentos/tareaASM.md](documentos/tareaASM.md) | Borrador de diagramas recibido. |
| [informe/ASMTarea2.tex](informe/ASMTarea2.tex) | Fuente del informe y figuras locales. |
| [informe/README.md](informe/README.md) | Recursos y compilación. |

El informe conserva el diagrama funcional y una curva teórica con parámetros hipotéticos; el esquema eléctrico preliminar se excluyó porque no muestra el cableado real. El `.tex` y el PDF incluyen las mediciones reales en una tabla. Las figuras de MATLAB y la evidencia audiovisual se agregarán después.

El ejemplo ideal del compañero supone alimentación constante del motor y un equilibrio final. Para las capturas reales donde se apaga la fuente y el disco termina en cero, usar [ejecutar_analisis.m](matlab/ejecutar_analisis.m): detecta los pares de CSV, compara las corridas y calcula un modelo local si los datos lo permiten. La ejecución de `impulse` en MATLAB y el video único siguen pendientes.
