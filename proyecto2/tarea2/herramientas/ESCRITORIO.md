# Aplicación de escritorio del banco de frenado

La ventana nativa conserva la conexión serial, simulación, gráficas, ciclos automáticos y captura del banco. Usa PySide6 y comparte la clase Banco con el panel anterior. No abre navegador ni servidor HTTP. La ESP32 sigue ejecutando la medición y el control. Esta interfaz no requiere cambiar ni cargar firmware.

## Abrir con un archivo Python

Desde cualquier carpeta puedes ejecutar este comando en fish.

```fish
python3 '/home/saddygr/Documentos/GitHub/sguzman_asm_2026_s2/proyecto2/tarea2/herramientas/banco_frenado.py'
```

Si estás dentro de herramientas, basta con `python3 banco_frenado.py`. El archivo también tiene permiso de ejecución para usar `./banco_frenado.py`.

El arranque comprueba PySide6 y pyserial. Si el Python elegido no los tiene, utiliza el entorno `.venv` de esta carpeta. Si todavía no existe un entorno preparado, lo crea e instala `requirements-escritorio.txt`. La primera instalación puede necesitar internet y permisos de escritura en herramientas. No instala paquetes globales y no depende de `/tmp`. No hace falta activar el entorno a mano.

`python3 banco_frenado.py --comprobar` verifica el entorno sin abrir una ventana. `--sin-instalar` impide preparar paquetes nuevos. La simulación también necesita `g++` para compilar temporalmente el cálculo PID y la conversión angular del firmware.

## Conectar la ESP32

1. Cierra la conexión del panel anterior y el monitor de PlatformIO para liberar el USB.
2. Selecciona ESP32. La búsqueda periódica omite los puertos ttyS del sistema y elige automáticamente un único USB. Si hay varios, debes elegir. El campo sigue permitiendo un puerto manual.
3. Pulsa Conectar ESP32. Buscar puertos no los abre ni inicia el motor. Abrir la conexión puede reiniciar la placa.
4. Pulsa Consultar estado. Las órdenes y respuestas aparecen en Eventos y órdenes.
5. Elige duración y ángulo, por ejemplo seis segundos y 30 grados, y pulsa Iniciar ciclo fijo. El comportamiento es el mismo del firmware probado, con corte a 1400 RPM e inicio del freno al bajar a 1300 RPM.

Los botones Encender motor y Apagar motor están en Control manual y calibración. Se conserva el campo para otros comandos y el diagnóstico GPIO34. El ensayo automático mantiene el rango de 15 a 45 grados y la calibración manual conserva de 0 a 90 grados. Las ganancias físicas permanecen en el firmware, sin cambiarlas desde esta ventana.

## Probar sin maqueta

Selecciona Simulación e Iniciar simulación. También puedes abrir directamente esa fuente con `python3 banco_frenado.py --simulacion`. Esta opción conecta la planta ficticia, pero no inicia el motor de la maqueta.

Se mantienen los controles de RPM objetivo y ganancias de ejemplo, las referencias lineal, exponencial normalizada y coseno, el ciclo libre, el fijo y el PID simulado. Las referencias fisicas disponibles son lineal y exponencial normalizada. Seleccionar una y pulsar Aplicar figura entre ensayos. El coseno queda solo para simulacion. La figura activa se muestra y su selección se bloquea durante el ensayo.

## Gráficas y diagnóstico

La ventana muestra velocidad, referencia, error, acción solicitada, limitada y aplicada, orden al servo y términos P, I y D. La velocidad cruda puede ocultarse. Los intervalos sin medida válida no se rellenan. El cero estimado tras un segundo sin pulsos conserva su indicación y no sustituye una medición del PID.

Puedes elegir una ventana de 15, 30, 60 o 300 segundos, consultar puntos con el puntero y exportar la gráfica de velocidad a PNG. Pausar vista congela gráficas y tarjetas, pero la captura, el estado de conexión y los eventos siguen actualizándose. Reanudar recupera la vista actual.

Las pestañas inferiores contienen señal y temporización, eventos y órdenes y las últimas llamadas del sensor GPIO34. Los registros completos permanecen en los CSV y en serial.txt.

## Captura y cierre

Los archivos se guardan automáticamente en `proyecto2/tarea2/capturas/escritorio/reales` o `simuladas`, dentro de una carpeta nueva por conexión. El botón Abrir carpeta de captura muestra su ubicación. `--salida` permite elegir otra carpeta.

Se conservan los formatos de datos_1.csv, eventos_1.csv, diagnostico_1.csv, sensor_1.csv, serial.txt y metadatos.json. Los metadatos identifican la interfaz como escritorio. Desconectar cierra los archivos y no exige alcanzar cero.

Si se intenta cerrar o desconectar con una prueba física o motor ordenado activo, la ventana ofrece cancelar primero. Después de aceptar, espera una confirmación nueva del firmware y una muestra con motor apagado antes de cerrar la captura. Si no llega, deja la ventana abierta y muestra el problema. Si se perdió la conexión con un último estado activo, indica que no puede confirmar la parada y permite volver o cerrar explícitamente. No afirma que la placa se haya detenido por cerrar una ventana.

Las aperturas y cierres de fuente, la búsqueda USB y la compilación de la simulación se hacen en hilos para mantener la ventana disponible. El panel web y el modo terminal anteriores siguen disponibles para comparar o volver al funcionamiento anterior. No deben abrir a la vez el mismo puerto USB.

## Verificación

Las pruebas de escritorio usan Qt fuera de pantalla y puertos simulados. Comprueban el ciclo completo de la planta ficticia, CSV con descenso libre, exportación PNG, pausa, selección de puerto, recuperación de errores y confirmación de cancelación. No certifican una nueva prueba física del motor o del sensor.
