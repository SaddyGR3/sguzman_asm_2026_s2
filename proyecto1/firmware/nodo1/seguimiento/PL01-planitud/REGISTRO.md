# PL01: planitud del piso sin resta

## Referencia y alcance

Rama `nodo1-debug-ampliado`. Sin compilar ni hacer commit.
`antes.tar.gz` conserva los cinco archivos del trabajo de nodo 1 justo antes de
PL01, incluidos todos los cambios locales anteriores. `referencia.json` registra
el HEAD, la rama y SHA-256 de los archivos antes y después.

`cambio.patch` contiene solamente el incremento PL01: cálculo de planitud,
identificación y descripción de consola, README y plan. No contiene los cambios
anteriores de diagnóstico o debug. Este registro permanece como historial incluso
si se revierte PL01.

## Motivo y cambio

P3, con banda 100–3000, quedó tipo 0 en los intervalos recibidos. Su ocupación
frecuentemente superó 80%, pero la planitud residual cayó alrededor de 0.09–0.18.
La resta del fondo puede dejar ceros que hunden la media geométrica.

PL01 calcula media geométrica / aritmética del piso actual, sin resta. Conserva
umbral 0.5, ocupación 80%, requisitos de elevación sobre fondo, actividad RMS y
persistencia. El resto de detectores, prioridad, energía, adquisición y paquetes
conservan las reglas anteriores. El debug imprime `DEBUG ancha PL01`.

## Registro de pruebas acústicas

Estas observaciones anteriores provienen del usuario; no son ejecuciones del agente.
Mantener volumen, montaje y umbrales, y capturar el fondo en silencio.

| Caso | Banda | Antes de PL01 | Después de PL01 |
|---|---|---|---|
| Silencio | 100–1200 | Sin resultado registrado de esta versión | Pendiente: observar falsos tipos 3/5 |
| P1 | 100–1200 | Tipo 1 | Pendiente |
| P2 | 100–1200 | Tipo 4 | Pendiente |
| P3 | 100–3000 | Mayormente 0; tipo 3 intermitente | Pendiente |
| P4 | 100–1200 | Tipo 0; impulsivo sin resolver | Pendiente; PL01 no busca corregirlo |
| P5 | 100–1200 | Usuario confirmó resultado correcto | Pendiente |

Primero observar silencio y repetir P3. Luego comprobar P1/P2/P5 para detectar
regresiones. Registrar tipos y contadores de intervalo, no solo el último bloque
de cada resumen. No declarar éxito acústico con los resultados sintéticos.

## Comprobaciones realizadas

- Caso numérico dirigido: 320 bins con piso 3 y 52 con piso 0.9, fondo 1.
  Ocupación 86.02%; planitud residual anterior 0.0211, planitud PL01 0.9368.
  Con piso igual al fondo la ocupación sigue siendo 0%.
- Referencia independiente Python, diez escenarios y 119 ventanas por escenario:
  conserva los resultados previos del README, incluidos los casos ambiguos.
  Evalúa candidatos instantáneos y mayoría temporal 2/3; no ejecuta el C++.
- Revisión del incremento contra la copia: en `diagnostico.cpp` solo cambia la
  fórmula de planitud y su comentario; en `main.cpp` solo dos textos de consola.
- `git diff --check` y comprobaciones estáticas de formato/interfaz. Sin validación
  de tipos, compilación, carga ni medida de tiempos en placa.

## Cómo revertir únicamente PL01

Desde la raíz del repositorio, primero comprobar que el parche aún se puede quitar:

```sh
git apply --check -R proyecto1/firmware/nodo1/seguimiento/PL01-planitud/cambio.patch
```

Si pasa, revertir solo ese incremento:

```sh
git apply -R proyecto1/firmware/nodo1/seguimiento/PL01-planitud/cambio.patch
```

Esto conserva el trabajo anterior sin commit. Si la comprobación falla después
de otros ajustes, revisar el conflicto antes de revertir: no restaurar todos los
archivos desde Git ni sobrescribirlos con el archivo completo anterior. Para
comparar archivos completos se puede extraer `antes.tar.gz` en un directorio
temporal, sin reemplazar el árbol de trabajo.
