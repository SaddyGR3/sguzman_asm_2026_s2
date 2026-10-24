# Paso 8: selección de bibliotecas

La [documentación de bibliotecas](../../seccion_2_5/docs/2_5_bibliotecas_esp32.md)
compara ESP-DSP 1.8.2 y KISS FFT 131.1.0, identifica licencias y formatos,
y propone ESP-DSP para FFT y FIR float32 en ESP32 clásico.

Se revisaron cabeceras, implementación ANSI, FIR optimizado para ESP32,
inicialización, tablas de bit reversal, manifiesto, Kconfig y licencia.
La revisión se fijó al tag v1.8.2 y commit
`a53a0756833c045311ea1d79a2badf495cdfde4c`, obtenido de la API oficial
de GitHub. Se consultaron fuentes primarias el 12 de octubre de 2026.

## Evidencia y reproducción

[seleccion_bibliotecas.json](seleccion_bibliotecas.json) registra URL y
SHA-256 de cada archivo oficial leído, versión, configuración y
derivaciones de memoria. También vincula el presupuesto inicial mediante
su SHA-256.

Para repetir las comprobaciones, descargar los archivos de la lista
`fuentes` del JSON a una carpeta, usando como nombre local el campo
`archivo`. Desde la raíz del repositorio ejecutar:

```bash
.venv/bin/python revision/paso_8/verificar_biblioteca.py --fuentes /ruta/a/las/copias
```

La ejecución realizada usó `/tmp/esp-dsp-p8`. Las fuentes externas no
se incorporaron al código del proyecto ni se instalaron como dependencia.
El verificador comprueba el conteo de índices de la tabla de 1024,
las fórmulas de reserva, el contrato de delay FIR, la configuración de
1024 y el requisito de IDF. Registra hashes; una revisión futura debe
compararlos con este registro para detectar cambios de fuente.

## Resultado

- FFT: datos complejos 8192 bytes; twiddles 4096 y copia de bit reversal
  1984, total de tablas activas 6080 bytes.
- Espectral: subtotal 65133 bytes; con reserva auxiliar, 81517 bytes,
  79.61 KiB. Margen respecto del objetivo de 96 KiB: 16787 bytes.
- FIR de biblioteca: coeficientes 148 bytes y delay 164; estructura
  estimada de 40 bytes con ABI de 32 bits. Núcleo estimado: 352 bytes;
  subtotal con buffers y control: 9568 bytes.

Se define una IFFT por conjugación y normalización 1/N, el reordenamiento
de bins, conservación de simetría, inicialización única y contrato FIR.
Se documenta el orden invertido de coeficientes y la diferencia de
restricciones entre ESP32 clásico y ESP32-S3.

El presupuesto del paso 7 se conserva como versión inicial; el del
paso 8 refina el payload de tablas y estado con una biblioteca concreta.
Las reservas siguen siendo provisionales. No se ejecutaron las rutinas
ESP-DSP, no se midieron plazos en ESP32 ni se confirmó `sizeof` con
su compilador. La precisión y compatibilidad efectiva quedan sujetas
a las pruebas de implementación indicadas en la documentación.

La siguiente actividad es la arquitectura de tres nodos y el presupuesto
de comunicación del paso 9.
