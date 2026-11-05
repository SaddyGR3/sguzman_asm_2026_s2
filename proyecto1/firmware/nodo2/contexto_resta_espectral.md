# Contexto de implementación: resta espectral (paso 6b-2)

Estado al 4 de noviembre de 2026. Documento para compartir con el equipo o
continuar el trabajo en otra sesión. Describe cambios aplicados al código;
no constituye evidencia de compilación ni de funcionamiento en placa.

## Rama y alcance

- Rama de trabajo: `nodo2-resta-espectral`.
- Creada desde `development`, en el commit `d8f6609` (base espectral 6b-1).
- Los pasos 1 a 6 del plan se completaron como implementación, documentación
  y revisión estática. La validación física sigue pendiente.
- Los cambios están en el árbol de trabajo, sin commit ni push de esta implementación.
- Solo se modificó `proyecto1/firmware/nodo2/`. No se modificaron el nodo 1,
  la simulación, los filtros temporales, el receptor, la grabación ni el controlador DAC.

## Arquitectura de esta implementación

El nodo 1 adquiere audio del micrófono y transmite INPUT y DIAG por UART.
La otra ESP32 reúne los nodos lógicos 2 y 3: graba por actividad y, al pedir
reproducción, decodifica la grabación y calcula dos rutas independientes sobre
la misma entrada: temporal (FIR/notch) y espectral (FFT/IFFT).

El modo elegido determina qué salida se entrega al DAC. La resta se calcula
en la ESP32 durante la reproducción, bloque a bloque; no en la PC. El sistema
no dispone de referencia limpia para medir MSE o SNR exactos en placa.

## Qué ya existía: paso 6b-1

- Modo `ESPECTRAL`, por botón GPIO32 o comando `modo espectral`.
- FFT de 1024 puntos, avance de 512 muestras a 8 kHz.
- Ventana raíz de Hann periódica en análisis y síntesis.
- FFT e inversa mediante ESP-DSP, con solapamiento y suma.
- Ganancia unitaria, sin reducción de ruido.
- Reinicio de estados al comenzar cada reproducción y bloque final de ceros
  para recuperar la cola espectral.
- Medición separada de `proc temporal`, `proc espectral` y `proc total`.

## Cambios aplicados

### 1. Estimador de ruido causal

En `src/espectral.cpp` se calculan las magnitudes de los 513 bins positivos,
incluidos DC y Nyquist, antes de modificar el espectro. Un anillo guarda las
últimas 8 tramas originales, incluida la actual; no se usan muestras futuras.

Para cada bin se calcula la mediana temporal de esos 8 valores. Luego se
suaviza el perfil con una mediana de 31 bins vecinos. En los extremos se
reflejan los índices sin repetir el valor del borde. El perfil y el piso
suavizado tienen búferes separados para evitar alterar vecinos aún pendientes.

La primera FFT contiene medio bloque de ceros de arranque y se excluye del
historial de ruido. Las primeras 8 llamadas de procesamiento mantienen
ganancia 1; la novena dispone de 8 tramas reales y empieza a aplicar la resta.

### 2. Ganancia de resta espectral

Con magnitud original `M[k]` y piso suavizado `P[k]`:

```text
G[k] = max(gmin, min(1 - alfa * P[k] / max(M[k], 1e-12), 1))
Y[k] = G[k] * X[k]
```

Se aplica la misma ganancia real a las partes real e imaginaria. Los bins
negativos se reconstruyen como conjugados de los positivos; DC y Nyquist
conservan parte imaginaria cero. Se mantienen las ventanas, la IFFT, la
normalización y el solape existentes, con retardo algorítmico de 64 ms.

La versión básica no incluye protección de tonos ni un método adicional de
detección y eliminación de picos.

### 3. Configuración y reinicios

`src/espectral.h` declara `ConfiguracionEspectral`, con valores iniciales:

| Parámetro | Inicial | Rango inclusivo |
| --- | ---: | --- |
| alfa | 3 | 0.5 a 10 |
| ganancia mínima | 0.05 | 0 a 0.5 |

La API agrega:

- `espectral_configurar(double alfa, double ganancia_minima)`: valida ambos
  valores antes de modificarlos; devuelve false si alguno es inválido.
- `espectral_configuracion()`: consulta de los parámetros vigentes.

Al iniciar una reproducción, `espectral_reiniciar()` limpia audio, solape,
historial de ruido, perfil, piso y contadores. Conserva los parámetros elegidos.
Cambiar alfa/gmin entre bloques no borra el historial. Reiniciar la placa
restaura los valores iniciales; no hay persistencia en flash.

### 4. Consola

`src/main.cpp` incorpora `espectral <alfa> <gmin>`. Requiere exactamente dos
números finitos dentro de los rangos. Argumentos faltantes, adicionales,
valores no numéricos, `nan`, `inf` o valores fuera de rango producen `Error:`
sin modificar la configuración. Se reutiliza el procesamiento de comandos
existente, que los aplica entre bloques completos.

