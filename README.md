# CE1110 Análisis de Señales Mixtas — sguzman_asm_2026_s2

Repositorio del grupo para el Proyecto Grupal 1: un sistema distribuido de reducción de ruido en tiempo real con 3 ESP32 conectados por UART. El nodo 1 adquiere (o genera) la señal y la envía; el nodo 2 filtra en el tiempo y reproduce por DAC; el nodo 3 filtra por FFT/IFFT, calcula métricas y las muestra.

## Carpetas de `proyecto1/`

| Carpeta | Contenido |
|---|---|
| [firmware/](proyecto1/firmware/) | Firmware de las ESP32. Hoy: [nodo1/](proyecto1/firmware/nodo1/), el emisor del nodo 1, terminado y verificado en placa. |
| [herramientas_pc/](proyecto1/herramientas_pc/) | Receptor en la PC que valida lo que envía el emisor, con capturas reales de 60 s. |
| [simulacion/](proyecto1/simulacion/) | Simulación en Python: protocolo, banco de señales, cadena analógica y nodo 2 hechos; nodo 3 en curso. |
| [documentos/](proyecto1/documentos/) | Enunciados, contrato entre nodos, plan de frecuencias, guías y estado del proyecto. |
| [tarea1/](proyecto1/tarea1/) | Entrega de la Tarea 1, ya cerrada. |
| [avance_s12/](proyecto1/avance_s12/) | Entrega del avance de la semana 12. |

## Empezar aquí

- [estado_proyecto.md](proyecto1/documentos/estado_proyecto.md): qué está hecho y qué falta.
- [guia_git.md](proyecto1/documentos/guia_git.md): flujo de ramas. Leerla antes del primer commit.
- [contrato_nodos.md](proyecto1/documentos/contrato_nodos.md): formato de los paquetes y reglas entre nodos.
- [plan_frecuencias.md](proyecto1/documentos/plan_frecuencias.md): plan de frecuencias.
- [guia_conexiones_hardware.md](proyecto1/documentos/guia_conexiones_hardware.md): conexiones de las placas.

## Entregas

- Avance de la semana 12: **30 oct, 11:59 pm**.
- Proyecto completo: **6 nov, 11:50 pm**.

## Tarea 1

La entrega está en [proyecto1/tarea1/](proyecto1/tarea1/) y en el tag `tarea1_prototipo`.
