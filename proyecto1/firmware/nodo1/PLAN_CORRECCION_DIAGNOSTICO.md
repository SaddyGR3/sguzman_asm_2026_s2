# Corrección general del diagnóstico de nodo 1

## Alcance

Implementar sobre `nodo1-debug-ampliado`, conservando los cambios debug existentes.
Solo diagnóstico, consola y documentación de nodo 1. No cambiar adquisición,
audio INPUT, paquetes DIAG/CONFIG ni nodo 2. No compilar ni hacer commit.
No leer ni modificar `simulacion/`. Una FFT existente por bloque, memoria fija.

## Problemas observados

- En silencio, ocupación casi completa y planitud suficiente disparan banda ancha.
- Una familia de múltiplos de 50 Hz absorbe un tono dominante junto con picos
  mucho menores; la coincidencia de frecuencias no basta para clasificar red.
- Un pico pequeño respecto de la interferencia puede ocultar una banda limitada.
- Banda limitada y ancha se confirman simultáneamente, y gana siempre la ancha.
- Cresta 6 pierde impulsos acústicos; bajarla a 4.5 también clasifica el fondo.

## Reglas de implementación

1. **Referencia del ambiente:** al arrancar en ADC, descartar 8 bloques y acumular
   32 ventanas completas válidas (~2.56 s en total). Promediar potencia temporal,
   magnitudes FFT al cuadrado y piso local al cuadrado. Congelar la referencia.
   Durante la captura publicar tipo 0 con calentamiento. `fondo_diag calibrar`
   repite la captura y borra las historias; `estado` informa progreso y RMS.
   El usuario debe dejar silencio con el micrófono conectado. Si la captura
   incluye audio, repetirla; el sistema no puede demostrar que estaba en silencio.
   El generador conocido omite esta captura y usa fondo cero.
2. **Actividad espectral:** exigir RMS > 2 veces el RMS de fondo. Cada pico o bin
   seleccionado debe superar también su referencia espectral por factor 2.
   Rechazar evidencia con muestras no finitas o recortadas (|x| >= 0.999).
3. **Tonal:** mantener contraste local 6 y persistencia 3/3; exigir además que el
   pico ±2 bins tenga >=20% del exceso de energía fuera de protección. El exceso
   por bin es max(M² − potencia de fondo, 0). No dividir por energía útil protegida.
4. **Red:** mantener contraste 6 y tolerancia de un bin; contar solo armónicos
   >=25% de la magnitud del más fuerte. Exigir >=3 y energía conjunta >=20% del
   exceso fuera de protección. Solo una familia que cumpla todo excluye sus
   miembros del candidato tonal. Conservar confirmación y retirada 3/3.
5. **Bandas:** conservar selección local/global y persistencia. Exigir elevación
   sobre el fondo. Para limitada, anchura entre 8 bins y 1000 Hz y >=35% del exceso
   de energía del piso fuera de protección. Para ancha, ocupación >=80% de todo
   100–3000 Hz y planitud >=0.5 del piso actual sin resta (ajuste PL01). Una limitada
   confirmada tiene preferencia frente a ancha. No inferir regiones protegidas.
6. **Impulsivo:** 16 subbloques de 32 muestras (4 ms). Comparar su RMS con el mayor
   entre su mediana y el RMS de fondo. Exigir de 1 a 4 subbloques por encima de
   factor 3, pico >3 veces el RMS de fondo y cresta >3. El umbral de cresta 6
   también puede habilitar el contraste corto con factor 2. Confirmar 2/3 bloques.
   Limitar duración evita aceptar la parte sostenida de una ráfaga tonal; no
   garantiza distinguir todos los ataques de señal útil de los impulsos de ruido.
7. **Prioridad:** tonal cualificado → red cualificada → impulsivo → limitada →
   ancha → ninguno. Conservar frecuencia publicada durante retirada.
8. **Consola:** ampliar `umbral_diag` con `fondo`, `tonal_pct`, `red_rel`,
   `red_pct`, `region_pct`, `rafaga`, `pico_fondo`. Razones o porcentajes según
   nombre, valores finitos en (1,100]. Banda/umbrales reinician historias pero
   conservan referencia. Reinicio de placa vuelve a valores iniciales y calibra.
