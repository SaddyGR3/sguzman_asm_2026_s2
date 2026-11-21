# CE1110 — Tarea 2: Modelado de sistemas

**Proyecto relacionado:** Diseño de un sistema de control de frenado de ABS  
**Integrantes:** 4  
**Entrega de la tarea:** 22 de noviembre de 2026  
**Objetivo:** completar los cinco puntos obligatorios (100 %) y procurar los dos puntos extra (hasta 80 % adicional).

## 1. Distribución del trabajo

| Integrante | Responsabilidad principal | Puntos de la tarea | Valor |
|---|---|---|---|
| **1 — Hardware y diagrama** | Diagrama de bloques y construcción de la planta | 4 y 6 | 25 % + 40 % extra |
| **2 — Muestreo y firmware** | Frecuencia de muestreo, PID sin `delay()` y apoyo a la planta | 2 y 3 | 30 % |
| **3 — Teoría y modelado** | Respuestas al impulso/escalón y modelo matemático | 1 y 5 | 45 % |
| **4 — Experimentos y documentación** | Caracterización experimental, MATLAB, videos e integración | 7 | 40 % extra |

> Los porcentajes corresponden a los apartados de la rúbrica, **no** a una medida equivalente de esfuerzo. El montaje y las pruebas deben realizarse en colaboración.

## 2. Indicaciones por integrante

### Integrante 1 — Diagrama y construcción

**Punto 4 (25 %):** elaborar el diagrama de bloques del sistema completo y describir en prosa los componentes continuos y discretos: referencia, adquisición de velocidad, microcontrolador, accionamiento del freno, motor y disco.

**Punto 6 (40 % extra):** liderar la construcción de la planta **sin controlador**, con disco, motor DC, freno accionado y sensor. Demostrar funcionamiento **a lazo abierto**.

**Entregables:**
- [ ] Diagrama de bloques legible y explicación de cada componente.
- [ ] Planta ensamblada y funcional.
- [ ] Fotografías del montaje.
- [ ] Video del funcionamiento a lazo abierto.
- [ ] Descripción de materiales y conexiones para el informe.

### Integrante 2 — Muestreo y programación

**Punto 2 (15 %):** explicar cómo determinar la frecuencia de muestreo de un sistema de control continuo y justificar una propuesta razonable para el banco de frenado. La frecuencia definitiva debe considerar la dinámica y las mediciones reales.

**Punto 3 (15 %):** explicar cómo implementar un PID digital en un microcontrolador, por qué evitar `delay()` y mostrar código que use temporización no bloqueante. Para esta tarea, el código PID puede presentarse como ejemplo; el punto extra 6 exige la planta a lazo abierto, no el PID funcionando.

**Entregables:**
- [ ] Justificación de la frecuencia y período de muestreo.
- [ ] Explicación del algoritmo PID discreto.
- [ ] Código de microcontrolador sin `delay()`.
- [ ] Apoyo en conexión y lectura del sensor de velocidad.
- [ ] Registro de tiempo, entrada de frenado y velocidad para las pruebas.

### Integrante 3 — Teoría y modelo matemático

**Punto 1 (20 %):** explicar por qué las respuestas al impulso y al escalón son importantes para modelar sistemas y ejemplificar ambas con el banco de frenado.

**Punto 5 (25 %):** plantear la representación matemática del sistema según la teoría, explicar la respuesta esperada de la planta sin controlador e identificar parámetros teóricos posibles. Diferenciar claramente el modelo supuesto de los parámetros que se obtengan experimentalmente.

**Entregables:**
- [ ] Explicación y ejemplos de respuesta al impulso y escalón.
- [ ] Ecuaciones del sistema rotacional y sus supuestos.
- [ ] Modelo matemático y comportamiento esperado a lazo abierto.
- [ ] Parámetros físicos relevantes y fuentes bibliográficas.
- [ ] Apoyo al integrante 4 en interpretación y ajuste del modelo.

### Integrante 4 — Caracterización y documentación

**Punto 7 (40 % extra):** coordinar la caracterización de la planta mediante respuesta al escalón. Trabajar con los datos reales obtenidos del montaje, procesarlos en MATLAB y documentar el resultado. El enunciado también solicita utilizar la respuesta al impulso de MATLAB disponible en LAIMI.

