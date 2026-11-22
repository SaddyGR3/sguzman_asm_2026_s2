# Tarea 2 — Modelado de sistemas

| Ruta | Contenido |
| --- | --- |
| [documentos/Tareas_ASM_Tarea2_v5.pdf](documentos/Tareas_ASM_Tarea2_v5.pdf) | Enunciado original de la tarea. |
| [documentos/Distribucion_Tarea2_ASM.md](documentos/Distribucion_Tarea2_ASM.md) | Reparto propuesto por integrante. |
| [PLAN_PUNTOS_EXTRA.md](PLAN_PUNTOS_EXTRA.md) | Estado real, protocolo de medición y datos necesarios para MATLAB y los puntos extra 6 y 7. |
| [herramientas/README.md](herramientas/README.md) | Captura CSV y calibración del SG90 con flechas en la terminal. |
| [analisis/README.md](analisis/README.md) | Comparación reproducible en MATLAB con las cinco corridas reales conservadas. |
| [matlab/README.md](matlab/README.md) | Trabajo del compañero: ejemplos simulados y analizador para un ensayo con motor alimentado continuamente. |
| [documentos/tareaASM.md](documentos/tareaASM.md) | Borrador de diagramas recibido. |
| [informe/ASMTarea2.tex](informe/ASMTarea2.tex) | Fuente del informe y figuras locales. |
| [informe/README.md](informe/README.md) | Recursos y compilación. |

Las dos imágenes enviadas por WhatsApp están asignadas a figuras del informe. La curva del escalón que ya existe es teórica y usa parámetros hipotéticos. El `.tex` incluye ahora las mediciones reales en una tabla; el PDF incluido todavía debe recompilarse. Las figuras de MATLAB y la evidencia audiovisual se agregarán después.

El programa de `matlab/` llegó en el commit `02fcb3c`. Su analizador experimental supone alimentación constante del motor y un equilibrio final, por lo que no se debe aplicar sin adaptación a las capturas reales donde se apaga la fuente y el disco termina en cero. Para estas cinco corridas se preparó [analizar_capturas.m](analisis/analizar_capturas.m). Ninguno de los dos análisis sustituye la ejecución de `impulse` en MATLAB ni el video único exigido por el punto extra 7.
