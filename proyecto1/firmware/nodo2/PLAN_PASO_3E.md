# Plan de trabajo: Paso 3e

## Modo automático según el diagnóstico del nodo 1

Este documento describe la implementación del modo automático en la placa de los nodos 2 y 3. La reproducción es diferida, por lo que el diagnóstico utilizado debe ser el que el nodo 1 informó mientras se grababa el audio.

## Condición previa

El paso 3e requiere que el paso 7a esté fusionado en `development`.

Antes de comenzar se debe verificar que el nodo 2 ya reciba y aplique los mensajes `CONTROL CONFIG` enviados por el nodo 1, incluyendo la banda protegida vigente. El paso 3e no volverá a implementar esa propagación.

El paso 3e se implementará en la rama existente:

```text
propagacion-banda
```

La rama ya contiene el trabajo del paso 7a, por lo que el modo automático se agregará sobre esa misma base.

## Alcance

Solo se modificará:

```text
proyecto1/firmware/nodo2/
```

No se modificarán:

- El ADC.
- La decimación.
- La grabación de audio.
- La salida DAC.
- La ruta espectral.
- La simulación.
- Otros nodos.

Durante esta tarea no se compilará, no se subirá firmware y no se hará commit ni push.

## Objetivo

Agregar el comando:

```text
auto on
auto off
```

Cuando `auto on` esté habilitado, la placa configurará la ruta temporal al iniciar una reproducción usando el diagnóstico guardado junto con la grabación.

El valor inicial será:

```text
auto off
```

## Diagnóstico utilizado

Durante `GRABANDO`, se procesará cada DIAG válido recibido del nodo 1.

Los campos utilizados son:

| Offset | Campo | Uso |
|---:|---|---|
| 10 | `tipo_ruido` | Tipo de ruido informado por el nodo 1 |
| 11 | `filtro_n2` | Filtro sugerido para la ruta temporal |
| 12 | `pico_Hz` | Frecuencia del pico dominante |

Se leerán mediante las funciones existentes del protocolo, sin usar estructuras con posible relleno de memoria.

Solo se considerarán sugerencias con `filtro_n2 != 0`.

Un `pico_Hz` será válido únicamente si:

```text
es finito
100 <= pico_Hz <= 3000
```

## Diagnóstico asociado a cada grabación

Al comenzar una grabación nueva se limpiarán las acumulaciones de la grabación anterior.

Mientras el estado sea `GRABANDO`:

1. Se contará cada sugerencia válida de `filtro_n2`.
2. Se guardarán los picos válidos de las sugerencias 2 y 3.
3. No se utilizarán DIAG recibidos durante `ESPERANDO`, `LISTA` o `REPRODUCIENDO`.

Al pasar a `LISTA`:

- Se elegirá la sugerencia más frecuente.
- Si no hubo sugerencias, el diagnóstico será tipo 0, filtro 0.
- Para filtro 2, se calculará la mediana de sus picos válidos.
- Para filtro 3, también se calculará la mediana de sus picos, aunque se aplicará como notch.
- Para filtro 1 no se requiere un pico.

Una grabación nueva reemplazará el diagnóstico guardado anteriormente.

## Configuración automática al reproducir

Si `auto on` está activo, la configuración se aplicará antes del primer bloque de audio.

| `filtro_n2` | Acción |
|---:|---|
| 0 | Seleccionar `SIN FILTRO` |
| 1 | Usar la banda protegida vigente y seleccionar `FIR` |
| 2 | Configurar notch en el pico guardado, con Q = 8.5, y seleccionar `NOTCH` |
| 3 | Configurar notch en el pico dominante, con Q = 8.5, y seleccionar `NOTCH` |

Se reutilizarán las funciones existentes:

```cpp
filtros_cambiar_banda(...)
filtros_cambiar_notch(...)
filtros_reiniciar_estados()
```

La banda usada por el caso FIR será la banda vigente, incluyendo la última configuración recibida desde el nodo 1 mediante el paso 7a.

## Interacción con ESPECTRAL

La ruta espectral no se modificará.

