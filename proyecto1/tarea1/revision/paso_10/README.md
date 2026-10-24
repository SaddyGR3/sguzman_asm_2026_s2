# Paso 10 — integración del informe

Se creó `informe/informe.tex`, con portada editable, índice, secciones 2.1–2.5, conclusiones, referencias, declaración de IA y apéndice de los 37 coeficientes FIR mediante simetría. No se modificaron los aportes originales ni los resultados medidos.

`informe/preparar_recursos.py` copia 23 figuras existentes y genera dos figuras del FIR definitivo. Genera las cuatro tablas directamente desde `seccion_2_5/resultados/metricas.csv`, sin volver a medir tiempos. Los recursos están dentro de `informe/` para que la compilación sea portable.

Se conserva el protocolo común de 8174 muestras, alineación FIR de 18 muestras, energía útil condicional y distinción entre memoria lógica, pico trazado y presupuestos embebidos. La ablación espectral utiliza captura completa y se identifica como experimento diferente. La arquitectura usa los presupuestos refinados del paso 9: 256 ms y memoria completa por nodo.

La compilación integrada de Codex no admite las imágenes/archivos adicionales de este proyecto. Se comprobó la compilación de la carpeta completa con el LaTeX instalado, mediante `latexmk -pdf -interaction=nonstopmode -halt-on-error informe.tex`, sin instalar herramientas. Es el mismo comando documentado para VS Code. La revisión visual se realizó con Poppler; el registro JSON identifica el PDF y fuentes revisados.

Antes de entregar deben completarse grupo y nombres al comienzo del archivo. El remoto actual proporciona el enlace del repositorio. La etiqueta final, notebook unificado y ZIP no se generan en este paso.
