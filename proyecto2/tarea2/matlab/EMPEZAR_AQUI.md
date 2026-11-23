# Empezar con los CSV reales

Colocar en `../capturas/` al menos un par `datos_*.csv`/`eventos_*.csv` de giro libre y un par de frenado `g40`, ambos con RPM iniciales parecidas. Abrir esta carpeta en MATLAB y ejecutar:

El capturador ahora numera los pares automáticamente: `datos_1.csv`/`eventos_1.csv` y `datos_2.csv`/`eventos_2.csv`. Si esos son los únicos ensayos de la carpeta, dejar `opciones.ids = {};` en `ejecutar_analisis.m`; no hay que indicar nombres a MATLAB.

```matlab
ejecutar_analisis
```

El programa imprime qué corridas incluyó, omite las incompletas y guarda gráficas y tablas en `resultados_reales/`. Consultar [README.md](README.md) para escoger solo dos corridas con `opciones.ids`, interpretar el modelo y comprobar `impulse`.

El [ejemplo ideal](ejemplo_ideal.m) del compañero permanece separado; sus valores son hipotéticos y corresponden a un motor que sigue alimentado durante el escalón.
