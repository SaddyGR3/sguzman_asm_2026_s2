# FFT configurable sin modificar el transporte

Rama `bloques-configurables`. Implementación sin compilar firmware ni hacer
commit desde el agente. INPUT sigue en 512 muestras, 8 kHz, 64 ms y UART a
921600. Cambia N de diagnóstico y espectral; H=N/2. Solo nodo 1 manda CONFIG.

## Verificación previa en PC

```sh
python3 -m unittest discover -s proyecto1/herramientas_pc/tests -v
```

18 pruebas: parser v1/v2/v3, fragmentación, NA, repeticiones, conflictos, N/H,
captura y referencias numéricas de reconstrucción, retardos, ventanas y extremos.
Son referencias independientes: no ejecutan el C++ ni demuestran el plazo real.
Revisión estática de delimitadores y argumentos printf; `git diff --check`.
El formato INPUT y su validación siguen en 512; CONFIG sigue en 32 bytes y DIAG
en 64. CSV v3 añade n_fft/h_fft al final (35 campos) sin alterar campos anteriores.

## Preparación en las dos placas

1. Cargar ambos firmwares actualizados y abrir sus monitores. Nodo 2 debe tener
   el filtro `metricas_csv` del monitor. No mezclar firmware antiguo que solo
   valida CONFIG 1024/512 con este emisor configurable.
2. Dejar silencio con el micrófono conectado hasta `fondo listo` en nodo 1.
   Se aprenden las tres rejillas en esa captura, sin reservas dinámicas. Vigilar
   `análisis max`, desbordes ADC y descartes TX durante esa fase y después.
3. En nodo 1: `banda 100 3000`. Comprobar que nodo 2 aplique la banda por CONFIG.
4. Grabar P3 **una sola vez** usando el disparo existente y esperar LISTA en
   nodo 2. Consultar `grabacion` para verificar duración; ese comando no graba.
5. En nodo 2: `modo espectral`. Esto desactiva auto y permite mantener la escucha
   espectral durante la comparación. Conservar alfa, ganancia mínima, volumen y
   montaje. No volver a grabar entre tamaños.

## Escucha y medición por tamaño

Realizar cada fila por separado. Esperar a que finalice la reproducción antes
de pasar a la siguiente. Los comandos `n` van en nodo 1; `estado`/`reproducir`
van en nodo 2.

| En nodo 1 | Verificar en `estado` de nodo 2 | Después, nodo 2 | Retardo RESTA esperado |
|---|---|---|---:|
| `n 1024` | N 1024 H 512 | `reproducir` | 64 ms |
| `n 512` | N 512 H 256 | `reproducir` | 32 ms |
| `n 256` | N 256 H 128 | `reproducir` | 16 ms |
| `n 1024` | N 1024 H 512 | `reproducir` | 64 ms; regresión de retorno |

En cada informe comprobar cuatro filas `METRICAS,3,`, mismo N/H en el grupo,
misma cantidad L de muestras y MSE SIN FILTRO 0. FIR/notch conservan coeficientes
y deberían conservar MSE al cambiar solo N. La métrica de energía por banda puede
variar aun en esas rutas por resolución/fuga/bins: no exigir igualdad entre N
distintos. Al volver a 1024 con la misma grabación/configuración, las métricas de
señal deberían reproducir las de la primera corrida, exceptuando tiempos.

Con protección completa la SNR/ΔSNR y atenuación exterior son NA; eso no invalida
el informe. MSE y energía siguen informando la modificación de x. El retardo
indicado es algorítmico, no la latencia total de UART, adquisición, DMA y parlante.

Escuchar el compromiso entre resolución 7.8125/15.625/31.25 Hz y retardo. No
exigir que el ruido musical aumente monótonamente: depende del audio y estimador.
El calentamiento de ocho tramas y la mediana de 31 bins conservan sus cantidades,
por lo que su duración/cobertura cambian. La clasificación también puede variar
al perder resolución; P4 no se corrige en esta etapa.

Para analizar, usar el archivo anunciado por el monitor:

```sh
python3 proyecto1/herramientas_pc/analizar_metricas.py RUTA_CSV --etiqueta P3
```

## CONFIG durante reproducción

1. Estando en 1024 y LISTA, ejecutar `reproducir` en nodo 2.
2. Mientras suena, escribir `n 512` en nodo 1.
3. Nodo 2 debe anunciar CONFIG diferida y conservar N 1024 durante esa reproducción.
4. El informe que termina debe seguir N 1024 H 512 y estado OK; después se aplica
   el CONFIG pendiente. `estado` debe mostrar N 512 H 256.
5. Otra reproducción de la misma grabación debe salir en N 512. Si durante una
   reproducción se reciben varios CONFIG, solo se aplica el último al terminar.
6. Repetir `n 512` en nodo 1 no cambia ID ni reinicia; `n 128`, `n 0` y texto
   adicional deben rechazarse. Volver a `n 1024` al terminar las comprobaciones.

## Recepción, tiempos, memoria y límites

- INPUT/DIAG deben seguir alrededor de 15.6/s. Sin aumentos de CRC, COBS,
  cabeceras inválidas, pérdidas o desbordes DAC/ADC; comparar contadores antes/después.
- Medir el máximo total de reproducción y vaciado para cada N contra los 64 ms.
  No extrapolar la holgura de v2. También revisar la calibración inicial de nodo 1.
- Los arreglos y tabla se reservan al máximo; cambiar N no debe reducir RAM libre
  progresivamente. Se añaden 8208 B estáticos en nodo 1 para dos referencias de
  fondo extra y 2048 B en nodo 2 para el bloque espectral anterior de métricas.
- Reiniciar nodo 2 debe recuperar el N de nodo 1 por CONFIG repetido. Reiniciar
  nodo 1 vuelve a N 1024 y a una sesión nueva; nodo 2 debe aceptar ese CONFIG
  aunque su ID se haya usado antes. No reiniciar durante la comparación P3,
  porque puede reiniciar la calibración/grabación.

Estado actual: pruebas de PC y revisión estática realizadas; compilación,
escucha, clasificación, memoria y plazos en los tres tamaños **pendientes en placa**.