**Entregables:**
- [ ] Protocolo de prueba a lazo abierto: condición inicial, entrada escalón y medición.
- [ ] Datos registrados de entrada y velocidad angular en función del tiempo.
- [ ] Gráficas y análisis de la respuesta al escalón.
- [ ] Trabajo en MATLAB según las indicaciones del profesor.
- [ ] **Un solo video** que muestre la ejecución física, las explicaciones del equipo y el funcionamiento en computadora.
- [ ] Integración del PDF final, revisión de referencias y enlaces de videos.

## 3. Dependencias y colaboración

1. **Integrantes 1 y 2:** deben tener el montaje y la adquisición de velocidad operativos para poder registrar datos.
2. **Integrante 4:** necesita esa planta funcional para aplicar escalones de frenado y obtener las mediciones.
3. **Integrante 3:** apoya la interpretación de las curvas y la comparación entre modelo y comportamiento real.
4. **Todo el grupo:** participa en una sesión de montaje, pruebas y grabación; revisa que las explicaciones sean consistentes.

**Prioridad:** construir y probar temprano la planta a lazo abierto. Sin datos físicos, el punto 7 extra queda comprometido.

## 4. Cronograma propuesto

| Fecha | Actividad | Responsables |
|---|---|---|
| **12–14 nov.** | Definir componentes y montaje; iniciar teoría, modelo y diagrama | Todos |
| **15–17 nov.** | Ensamblar planta, probar freno y adquirir velocidad | 1 y 2; apoyo del grupo |
| **18–19 nov.** | Ensayos a lazo abierto con entrada escalón y registro de datos | 1, 2 y 4; apoyo de 3 |
| **20 nov.** | Análisis en MATLAB y grabación de videos | 3 y 4; participación de todos |
| **21 nov.** | Integración, referencias, revisión técnica y PDF | 4 coordina; todos revisan |
| **22 nov.** | Subir entrega antes de las 11:59 p. m. | Responsable designado |

## 5. Lista de verificación final

### Puntos obligatorios (100 %)
- [ ] **1 (20 %):** importancia de respuesta al impulso y al escalón, con ejemplos del proyecto.
- [ ] **2 (15 %):** determinación y propuesta justificada de frecuencia de muestreo.
- [ ] **3 (15 %):** PID en microcontrolador y código sin `delay()`.
- [ ] **4 (25 %):** diagrama de bloques y descripción de componentes continuos y discretos.
- [ ] **5 (25 %):** representación matemática y respuesta esperada de la planta sin controlador.

### Puntos extra (hasta 80 % adicional)
- [ ] **6 (+40 %):** planta completa, fotos y video de funcionamiento a lazo abierto.
- [ ] **7 (+40 %):** caracterización por escalón, trabajo en MATLAB y video único físico/computadora.

### Formato de entrega
- [ ] Un archivo **PDF** con respuestas fundamentadas, ejemplos, fotografías y referencias.
- [ ] Programas del microcontrolador incluidos en el PDF (pueden ir como *listing*).
- [ ] Enlaces a videos **no listados** en YouTube, o a una lista de reproducción no listada.
- [ ] Figuras, ecuaciones, código y enlaces legibles.
- [ ] Verificación de citas y originalidad del contenido.
- [ ] Entrega en **TEC-Digital → Evaluaciones**, antes de las **11:59 p. m. del 22 de noviembre**.

## 6. Criterio de prioridad

1. Asegurar los cinco puntos obligatorios.
2. Completar cuanto antes el montaje para optar al **punto 6 (+40 %)**.
3. Registrar una respuesta al escalón real y procesarla en MATLAB para optar al **punto 7 (+40 %)**.
4. Reservar el 21 de noviembre para integrar y revisar, no para empezar a construir.

> **Nota:** esta distribución es una propuesta organizativa. Los requisitos y porcentajes provienen de *Tareas_ASM_Tarea2_v5.pdf*; la descripción de la planta se apoya en *Proyectos_ASM_Proyecto_Grupal2_v7.pdf*.
