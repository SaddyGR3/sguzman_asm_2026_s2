# Tarea 1 — caracterización espectral y reducción de ruido

Repositorio: [sguzman_asm_2026_s2](https://github.com/SaddyGR3/sguzman_asm_2026_s2).

Autores:

- Saddy Guzman Rojas — 2023088184
- David García Cruz — 2024115575
- Válerin Calderón Bran — 2020033313
- Luis Castro Montenegro — 2013083843

Versión de entrega: etiqueta `tarea1_prototipo`, rama `integracion-tarea1`.
[Consultar la versión etiquetada](https://github.com/SaddyGR3/sguzman_asm_2026_s2/tree/tarea1_prototipo).
La carpeta y el ZIP se denominan `tarea1`, sin número de grupo.

## Contenido

```text
tarea1/
  informe.pdf
  notebook.ipynb
  src/
    generar_senales.py
    analizar_2_1.py
    filtros_temporales.py
    filtrado_espectral.py
    metricas.py
    evaluar_comparacion.py
    graficar_comparacion.py
  pruebas/
    caso_1/                 NPZ, WAV y metadatos
    caso_2/
    caso_3/
    filtros_temporales/     ocho scripts con aserciones
    filtrado_espectral/    cuatro pruebas unittest
    comparacion/           nueve pruebas unittest
  resultados/
    metricas.csv           mediciones originales citadas en el PDF
    resultados_2_5.json     registro original de esas mediciones
    figuras/               figuras originales de comparación
    regenerados/           resultados de la ejecución completa del notebook
  metadatos/
    configuraciones.json
    protocolo.json
    huellas_muestras.json
    trazabilidad_codigo.json
  documentacion/
  requirements.txt
  requirements-lock.txt
  MANIFEST.sha256
```

## Ejecución desde cero en VS Code

Se verificó con Python 3.12.14. Crear un entorno con Python 3.12 e instalar:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

En Windows, usar `py -3.12 -m venv .venv` y `.venv\Scripts\python -m pip install -r requirements.txt`.

Abrir `notebook.ipynb`, seleccionar ese entorno como kernel y ejecutar todas las celdas, desde la primera, con un kernel nuevo. El notebook ya incluye salidas de una ejecución comprobada. También se incluye `requirements-lock.txt` con las versiones transitivas usadas durante esa comprobación.

La ejecución regenera los tres casos y las cuatro gráficas de cada uno, demostraciones de fundamentos, coeficientes/respuesta del FIR, resultados espectrales con ablación, métricas comunes, benchmark y seis figuras comparativas. Guarda las nuevas mediciones en `resultados/regenerados/`, sin sobrescribir las cifras del PDF. No necesita archivos de `Contexto/` ni las carpetas originales del repositorio, ni descarga datos durante el cálculo. Las dependencias se instalan previamente.

La verificación se ejecutó en una carpeta temporal, sin señales NPZ/WAV, metadatos por caso, configuraciones agregadas ni resultados previamente calculados. Las muestras regeneradas coincidieron con las huellas congeladas. Pasaron los ocho scripts temporales, cuatro pruebas espectrales y nueve pruebas de comparación. La ejecución de las siete celdas Python terminó sin errores.

## Interpretar resultados

- Capturas: 8192 muestras, 8 kHz, 1.024 s; bloque FFT 1024 y salto espectral 512.
- Comparación principal: 8174 muestras comunes. FIR desplazado 18 muestras; espectral y entrada sin desplazar.
- SNR/MSE, energía útil condicional y atenuación usan la misma referencia y protocolo. El espectral aprende sus ganancias solo desde la mezcla; después se fija ese operador para evaluar las componentes.
- Las cifras del apartado 2.4 y su ablación usan la captura completa y se distinguen de la comparación principal.
- Los tiempos y picos de memoria de una ejecución nueva pueden variar; no se exige reproducir el benchmark del informe. Las métricas de calidad reproducen sus resultados con tolerancia numérica.
- El espectral actual estima piso/DC sobre la captura completa: es una referencia fuera de línea. UART, memoria, parámetros causales y plazos ESP32 son propuestas aún sin pruebas en placa.

`metadatos/huellas_muestras.json` identifica el contenido numérico congelado. El notebook comprueba esas huellas antes de actualizar los hashes de los NPZ regenerados en el protocolo: no permite sustituir silenciosamente las señales por otras. La reproducción exacta se validó con las versiones incluidas; otros entornos pueden producir diferencias de punto flotante y la comprobación las señalará.

Los módulos FIR, FFT/IFFT y métricas se copian sin cambios de algoritmo. Los evaluadores/gráficos y pruebas adaptan rutas a este paquete. `trazabilidad_codigo.json` registra orígenes y hashes; la generación reutiliza las celdas de 2.2, con rutas portables y exportación agregada de metadatos. La documentación conserva la explicación de las decisiones; referencias a registros externos señalan rutas del repositorio, no dependencias de ejecución.

El JSON original de `resultados/` conserva la procedencia del benchmark del PDF y sus rutas/hashes del repositorio. Para comprobar esta entrega portable con los módulos adaptados, usar el JSON recién generado en `resultados/regenerados/`.

## Uso de IA y contribuciones

Se utilizó asistencia de IA para integrar aportes, adaptar rutas, preparar notebook/paquete y verificar la regeneración. Se suministraron enunciados, plan, libros, módulos y datos. La ejecución aislada, pruebas y comparación de calidad verifican la integración; no sustituyen la revisión de los autores ni la validación futura del hardware. El informe identifica responsabilidades por integrante; los nombres y carnés se encuentran en la portada.

`MANIFEST.sha256` permite comprobar la integridad de los archivos incluidos con `sha256sum -c MANIFEST.sha256` en Linux. Si se vuelve a ejecutar el notebook o modificar archivos, regenerar el manifiesto y el ZIP para la versión que se entregue.