Si el modo actual es `ESPECTRAL` y se inicia una reproducción con `auto on`:

- Se podrá actualizar internamente el FIR o el notch según el diagnóstico.
- El modo de salida permanecerá en `ESPECTRAL`.
- El automático no cambiará la salida a `FIR`, `NOTCH` o `SIN FILTRO`.

## Interacción con comandos y botón

El comando `modo` seguirá permitiendo seleccionar manualmente:

```text
modo sin
modo fir
modo notch
modo espectral
```

Cualquier comando `modo` desactivará el automático y mostrará:

```text
Auto: desactivado
```

El botón GPIO32 tendrá el mismo comportamiento: al cambiar el modo, pasará a control manual y desactivará `auto`.

## Mensajes esperados

Al iniciar una reproducción automática se mostrará una línea como:

```text
Auto: grabación tipo 1, filtro 2, pico 2148.4 -> NOTCH
```

Para una grabación sin diagnóstico:

```text
Auto: grabación tipo 0, filtro 0, pico -1 -> SIN FILTRO
```

El estado `auto on|off` y el diagnóstico de la grabación se mostrarán en los comandos:

```text
estado
grabacion
```

## Archivos previstos

Los archivos que podrían modificarse son:

```text
proyecto1/firmware/nodo2/src/protocolo.h
proyecto1/firmware/nodo2/src/protocolo.cpp
proyecto1/firmware/nodo2/src/recepcion.h
proyecto1/firmware/nodo2/src/recepcion.cpp
proyecto1/firmware/nodo2/src/grabacion.h
proyecto1/firmware/nodo2/src/grabacion.cpp
proyecto1/firmware/nodo2/src/main.cpp
proyecto1/firmware/nodo2/README.md
```

No se espera modificar `filtros.cpp`, porque sus funciones actuales ya permiten recalcular la banda, recalcular el notch y reiniciar los estados.

## Orden de implementación

1. Confirmar que la rama `propagacion-banda` contiene el paso 7a.
2. Agregar el callback para recibir DIAG válido.
3. Agregar el almacenamiento del diagnóstico durante `GRABANDO`.
4. Calcular el diagnóstico final al terminar la grabación.
5. Agregar `auto on` y `auto off`.
6. Aplicar el diagnóstico al inicio de la reproducción.
7. Desactivar automático desde `modo` y desde el botón GPIO32.
8. Mostrar automático y diagnóstico en `estado` y `grabacion`.
9. Actualizar el README.
10. Revisar cambios y desviaciones sin compilar ni subir.

## Pruebas previstas en placa

1. Ejecutar `auto on` y grabar P1.
2. Verificar que el diagnóstico guardado sea tonal, filtro 2, pico cercano a 2148.4 Hz.
3. Reproducir en silencio y comprobar:

   ```text
   Auto: grabación tipo 1, filtro 2, pico 2148.4 -> NOTCH
   ```

4. Grabar P3 y verificar que, con el diagnóstico actual del nodo 1, se obtenga tipo 0 y `SIN FILTRO`.
5. Pulsar el botón GPIO32 y verificar `Auto: desactivado`.
6. Ejecutar `modo espectral`, luego `auto on`, y comprobar que la reproducción permanezca en `ESPECTRAL`.
7. Comprobar que `errores`, `perdidos` y `desbordes_dac` permanezcan en cero.

## Riesgos

- Implementar sobre una rama que todavía no contiene el paso 7a.
- Mezclar el DIAG en vivo con el diagnóstico de la grabación.
- No reiniciar el diagnóstico al comenzar una nueva grabación.
- Configurar un notch con un pico inválido.
- Cambiar el modo durante el procesamiento de un bloque.
- Reemplazar accidentalmente el modo `ESPECTRAL` cuando el automático solo debe configurar la ruta temporal.
- Alterar la grabación, la salida DAC o la ruta espectral fuera del alcance de este paso.

## Desviaciones

Se documentarán aquí al terminar la implementación cualquier cambio respecto a este plan y cualquier prueba que no haya sido posible realizar.
