# Paso 9: arquitectura y comunicación

La [propuesta completa](../../seccion_2_5/docs/2_5_arquitectura_comunicacion.md)
define tres placas ESP32, funciones, enlaces, referencia, protocolo,
presupuesto de tasa, sincronización, pérdidas, latencia y memoria.

El diagrama está en
[PNG](../../seccion_2_5/docs/figuras/arquitectura_nodos.png),
[SVG](../../seccion_2_5/docs/figuras/arquitectura_nodos.svg) y
[fuente Graphviz](../../seccion_2_5/docs/figuras/arquitectura_nodos.dot).
Se inspeccionó la versión final: etiquetas legibles, tres rutas de datos,
dos salidas y la interfaz. La distribución vertical reemplazó un primer
diseño demasiado ancho para integrarlo cómodamente en el informe.

## Cálculos y trama de ejemplo

Desde la raíz del repositorio:

```bash
.venv/bin/python revision/paso_9/calcular_comunicacion.py
```

El script lee los presupuestos previos, registra sus hashes y genera
[presupuesto_comunicacion.json](presupuesto_comunicacion.json) y
[trama_ejemplo.bin](trama_ejemplo.bin). La trama INPUT_REF contiene
las primeras 512 muestras de x y s del caso 1, convertidas a float32
e intercaladas. Se registra su SHA-256 y el del archivo NPZ fuente.
No se modifican las señales ni se vuelve a ejecutar el benchmark.

Se comprobaron cabecera de 32 bytes, ida/vuelta del payload completo,
CRC de `123456789`, vector COBS conocido, límites 253/254/255 y
longitudes de paquetes grandes con ceros/no ceros. La inversión de un
bit del paquete decodificado produjo discrepancia CRC, como se esperaba.
Estas pruebas de representación no equivalen a recepción UART ni
validación del parser en firmware.

## Resultados de diseño

- Enlace más exigente: N1→N3 con referencia y diagnóstico, 4252 bytes
  máximos por avance; 664375 baud sostenidos en UART 8N1.
- Con reserva de 10 mensajes de control por segundo y por sentido:
  671375 baud, ocupación de 72.85 % a 921600.
- Tres enlaces independientes y simultáneos; no se suman las tasas
  como si compartieran un bus único.
- Reproducción programada: 256 ms. Disponibilidad modelada de salida
  espectral: 223.90 ms; de FIR alineado en N3: 226.07 ms.
- Totales provisionales: N1 71.16 KiB, N2 45.56 KiB y N3 134.16 KiB.
  Objetivos de reserva: 96, 64 y 160 KiB respectivamente.

Las reservas auxiliares de N1 y N2, de 32768 bytes cada una, contemplan
12288 bytes de buffers UART, 8192 de pilas, 8192 de DMA, 2048 de
colas y 2048 de otros datos. En N1, los UART contemplan RX de 2048
por enlace y TX de 4096 por enlace; en N2, RX de 4096 para datos y
2048 para control, y TX de 4096 para salida y 2048 para control.
La reserva de N3 se detalla en la propuesta y en el JSON.

La evaluación condicional con referencia requiere estado y trabajo
extra: en N3 se reservan historial DC y OLA útiles, y FIR de referencia.
Por ello los 79.61 KiB del paso 8, correspondientes al DSP aislado,
no representan el consumo del nodo completo. Los archivos previos
se conservan como etapas del diseño.

## Alcance y fuentes

Se revisaron funciones de nodos y restricciones del proyecto local,
documentación oficial de UART, el artículo original COBS y documentación
zlib; los enlaces están en la propuesta. Consulta: 12 de octubre de 2026.

No se conectaron placas, instalaron drivers ni se implementó firmware.
Los plazos incluyen objetivos de procesamiento y supuestos de cola,
no tiempos medidos. Se especifican pruebas de hardware necesarias,
incluyendo enlaces simultáneos, fragmentación/corrupción, deriva de
relojes y cálculo de métricas con referencia válida. Sin s, la interfaz
no mostrará métricas que requieren esa referencia.

La siguiente actividad es integrar el contenido en LaTeX en `informe/`
durante el paso 10, conforme al flujo acordado.