9. **Debug:** mostrar referencia, actividad sobre fondo, exceso fuera, fracciones
   de pico/familia/región, armónicos antes/después de filtrar, contraste corto y
   cantidad de subbloques, candidatas impulsivas y confirmaciones por intervalo.

Los números son valores iniciales explícitos, no resultados garantizados de las
grabaciones. No identificar pruebas ni introducir excepciones por frecuencia.

## Verificación

Revisión estática, `git diff --check`, coherencia consola/documentación y revisión
de límites, invalidación y persistencia. Referencia numérica independiente en
Python con señales sintéticas (no compila ni ejecuta el firmware): fondo,
tono dominante con secundarios débiles, familias equilibradas, banda con pico
débil, ruido ancho, impulsos y ráfagas útiles. Documentar resultados y límites.

Después de que el usuario cargue firmware: primero referencia en silencio,
comprobar `estado`, observar silencio y luego repetir audios sin mover montaje
ni ajustar volumen. Revisar clasificación y contadores/timing con `vista todo`.
P1/P2/P4 requieren comprobar las correcciones; P3/P5, comprobar regresiones.
La latencia, el costo real y la clasificación acústica solo se validan en placa.

## Estado de entrega

Implementado en `src/diagnostico.cpp`, `src/diagnostico.h`, `src/main.cpp` y README.
Se conservaron los cambios debug previos. Sin compilación ni commit.

- `git diff --check`: sin errores.
- Revisión de delimitadores y 65 llamadas `printf`: sin discrepancias; no es
  comprobación de tipos ni sustituye compilar.
- Temporizador, funciones de UART y empaquetado INPUT/DIAG/CONFIG: iguales a HEAD.
- Una llamada a la FFT existente por análisis; sin reservas dinámicas explícitas.
- Referencia Python: diez escenarios sintéticos, 119 ventanas por caso. Fondo,
  tono dominante, familias, banda con pico débil y ruido ancho cumplieron la
  expectativa en todas sus ventanas. No ejecuta C++ ni persistencia espectral.
- Limitación observada: banda parcialmente protegida dio 104 candidatos limitada
  y 15 tonal. Ráfagas útiles dieron cuatro candidatos impulsivos aislados, ninguno
  confirmado 2/3. Impulsos repetidos dieron 118 confirmaciones de 119 ventanas.

El README contiene los resultados, límites y la primera comprobación en placa.

## Ajuste PL01: planitud sin resta de fondo

Las corridas acústicas posteriores dieron P1 tipo 1, P2 tipo 4 y P5 correcto,
pero P3 quedó mayormente tipo 0 incluso con protección 100–3000. El debug mostró
planitud ~0.09–0.18 en muchos resúmenes, con ocupación frecuentemente >=80%.
P4 también sigue pendiente (tipo 0 según el usuario); PL01 no corrige impulsivo.

Se reemplaza únicamente la magnitud residual usada para la planitud por el piso
actual. El fondo conserva su función en actividad y ocupación. Umbrales y resto
de detectores se conservan. Identificación en consola: `DEBUG ancha PL01`.

Referencia completa anterior, parche incremental reversible, resultados y tabla
de regresión: [seguimiento/PL01-planitud/REGISTRO.md](seguimiento/PL01-planitud/REGISTRO.md).

## Ajuste PL02: referencia temporal del fondo

El silencio real produjo 7–13 confirmaciones impulsivas por intervalo de 16
bloques, con RMS cerca del fondo y sin saturaciones nuevas. La regla de contraste
corto detectaba transitorios habituales que el RMS global no caracteriza.

Durante las mismas 32 ventanas de captura se guardan máximo RMS corto y pico
absoluto por bloque. Tomar percentil 95 por rango superior más cercano (índice
30). El candidato anterior debe superar además 1.5 veces ambas referencias.
Conservar los contrastes, duración máxima, mayoría 2/3, PL01 y todo el espectro.
Usar dos arreglos estáticos de 32 floats (256 bytes). La referencia sigue congelada
y se borra al reiniciar o ejecutar `fondo_diag calibrar`. El generador sigue con
fondo cero. Mostrar referencias, mínimos aplicados y rechazos en debug PL02.

Referencia anterior completa, parche incremental y registro de pruebas:
[seguimiento/PL02-fondo-impulsivo/REGISTRO.md](seguimiento/PL02-fondo-impulsivo/REGISTRO.md).
