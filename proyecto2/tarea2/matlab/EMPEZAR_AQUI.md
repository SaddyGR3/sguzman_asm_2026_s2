# Ejecutar el ejemplo ideal

Abrir esta carpeta en MATLAB y ejecutar lo siguiente.

```matlab
close all
clear analizar_ensayo estilo_figura
ejemplo_ideal
```

`close all` cierra las figuras de la sesión. Omitirlo para conservar otras gráficas abiertas.

El ejemplo crea un CSV simulado, ajusta un modelo y muestra figuras detalladas más un resumen de tres paneles. Los valores son hipotéticos y no describen mediciones de la maqueta. El usuario ya confirmó su ejecución en MATLAB y los parámetros recuperados.

Si aparece la advertencia sobre Control System Toolbox, el ejemplo sigue funcionando con la expresión analítica del impulso. Falta ejecutar `impulse` con ese complemento para completar esa parte del enunciado.

Consultar [README.md](README.md) para el formato de datos, configuración de ensayos reales, supuestos, resultados y pendientes. Después puede probarse `demo_simulada`, cuya ejecución en MATLAB aún debe comprobarse.
