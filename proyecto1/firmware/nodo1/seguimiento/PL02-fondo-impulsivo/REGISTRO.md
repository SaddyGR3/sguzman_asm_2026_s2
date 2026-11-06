# PL02: referencia de transitorios habituales del fondo

## Referencia y alcance

Rama `nodo1-debug-ampliado`, sin compilar ni hacer commit. `antes.tar.gz` conserva
los cinco archivos de diagnóstico/documentación antes de PL02, incluido PL01.
`referencia.json` conserva rama, HEAD y hashes de antes/después. `cambio.patch`
contiene únicamente este ajuste y su documentación; no incluye el trabajo previo.

## Evidencia previa

Con silencio declarado por el usuario: RMS aprendido 0.00664963, máximos cortos
que superan contraste 3 y un subbloque fuerte en muchos reportes. Tipo 5 confirmado
en 7–13 de cada 16 bloques, aun con `nivel sobre fondo 0`. Saturaciones nuevas 0.
Esta evidencia identifica el patrón aceptado, no su origen físico.

## Cambio

En las mismas 32 ventanas válidas de calibración guardar dos series: máximo RMS
de subbloques de 32 muestras y pico absoluto por bloque. Ordenar y tomar P95
por rango superior más cercano (índice 30). Conservar ambas referencias fijas.
Exigir al candidato anterior superar simultáneamente 1.5 veces cada referencia.
Conservar todas sus condiciones anteriores y mayoría 2/3. El conteo de subbloques
sigue siendo por contraste; la comparación con P95 es un requisito adicional.

El factor 1.5 es una constante inicial de amplitud, no una garantía de separar
todo ruido de toda señal. Un fondo mal capturado o variable puede ocultar impulsos
o generar falsos positivos. El generador conserva referencias cero. Reinicio y
`fondo_diag calibrar` vacían ambas series. Se agregan 256 bytes de arreglos fijos,
sin FFT extra ni reservas dinámicas por bloque. Cambios en `estado` y debug
permiten reconocer `PL02`, referencias y rechazos.

## Comprobaciones

Referencia independiente en Python/numpy, semilla 20261106; no ejecuta C++.
El script `referencia_numerica.py` está junto a este registro y puede ejecutarse
desde la raíz del repositorio con:

```sh
python3 proyecto1/firmware/nodo1/seguimiento/PL02-fondo-impulsivo/referencia_numerica.py
```

| Escenario, 256 bloques | Antes: candidatos / confirmaciones 2/3 | PL02 |
|---|---:|---:|
| Fondo con transitorios recurrentes | 192 / 254 | 0 / 0 |
| Impulsos fuertes añadidos al mismo fondo | 256 / 255 | 256 / 255 |
| Ráfagas útiles de 200 ms | 5 / 0 | 5 / 0 |

La calibración sintética da RMS 0.006678, corto P95 0.029373 y pico P95 0.054152.
Se verifican además inválidos, recorte, silencio digital y que no se agreguen
candidatos nuevos respecto de las reglas anteriores. Las confirmaciones pueden
superar en número a los candidatos, porque la mayoría 2/3 conserva historia.

Revisión estática: `git diff --check`, delimitadores, 66 `printf` con número de
argumentos correcto, funciones de UART/temporización/paquetes iguales a HEAD y
detectores espectrales iguales a la referencia previa a PL02. No comprueba tipos
C++, tiempos ni comportamiento real de la placa.

## Estado de las pruebas acústicas

| Caso | Antes de PL02 | Después |
|---|---|---|
| Silencio, banda 100–1200 | Falsos tipos 5 recurrentes | Pendiente |
| P1, banda 100–1200 | Tipo 1 antes de PL01; regresión PL01 pendiente | Pendiente |
| P2, banda 100–1200 | Tipo 4 antes de PL01; regresión PL01 pendiente | Pendiente |
| P3, banda 100–3000 | PL01 todavía sin corrida válida registrada | Pendiente |
| P4, banda 100–1200 | Tipo 0 antes de PL01 | Pendiente |
| P5, banda 100–1200 | Correcto antes de PL01; regresión PL01 pendiente | Pendiente |

Al cargar firmware, dejar silencio hasta `fondo listo`, usar `banda 100 1200` y
`vista debug`. Comprobar primero silencio unos 10 s y observar `DEBUG impulso
PL02`, mínimos y rechazos. No cambiar ganancia, montaje ni volumen entre casos.
Después comprobar P4 para detectar si el nuevo requisito pierde impulsos; P3 usa
100–3000 y evalúa PL01. No declarar pasadas las otras pruebas sin ejecutarlas.

## Reversión independiente

Desde la raíz del repositorio, comprobar primero y aplicar solo si la comprobación
pasa (estos comandos no se ejecutaron para revertir el trabajo):

```sh
git apply --check -R proyecto1/firmware/nodo1/seguimiento/PL02-fondo-impulsivo/cambio.patch
git apply -R proyecto1/firmware/nodo1/seguimiento/PL02-fondo-impulsivo/cambio.patch
```

Esto retira PL02 y conserva PL01 y el trabajo previo. Si se quiere quitar también
PL01, retirar primero PL02 y después usar el parche de PL01. Si otros cambios
impiden aplicar un parche, revisar el conflicto sin sobrescribir todo el árbol.
Los registros y referencias permanecen para comparar resultados.
