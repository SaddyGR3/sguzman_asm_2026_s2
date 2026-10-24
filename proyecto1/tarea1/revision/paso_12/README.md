# Paso 12 — cierre de la entrega

Fecha local: 14 de octubre de 2026 (Costa Rica).

Se incorporaron exactamente los nombres y carnés proporcionados:

- Saddy Guzman Rojas — 2023088184
- David García Cruz — 2024115575
- Válerin Calderón Bran — 2020033313
- Luis Castro Montenegro — 2013083843

Se eliminó el campo de grupo de la portada. La carpeta es `entrega/tarea1/` y el archivo para cargar es `entrega/tarea1.zip`, sin identificador de grupo, conforme a la indicación del usuario. Las referencias de rutas y las instrucciones de reconstrucción se actualizaron para este nombre.

## Verificación final

El informe se compiló con latexmk/PDFLaTeX local y conserva 29 páginas, sin desbordamientos ni referencias indefinidas. Se extrajo el texto de portada para verificar los cuatro nombres/carnés y ausencia del campo de grupo; se inspeccionaron visualmente portada y página de cierre modificadas. El compilador integrado no soporta los recursos adicionales de este proyecto, por lo que se conserva el flujo documentado de VS Code/latexmk.

El notebook final se volvió a ejecutar en una copia aislada con un kernel nuevo, eliminando señales y resultados antes de comenzar. Incluye los nombres finales y las rutas nuevas. Sus ocho scripts temporales, cuatro pruebas espectrales y nueve de comparación comprueban la integración. Se conserva el benchmark original del informe y las nuevas mediciones se guardan aparte.

`verificacion.json` registra las comprobaciones, hashes del PDF, notebook y ZIP, y la calidad frente al informe. El ZIP se verifica mediante CRC y lectura/hash de cada entrada. Contiene un manifiesto SHA-256 para los archivos del paquete.

## Versión en Git

El cierre se registra mediante un commit en `integracion-tarea1` y la etiqueta anotada `tarea1_prototipo`. Se conserva el historial de los aportes anteriores. Los libros y materiales de consulta de `Contexto/` no forman parte del paquete ejecutable ni del commit de entrega. El estado local/remoto de la etiqueta se comprueba después de publicar.

La validación es técnica y de integridad; cada autor conserva la responsabilidad de revisar y poder explicar su aporte. La carga del ZIP en TEC-Digital corresponde al usuario; no se realizó desde esta sesión.
