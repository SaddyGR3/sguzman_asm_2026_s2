# Validación de métricas v2 — 6 de noviembre de 2026

Pruebas en placa realizadas por el usuario; revisión de sus reportes y análisis
de CSV por el agente. No se compiló ni cargó firmware desde el agente.
No se identificó el audio como un P concreto: no se atribuyen resultados por prueba.

Captura local (ignorada por Git):
`resultados/metricas/metricas_20261106T081143_400509Z.csv`.
Seis reproducciones de la misma grabación, 91648 muestras (11.456 s), 180 llamadas
incluido vaciado. Sin reinicios durante la secuencia.

| Reproducción | Condición | Resultado |
|---|---|---|
| 1 | Escucha SIN FILTRO, banda 100–1200 | Cuatro filas OK. Identidad: MSE 0, energía 100%, ΔSNR 0 |
| 1 repetida por `metricas` | Sin reproducción nueva | Cuatro filas idénticas deduplicadas por PC |
| 2 | Repetir grabación sin cambios | Métricas de señal idénticas, errores/pérdidas/desbordes 0 |
| 3 | Escucha ESPECTRAL | Métricas de los cuatro modos idénticas a las anteriores; estado OK |
| 4 | Cambiar notch 2150 → 2100 durante reproducción | CONFIG_CAMBIADA, seis métricas de señal NA por fila |
| 5 | Restaurar notch 2150 antes de reproducir | OK; recupera las métricas de señal originales |
| 6 | Banda local 100–3000 antes de reproducir | OK; SNR/ΔSNR y atenuación exterior NA, MSE y energía disponibles |

En los reportes completos recibidos, errores de trama/COBS/CRC/cabecera,
pérdidas y desbordes DAC permanecen en cero. RAM libre al final: 82812 B;
mayor bloque: 55296 B en los seis informes. Máximos totales entre 58.710 y
58.918 ms (plazo 64 ms); margen mínimo observado 5.082 ms, **ajustado**.
Las métricas incluidas consumen aproximadamente 19 ms medios por llamada.
Estos datos no garantizan plazos para toda configuración o condición futura.

La captura contiene seis grupos completos: cinco válidos y uno invalidado por
la placa. El analizador omitió cuatro duplicados y no rechazó líneas.
Generó tablas y figuras de los cinco válidos; el cuarto se conserva como
diagnóstico y no genera figuras. Código de salida 2 esperado para ese conjunto,
porque contiene CONFIG_CAMBIADA, no por fallo de lectura o captura.

## Límites y pendientes

- Esta validación comprueba consistencia, captura y comportamiento de las métricas;
  no demuestra calidad del filtrado contra una referencia limpia.
- El pico guardado fue −1 en todas estas corridas: no se validó en placa la
  atenuación por bin ±2 de un tono diagnosticado.
- No se probó aquí silencio digital ni el cambio de CONFIG recibido durante
  reproducción. Los casos de referencia numérica no sustituyen esas pruebas.
- Tras la prueba 6, restaurar en nodo 2 `banda 100 1200` antes de seguir usando
  la banda habitual. La escucha queda ESPECTRAL y el notch 2150 Hz, Q 8.5.
- Las capturas y figuras generadas son locales; conservarlas aparte si se requieren
  como evidencia de entrega. No se agregaron al repositorio como datos de prueba.