`estado` y el mensaje de arranque muestran alfa y ganancia mínima. El comando
configura la intensidad; `modo espectral` selecciona la salida por el DAC.

Ejemplo, cuando exista una grabación en estado LISTA:

```text
espectral 3 0.05
modo espectral
estado
reproducir
```

### 5. Documentación

Se actualizó `README.md`: método de resta, calentamiento, parámetros, comandos,
memoria, compromiso ruido-distorsión y procedimiento manual de validación.
Se retiraron las descripciones que presentaban la ganancia unitaria como
comportamiento de la versión actual.

## Archivos de esta entrega

Rutas relativas a `proyecto1/firmware/nodo2/`:

| Archivo | Cambio |
| --- | --- |
| `src/espectral.cpp` | Estimador, ganancia, configuración y reinicios. |
| `src/espectral.h` | Estructura de configuración, API y comentarios actualizados. |
| `src/main.cpp` | Comando, consulta en estado y mensaje de arranque. |
| `README.md` | Documentación y pruebas manuales. |
| `contexto_resta_espectral.md` | Este documento de traspaso. |

## Memoria y costo pendientes de medir

Los arreglos nuevos son estáticos y suman **22 696 bytes (22.16 KiB)**:

| Arreglo | Bytes |
| --- | ---: |
| Magnitudes: 513 float | 2052 |
| Historial: 8 por 513 float | 16 416 |
| Perfil temporal: 513 float | 2052 |
| Piso suavizado: 513 float | 2052 |
| Trabajo compartido de medianas: 31 float | 124 |

Se agregan índices, bandera y configuración. No se reservan estos arreglos
por bloque ni se colocan en la pila. La memoria adicional puede reducir la
duración que consigue reservar el módulo de grabación; comprobar su capacidad
impresa al arrancar antes de grabar las pruebas.

Después del calentamiento, cada bloque agrega 513 medianas temporales de 8
valores y 513 medianas frecuenciales de 31 valores, además de magnitudes y
ganancias. El tiempo real no se ha medido. El máximo de `proc total` debe
quedar holgadamente por debajo de 64 000 microsegundos.

## Revisión realizada y límites

Se revisó estáticamente el diff: límites de arreglos, anillo temporal,
calentamiento, reinicios, simetría conjugada, validación de consola y entrega
de la misma entrada a ambas rutas. `git diff --check` pasó sin errores.

No se compiló, no se ejecutó el firmware, no se cargó a una placa y no se
hicieron pruebas auditivas de esta versión. No se hizo commit, push ni PR.
La revisión estática no confirma rendimiento, compilación o funcionamiento físico.

## Validación que debe realizar el equipo

1. Compilar y cargar el proyecto nodo2 desde PlatformIO. Revisar RAM y capacidad
   de grabación al arrancar; `estado` debe mostrar alfa 3 y gmin 0.05.
2. Calibrar en silencio y grabar P1 con el micrófono. Comparar la misma grabación
   en SIN FILTRO y ESPECTRAL; registrar cuánto baja el pitido de 2150 Hz.
3. Grabar P3 y comparar reducción del ruido blanco y conservación del audio.
4. Sobre la misma grabación de P3, comparar `espectral 1 0.1` con
   `espectral 8 0.02`. Elegir los parámetros antes de reproducir y esperar LISTA
   entre escuchas. Registrar distorsión y ruido musical.
5. Repetir una reproducción con los mismos parámetros: no debe aparecer audio
   residual de la anterior; el calentamiento debe repetirse y los parámetros
   conservarse. Comprobar también el botón de selección de filtro.
6. Probar extremos válidos (`espectral 0.5 0`, `espectral 10 0.5`) y rechazos:
   `espectral 0.4 0.05`, `espectral 3 0.6`, `espectral nan 0.05`,
   `espectral 3 inf`, `espectral 3` y `espectral 3 0.05 extra`.
   Verificar con `estado` que los rechazos no cambian parámetros.
7. Restaurar `espectral 3 0.05` y observar una reproducción completa sin escribir
   comandos: tiempos por debajo de 64 ms, errores, pérdidas y desbordes DAC en 0.
   Medir después del calentamiento, cuando ya se calculan las medianas.

## Riesgos y alcance pendiente

- Una resta agresiva puede atenuar señal útil y generar ruido musical.
- La mediana frecuencial puede excluir un pitido estrecho del piso estimado.
  Por ello, la reducción clara del pitido de P1 es un criterio pendiente de
  verificar; si no se cumple, registrar el fallo y acordar un ajuste del método.
- El arranque repite el calentamiento y el cambio de parámetros puede producir
  transiciones audibles. No se agregó suavizado adicional de ganancias.
- No se agregaron métricas, interfaz de PC, selección automática por DIAG,
  protección de tonos ni procesamiento en núcleos separados.
- Tras validar en placa, corresponde al equipo registrar resultados, hacer
  commit/push y preparar el PR de esta rama hacia `development`.
