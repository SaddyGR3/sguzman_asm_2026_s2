# Análisis MATLAB de las capturas reales

Los datos físicos conocidos y pendientes están en [METADATOS_MONTAJE.md](METADATOS_MONTAJE.md).

Abrir MATLAB en la raíz del repositorio y ejecutar:

```matlab
run('proyecto2/tarea2/analisis/analizar_capturas.m')
```

El script usa las tres corridas libres y las dos frenadas comparables del 22 de noviembre. Lee ambos CSV de cada corrida, comprueba la presencia de los eventos y compara el tiempo desde unas 1300 RPM hasta menos de 500 RPM. Guarda en `resultados/` el resumen CSV, la gráfica de las cinco curvas y la gráfica de un **modelo local** ajustado solo antes de 500 RPM.

Estima la caída libre aproximando `dω/dt = -kω`. Para las frenadas ajusta `dω/dt = -kω - cu`, con `u=1` después de ordenar 40° al servo y `c` expresado como aceleración adicional efectiva en RPM/s. La función de transferencia local desde la orden normalizada hasta el cambio de velocidad es `G(s) = -c/(s+k)` tras convertir a rad/s. Si MATLAB tiene Control System Toolbox, el script usa `tf` e `impulse` para guardar `impulso_modelo_local.png`.

Este ajuste describe solo las velocidades aproximadas de 1300 a 500 RPM en el montaje de las capturas. No mide torque, fuerza ni el instante real de contacto del servo; el modelo lineal no representa la saturación en cero ni valida por sí solo la respuesta a un impulso físico. `RPM=0` es el indicador del firmware tras un tiempo sin pulsos. La marca manual de apagado tiene incertidumbre por reacción humana. La curva de impulso corresponde al **modelo** y debe explicarse así en el video.

MATLAB no está instalado en el entorno de este repositorio, así que el archivo `.m` todavía debe ejecutarse en la computadora del equipo o en LAIMI. Las métricas de los CSV fueron verificadas por separado con Python.
