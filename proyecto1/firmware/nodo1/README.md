# Nodo 1: emisor

Adquiere audio del micrófono MAX4466 por un canal ADC. Cada 64 ms completa
512 muestras a 8 kHz y envía INPUT + DIAG por UART1, TX GPIO18, hacia la
placa que integra los nodos 2 y 3. UART0 (USB) se usa para la consola.

## Qué hace

- **Entrada predeterminada:** micrófono por GPIO36 (ADC1 canal 0), a 24 kHz,
  12 bits y 12 dB. El ritmo lo marca la adquisición ADC, sin temporizador.
- **Procesamiento:** tabla raw → mV, FIR de 37 coeficientes con decimación ÷3
  a 8 kHz, pasa altos de 10 Hz y normalización con escala de 1200 mV.
- **Diagnóstico:** FFT seleccionable de 256/512/1024 muestras (inicial 1024),
  salto N/2, piso por mediana y
  clasificación tonal, familia 50/60 Hz, impulsiva, de banda ancha o limitada.
- **Salida única:** INPUT + DIAG por UART1 a 921600 baudios, 8N1, con destino
  lógico nodo 2, más CONTROL CONFIG cuando corresponde. La cabecera tiene 32 B;
  se usan CRC-32, COBS y delimitador 0x00.
- **Arranque:** comprueba CRC y COBS, imprime la cabecera INPUT y escribe un
  0x00 inicial en UART1 para resincronizar el receptor tras reiniciar.

El formato de los paquetes está en [contrato_nodos.md](../../documentos/contrato_nodos.md).
Las rutas históricas del contrato no representan el cableado actual: el nodo 1
solo transmite hacia la placa conjunta por UART1.

## Entrada por micrófono

Conexiones del MAX4466:

- VCC a 3.3 V.
- GND al pin G de la placa.
- OUT a la pata − del capacitor de 10 µF de x.

Cadena de entrada: MAX4466 → capacitor de 10 µF de x → divisor de 1.32 V
→ Sallen-Key (mitad A del LM358) → GPIO36.

ADC1 usa un solo patrón a 24000 Hz, un pool de 16384 B y tramas DMA de
1024 B. Cada bloque consume 1536 muestras crudas y entrega 512 muestras de x.
El FIR, la fase de decimación y el pasa altos conservan su estado entre bloques.

La tabla raw → mV se calcula al arrancar con la calibración de ESP-IDF:
4096 valores int16_t (8192 B) si caben; de lo contrario, int32_t (16384 B).
Se aprovecha la calibración eFuse cuando está disponible; si falta, se informa
el uso de Vref por defecto. Durante la adquisición solo se consulta la tabla.
La configuración del proyecto conserva −O2 y CPU de 240 MHz.

**Lección de montaje:** los equipos externos (YP-05 y otras placas) se conectan
al **pin G de la placa**, nunca al carril de GND de la protoboard del circuito
analógico.

## Generador de respaldo

El generador permite continuar si falla la captura por micrófono y probar la
placa de los nodos 2 y 3 sin señal acústica. Para activarlo, cambiar
`FUENTE_ENTRADA` de `Fuente::ADC` a `Fuente::GENERADOR` en `src/main.cpp`
y volver a compilar. El valor predeterminado es `Fuente::ADC`.

Genera x = s + i: s contiene tonos de 300, 700 y 1100 Hz; i contiene un tono
de 2150 Hz. Los arreglos s e i solo se usan para formar x. En este modo,
un temporizador de 64 ms marca el ritmo. La salida sigue siendo únicamente
INPUT + DIAG y CONTROL CONFIG por UART1.

## Consola y contadores

Comandos por UART0 a 115200 baudios:

- `n <256|512|1024>`: cambia la FFT del diagnóstico, con salto H=N/2. El
  transporte conserva 512 muestras y 64 ms. Cambiar N incrementa `config_id`
  y envía CONFIG; repetir N no incrementa ni reinicia. Otro valor no modifica nada.

- `banda <lo> <hi>`: cambia la banda protegida; admite `100 ≤ lo < hi ≤ 3000` Hz;
  inicialmente 100–1200 Hz.
- `estado`: muestra la banda protegida, `config_id`, la vista, todos los umbrales,
  la referencia del fondo (estado, progreso y RMS) y el diagnóstico actual.
- `fondo_diag calibrar`: vuelve a capturar el ambiente durante unos 3 s. Mantener
  silencio con el micrófono conectado hasta el mensaje `fondo listo`. Reinicia
  la clasificación y la referencia, sin detener INPUT. Solo disponible en ADC.
- `umbral_diag tonal <valor>`, `umbral_diag red <valor>`,
  `umbral_diag impulsivo <valor>` y `umbral_diag banda <valor>`: ajustan razones
  lineales, sin recompilar. También admite `fondo`, `tonal_pct`, `red_rel`,
  `red_pct`, `region_pct`, `rafaga` y `pico_fondo`, definidos en la tabla de
  clasificación. Admiten valores finitos en `1 < valor ≤ 100`.
  Un comando inválido informa error y conserva los umbrales. Cada ajuste válido
  borra las historias y la clasificación publicada, incluso si repite el valor;
  conserva la referencia de fondo. Los ajustes se pierden al reiniciar la placa.
- `vista diag`: resumen compacto, con `ADC x <min>-<max> mV` solo en modo ADC.
- `vista todo`: diagnóstico detallado, periodos, procesamiento, empaquetado,
  tamaños de paquetes, pila libre y estadísticas TX de UART1. En ADC también
  muestra crudos, mV, frecuencias, desbordes del pool, saturaciones y tiempos.
- `vista debug`: resumen compacto más evidencia del clasificador, cada 16 bloques.
  No cambia umbrales, prioridad, persistencia ni formato de DIAG. `vista diag`
  o `vista todo` desactivan la captura adicional. La clasificación no se reinicia
  al cambiar de vista; sí se reinician las observaciones y contadores debug.

Para investigar una clasificación inesperada, ejecutar `vista debug` **antes**
de reproducir la señal de prueba y copiar un resumen con todas sus líneas DEBUG:

- `activo` indica RMS mayor que el mínimo y muestras finitas sin recorte
  normalizado; `ventana_valida` indica ambas mitades válidas. `nivel sobre fondo`
  indica si se cumple la condición adicional de actividad para espectro.
- `fondo PL02` muestra si está calibrando o listo, espera, progreso y RMS
  aprendido. Añade `corto P95` (máximo RMS de 4 ms por bloque) y `pico P95`
  (pico absoluto por bloque), aprendidos en las mismas 32 ventanas.
- `selección` muestra exceso de energía **fuera de protección**, porcentaje del
  pico más fuerte antes de excluir red/aplicar el mínimo de energía, porcentajes
  de ambas familias y de la región aceptada. Un pico evaluado puede ser rechazado
  aunque tenga mucho contraste local. Pico −1 y porcentaje 0 indican ausencia.
  La fracción de región utiliza el exceso del **piso**, no el de magnitudes.
- `armónicos antes de nivel relativo` permite comparar los candidatos brutos
  con las listas posteriores al corte relativo al más fuerte.
- `impulso` muestra contraste RMS corto, cantidad de subbloques fuertes (de 16),
  candidato actual y número de candidatos desde el último reporte.
  `umbrales impulso` muestra el máximo RMS corto actual, mínimos de fondo para
  corto y pico, si supera ambos y cuántos candidatos descartó PL02 en el intervalo.
  `subbloques fuertes` sigue contando el contraste relativo anterior: los dos
  mínimos de fondo son requisitos adicionales para aceptar el candidato.
- `nivel` muestra RMS, pico absoluto y cresta del bloque actual de 512 muestras,
  además de sus mínimos y máximos desde el último reporte debug. RMS y pico están
  en unidades normalizadas de x, después de decimación y pasa altos; no son mV ni
  niveles acústicos. La referencia de fondo se captura por separado y queda fija.
- `ancha` muestra ocupación en porcentaje y planitud, ambas con rango del
  intervalo; junto a ellas aparecen los límites reales usados por el detector.
  La ocupación exige elevación sobre el fondo; desde PL01 la planitud usa el piso
  actual sin restarle el fondo. `DEBUG ancha PL01` identifica esta versión.
  `evaluada` indica si se ejecutó la prueba en el bloque actual. Un valor −1
  significa medida no disponible; si no hubo evaluaciones, min/max también son −1.
  `candidata`, `confirmada`, `confirma` y `ausencias` permiten distinguir evidencia
  instantánea de una clasificación persistente, aunque gane otra categoría.
- `limitada` muestra la región candidata actual y la última confirmada, con sus
  confirmaciones y ausencias. Límites −1 indican que no existe esa región. También
  informa la mediana global del piso, el umbral efectivo de selección de bins y
  la energía de la región candidata. Así se puede observar una banda que haya
  quedado oculta por una categoría de mayor prioridad. La energía de región
  candidata es ahora suma de `max(piso² − piso_fondo², 0)`.
- `energía FFT 100-3000` es la suma de magnitudes al cuadrado del análisis actual.
  Para el pico publicado tonal/red y el candidato tonal se suma su bin ±2 dentro
  de ese rango, con porcentaje de la energía total, energía del resto y razón
  pico/resto en dB. `--` indica ausencia del pico o cociente indefinido. No son SNR
  ni energía temporal calibrada: se usa la FFT con su ventana y sin normalizar.
  La suma incluye la banda protegida para comparar el pico con todo el intervalo.
- `red elegida` es la base de la familia publicada elegida, 50 o 60 Hz; 0 indica
  ninguna. Puede existir una familia confirmada aunque gane un tono independiente.
- Para cada base, `actuales` cuenta armónicos en el análisis actual; `publicados`
  cuenta los de su última familia confirmada. `confirma` y `ausencias` muestran
  el estado de persistencia, con límite 3.
- Las listas `50 actual` y `60 actual` muestran los picos que se contaron como
  armónicos. La lista `familia publicada` conserva la evidencia del análisis que
  actualizó la familia, incluso durante su retirada. Si debug se activa cuando
  la familia ya estaba retirándose, avisa que aún no se capturó su lista.
- Cada pico se escribe `2148.4Hz C47.2 R0.0`: frecuencia real del bin, contraste
  `C` en dB contra su piso local y nivel `R` en dB respecto del más fuerte de esa
  misma lista. No son medidas de potencia acústica ni prueban el origen eléctrico.
- `máximos fuera de protección` muestra picos que superan el umbral tonal antes
  de excluir familias de red. Permite ver, por ejemplo, un tono de P1 que terminó
  agrupado como red, o un pico estable inesperado durante P2.
- Las listas se ordenan por magnitud, conservan hasta **ocho picos** y muestran
  el total real; si hay más, indican explícitamente el recorte. El límite es solo
  de presentación: el detector continúa contando todos los armónicos.
- `candidato independiente` es la frecuencia tonal después de excluir red y
  exigir la fracción de energía;
  −1 indica que no quedó candidato.
- `intervalo` cuenta los bloques observados desde el último reporte debug,
  las veces que se superó el umbral de cresta, las confirmaciones de impulsivo
  por mayoría 2/3 y cuántos bloques publicaron cada tipo 0–5. Así se observan
  eventos breves que no coinciden con el bloque del resumen. Al ajustar banda o
  umbrales también se limpian estas observaciones, junto con la clasificación.
- `bandas intervalo` cuenta por separado las candidatas y confirmaciones de cada
  detector de banda, incluso si nunca ganaron la prioridad durante ese intervalo.
- `ADC intervalo` añade mínimos/máximos crudos junto a los mV y las saturaciones
  nuevas de los mismos 16 bloques. Permite comprobar si un mínimo repetido de mV
  corresponde también al extremo del código ADC. No modifica la conversión.

Antes de reproducir, esperar a `fondo listo`. Si el arranque ocurrió con audio,
volver a calibrar en silencio. Para capturar una corrida usar `vista debug` y
copiar los reportes completos, incluidos fondo, selección, bandas y ADC.
Mantener montaje, ganancia y volumen entre corridas; volver a calibrar si cambia
el ambiente o el montaje. Los contadores de saturación siguen describiendo
recortes del procesamiento de entrada, no prueban por sí solos saturación física.

No se añaden FFT ni impresiones por bloque de audio; solo captura acotada cuando
debug está activo. Los logaritmos de las listas se calculan al imprimir. El tiempo
`análisis` incluye la captura adicional; la salida debug aumenta el tráfico por
UART0, por lo que se debe revisar `vista todo` después de la prueba para comprobar
tiempos, desbordes y descartes. El modo está destinado a investigar, no a corregir
automáticamente la clasificación.

Las tres vistas nombran los seis tipos y muestran el factor de cresta y la región
detectada cuando corresponde. El contraste del pico publicado se conserva junto
con ese pico durante su retirada. La vista completa muestra por separado la
magnitud, el piso y el contraste del candidato tonal actual; esos datos no cambian
la frecuencia publicada hasta que se cumplan las reglas de persistencia.

Los resúmenes se imprimen cada 16 bloques, aproximadamente cada 1.024 s.
El prefijo `#nnnn t=…s` indica el número de resumen desde 1 (compartido entre vistas, con al menos 4 dígitos) y los segundos desde el arranque con 1 decimal; en `vista todo` aparece solo en la primera línea.
`procesamiento max` excluye la espera de adquisición ADC. El tiempo de
calibración incluye la extracción, consulta de tabla y estadísticas; el tiempo
de filtrado incluye FIR, pasa altos y normalización. El análisis se mide aparte.

`overruns` es la suma acumulada de bloques atrasados del temporizador (solo
GENERADOR) y descartes TX de UART1 (ambos modos). Cada descarte TX cuenta una
pareja INPUT + DIAG que no se pudo encolar completa, sin reintento. Se informa
en el siguiente DIAG que logre transmitirse; la consola muestra también el
contador específico de descartes TX.

En ADC, DIAG informa además los desbordes del pool y las saturaciones acumuladas.
La bandera de discontinuidad (0x0010) se activa solo cuando aumenta el contador
de desbordes del pool; este cuenta eventos, no la cantidad exacta de muestras
perdidas. `first_sample` avanza 512 por bloque. Se conservan las banderas de
calentamiento (0x0002), reinicio (0x0004) y ventana parcial (0x0020).

## Clasificación del ruido

Los valores siguientes son parámetros iniciales del detector; su aceptación con
audio real requiere pruebas posteriores. La prioridad entre categorías confirmadas
es **tonal independiente → familia 50/60 Hz → impulsivo → banda → ninguno**.
Todos los detectores actualizan sus historias en cada bloque, aunque otro gane.
Solo se publica una categoría. «Ninguno confirmado» indica ausencia de un patrón
confirmado; no garantiza audio limpio.

| Tipo | Nombre | filtro_n2 | metodo | Pico y región detectada |
|---:|---|---:|---:|---|
| 0 | Ninguno confirmado | 0 | 0 | Pico y límites −1 |
| 1 | Tonal | 2 | 1 | Pico tonal; límites −1 |
| 2 | Familia 50/60 Hz | 3 | 1 | Armónico más fuerte; límites −1 |
| 3 | Banda ancha | 1 | 2 | Pico −1; región 100–3000 Hz |
| 4 | Banda limitada | 1 | 2 | Pico −1; límites estimados de la región |
| 5 | Impulsivo | 1 | 2 | Pico y límites −1 |

Se reutilizan la ventana sqrt-Hann periódica, la FFT y el piso local de mediana de
31 bins. La referencia global es la mediana del piso en los bins con centro entre
100 y 3000 Hz, calculada con memoria estática. No se agrega otra FFT ni memoria
dinámica por bloque. La referencia ocupa dos arreglos de 513 floats (4104 bytes)
y las características cortas 16 floats (64 bytes), además de estado y debug.
PL02 añade dos series de 32 floats (256 bytes) para la calibración temporal. `análisis` y `análisis max` incluyen las características
temporales, las búsquedas, las historias y la resolución de prioridad.

| Comando `umbral_diag <nombre> <valor>` | Valor inicial | Significado |
|---|---:|---|
| `tonal` | 6 | Magnitud / piso local |
| `red` | 6 | Magnitud / piso local por armónico |
| `impulsivo` | 6 | Cresta que habilita contraste corto más sensible |
| `banda` | 2 | Piso local / mediana global para limitada |
| `fondo` | 2 | RMS / RMS de fondo y amplitud espectral / fondo |
| `tonal_pct` | 20 | % mínimo de exceso fuera de protección en pico ±2 bins |
| `red_rel` | 25 | % mínimo de magnitud respecto del armónico más fuerte |
| `red_pct` | 20 | % mínimo de exceso fuera de protección en la familia |
| `region_pct` | 35 | % mínimo del exceso del piso fuera de protección en la región |
| `rafaga` | 3 | RMS corto / máximo entre mediana corta y RMS de fondo |
| `pico_fondo` | 3 | Pico absoluto / RMS de fondo |

Los valores son iniciales y ajustables, no una garantía de reconocer todas las
señales. Razones lineales y porcentajes no son dB. Todos los nombres admiten
valores finitos en `(1,100]`; el resto se rechaza sin modificar estado.

| Constante | Valor |
|---|---:|
| RMS mínimo normalizado | 0.0001 |
| Espera / captura del fondo | 8 bloques / 32 ventanas completas |
| PL02: percentil temporal / margen sobre referencia | 95 / 1.5 × amplitud |
| Confirmación / retirada espectral | 3 análisis / 3 ausencias |
| Tolerancia tonal y armónica | 1 bin, 7.8125 Hz |
| Armónicos mínimos cualificados por familia | 3 |
| Persistencia impulsiva | 2 de los últimos 3 bloques |
| Subbloque / cantidad máxima de subbloques fuertes | 32 muestras (4 ms) / 4 |
| Cresta mínima adicional para impulsivo | Mayor que 3 |
| Hueco máximo / anchura de región limitada | 2 bins / 8–128 bins (62.5–1000 Hz) |
| Ocupación mínima para banda ancha | 80 %, sobre fondo y sobre 0.25 × mediana global |
| Planitud mínima del piso actual para banda ancha | 0.5 |

### Referencia del ambiente y actividad

Al arrancar en ADC se descartan 8 bloques y se acumulan 32 ventanas completas
válidas (~2.56 s en total). Se promedian el RMS al cuadrado del bloque actual,
la potencia de cada bin y el piso local al cuadrado. PL02 guarda además el mayor
RMS corto y el pico absoluto de cada bloque; ordena cada serie de 32 valores y
toma su percentil 95 por rango superior más cercano (posición 31, índice 30).
No mezcla muestras de diferentes escalas temporales ni aprende durante la señal.
Se requiere **silencio con
el micrófono conectado**. Mientras calibra, DIAG publica tipo 0 y calentamiento;
INPUT continúa. Al terminar imprime `fondo listo` y la referencia queda congelada.
El generador usa fondo cero y omite la captura, pues reproduce desde el arranque.

El detector no puede comprobar que la captura sea silencio: si había audio,
repetir `fondo_diag calibrar` al detenerlo. La referencia no sigue automáticamente
una señal ni el ambiente. Si cambia el ruido ambiental, la ganancia o la posición,
volver a capturar. El silencio digital permite una referencia cero; el RMS mínimo
y epsilon `1e-12` evitan cocientes inválidos.

Para evidencia espectral, el RMS actual debe superar `fondo` veces el RMS de
referencia (con mínimo 0.0001). Además cada pico/bin usado supera su referencia
espectral por ese factor de amplitud. Una mitad con NaN, infinito o `|x| >= 0.999`
se sustituye por ceros **solo en el análisis**: no aporta evidencia, tampoco la
ventana solapada que la incluye. Durante calibración, una ventana inválida tras
la espera reinicia la captura. No se modifica el audio transmitido.

### Tonal y familias de red

Los máximos deben estar fuera de la protección y superar su contraste local y
el fondo aprendido. La energía de selección es `max(M² − potencia_fondo, 0)`.
La energía del pico suma su bin ±2, recortados a 100–3000 Hz y excluyendo la
protección. Se divide por el exceso de **todo el rango fuera de protección**;
no se divide por la energía de la señal útil protegida. El tono necesita al menos
`tonal_pct` y tres confirmaciones con tolerancia de un bin.

Cada familia busca múltiplos de 50 o 60 Hz a distancia máxima de un bin, con un
máximo por armónico. Retiene solo los que alcanzan `red_rel` de la magnitud del
más fuerte; exige al menos tres y energía conjunta `red_pct`. Solo una familia
que cumpla ambas condiciones excluye sus miembros de los candidatos tonales.
Ambas familias conservan confirmaciones separadas. Si ambas están confirmadas,
gana la de más armónicos, luego mayor suma de magnitudes y finalmente 50 Hz.

El pico declarado y su contraste se mantienen durante las dos primeras ausencias;
se retiran en la tercera. Un conjunto compatible con red sigue sin demostrar su
origen eléctrico. Las familias muy desiguales pueden quedar clasificadas como
un tono dominante; es una limitación explícita del requisito de fuerza relativa.

### Impulsivo

Se calculan 16 RMS de subbloques de 32 muestras (4 ms) dentro del bloque actual.
La referencia corta es el máximo entre su mediana, el RMS de fondo y 0.0001.
Un subbloque fuerte supera `rafaga` veces esa referencia. Si la cresta del bloque
supera `impulsivo`, el factor corto se reduce a `min(rafaga, 2)`.

Un candidato requiere de 1 a 4 subbloques fuertes (4–16 ms acumulados), cresta
mayor que 3 y pico absoluto mayor que `pico_fondo` veces el RMS de fondo (con
mínimo 0.0001). **PL02 exige además**, simultáneamente:

- Mayor RMS corto del bloque > 1.5 × `corto P95` del fondo.
- Pico absoluto del bloque > 1.5 × `pico P95` del fondo.

El factor 1.5 es una constante de amplitud (`DIAG_MARGEN_TRANSITORIOS`), no
potencia; no modifica los umbrales por consola anteriores. Estos requisitos se
añaden a las reglas de contraste y duración, sin crear candidatos nuevos. Con
fondo cero del generador no añaden un mínimo artificial. Se confirma
con dos candidatos en tres bloques y se retira al perder esa mayoría. No exige
el umbral de RMS global usado por el espectro; un impulso breve puede tener poco
RMS global. Los subbloques fuertes pueden ser separados o contiguos.

Esta duración ayuda a excluir la parte sostenida de una ráfaga útil, pero sus
ataques y otros transitorios de señal útil pueden confundirse con ruido. Impulsos
muy débiles, largos o aislados pueden no confirmar. Si la captura incluye un
ruido fuerte, puede elevar las referencias y ocultar impulsos posteriores; volver
a calibrar en silencio cuando corresponda. El percentil con 32 bloques es una
estimación corta, sin garantía de cubrir todas las variaciones del ambiente; no se promete distinguirlos
perfectamente con una sola mezcla capturada por micrófono.

### Bandas y resolución de prioridad

Limitada exige piso local > `banda` × mediana global y elevación sobre el fondo,
fuera de protección. Une huecos de hasta dos bins sin cruzar la protección.
Acepta coberturas de 8 a 128 bins y al menos `region_pct` del exceso del piso fuera
de protección (`max(piso² − piso_fondo², 0)`). Elige la región de mayor exceso;
en empate, la de menor frecuencia inicial. Persiste tres análisis con solapamiento
de al menos la mitad de la menor región y se retira tras tres ausencias.

Ancha analiza todo 100–3000 Hz, incluida la protección. Cuenta bins con piso >
0.25 × mediana global **y** por encima de su fondo aprendido por factor `fondo`.
Exige ocupación >=80% y planitud >=0.5 sobre el **piso actual sin resta**
(PL01). La planitud es la media geométrica / aritmética. Restar la referencia
antes de calcularla producía ceros artificiales que rechazaban ruido ancho.
El fondo sigue siendo obligatorio para actividad y ocupación; su resta se
conserva para energía de selección tonal, red y limitada. Confirma y se retira
en tres.

La prioridad completa es **tonal cualificado → red cualificada → impulsivo →
limitada → ancha → ninguno**. Una limitada confirmada tiene preferencia frente a
ancha. Sus límites se conservan durante la retirada y son centros de bins, no
bordes exactos. Si la protección tapa parte del ruido, solo se informa la parte
visible; no se reconstruye ni adivina el tramo protegido.

Un cambio real de banda y cualquier ajuste válido de umbral reinician historias
y clasificación, conservando la referencia de fondo y la ventana de audio.
Repetir la misma banda no reinicia. `fondo_diag calibrar` reinicia también la
referencia. El calentamiento cuenta tres ventanas válidas después de capturar.

Las mismas reglas se aplican a cualquier audio, incluido el desconocido de la
revisión. No se identifican archivos ni se fijan excepciones por frecuencia. El
ruido que cambió desde la calibración puede contar como señal; una mezcla de
varias interferencias o señal útil fuera de protección puede ser ambigua. Cerca
de los bordes, la fuga espectral puede producir picos o ensanchar una región.

## Campos DIAG y región detectada

El paquete mantiene sus **64 bytes y offsets existentes**. Cambia la semántica
de `banda_lo` y `banda_hi`: describen la región de ruido detectada para tipos 3 y
4, y valen **−1 para los tipos 0, 1, 2 y 5**. `pico_Hz` solo es válido para tipos
1 y 2; vale −1 para los demás. `config_id` sigue identificando la configuración
de banda protegida, que se comunica mediante CONTROL CONFIG. No debe inferirse
la protección a partir de los límites de DIAG.

La energía, DC, piso, ventana, calentamiento y contadores mantienen sus campos.
El factor de cresta, los umbrales y el contraste son información local de consola;
no amplían el paquete binario.

## Banda protegida

Nodo 1 es la fuente de la banda protegida. Envía CONTROL CONFIG (tipo 5,
32 bytes de datos little-endian) al nodo 2 después del DIAG del primer bloque,
tras cada cambio de banda y aproximadamente cada segundo. `config_id` empieza
en 1 y aumenta solo si cambian los valores; repetir el mismo comando no lo
incrementa. Las repeticiones conservan el ID. `estado` muestra la protección y
su ID; DIAG conserva el ID y comunica la región de ruido con la semántica anterior.

CONFIG comparte la secuencia de INPUT y DIAG; `indice_efectivo` indica la primera
muestra del próximo INPUT. Usa fs=8000, N vigente (256/512/1024), H=N/2, método=0, opcode=1 y
status=0. Ocupa como máximo 70 bytes en el cable. No hay confirmación de vuelta:
la repetición permite recuperar la configuración si se pierde o reinicia nodo 2.

Se prioriza encolar INPUT + DIAG en el búfer TX. Solo después se intenta CONFIG,
reservando margen adicional para su escritura. Si no cabe, queda pendiente para
otro bloque, sin consumir secuencia ni sumar un descarte de audio. No añade
esperas ni cambia el ritmo de adquisición de 512 muestras cada 64 ms; los tiempos
y la ausencia de pérdidas deben verificarse en placa.

En nodo 2 la banda local es para pruebas: las repeticiones del mismo ID no la
reemplazan; un CONFIG con un ID nuevo vuelve a aplicar la banda del nodo 1.
Si llega durante reproducción, nodo 2 lo difiere hasta terminar.

## Requisitos

VS Code con la extensión PlatformIO. El proyecto usa `framework = espidf`
(ESP-IDF) y ESP-DSP, declarado en `src/idf_component.yml`.

## Compilar, subir y monitor

Desde `proyecto1/firmware/nodo1/`:

```sh
pio run
pio run -t upload
pio device monitor -p /dev/ttyUSB0 -b 115200
```

O con los botones de PlatformIO en VS Code.

## Validación de esta corrección

El plan está en [PLAN_CORRECCION_DIAGNOSTICO.md](PLAN_CORRECCION_DIAGNOSTICO.md).
El ajuste PL01, la referencia previa y las instrucciones para revertirlo están en
[seguimiento/PL01-planitud/REGISTRO.md](seguimiento/PL01-planitud/REGISTRO.md).
PL02 y su reversión independiente están en
[seguimiento/PL02-fondo-impulsivo/REGISTRO.md](seguimiento/PL02-fondo-impulsivo/REGISTRO.md).
Se revisaron reglas, límites, comandos y conservación de interfaces. No se compiló,
no se cargó firmware y no se ejecutaron WAV de `simulacion/` durante este cambio.
La clasificación real y los tiempos permanecen pendientes de comprobar en placa.
Pasaron `git diff --check`, el balance de delimitadores y el conteo de argumentos
de las 65 llamadas `printf`. Las funciones de temporización, UART y empaquetado
coinciden con HEAD. Son comprobaciones estáticas; no comprueban tipos C++.

La referencia previa a PL02, **independiente en Python**, usó numpy/scipy, semilla 20261105,
FFT de 1024, sqrt-Hann y mediana de 31 bins, fondo gaussiano RMS 0.015 y 32 ventanas
de referencia. Evaluó 119 ventanas por escenario sintético. Los resultados son
**candidatos instantáneos**, no salidas de C++ ni validación de la persistencia
espectral. Se comprobó por separado la mayoría impulsiva 2/3.

| Escenario sintético | Candidatos en 119 ventanas |
|---|---|
| Fondo sin señal añadida | 119 ninguno |
| Tono dominante con dos secundarios débiles | 119 tonal |
| Tres armónicos equilibrados de 50 Hz | 119 familia |
| Tres armónicos equilibrados de 60 Hz | 119 familia |
| Banda 2000–2800 + pico débil + tono protegido | 119 limitada |
| Banda ancha con protección 100–3000 | 119 ancha |
| Banda 900–1300 parcialmente protegida | 104 limitada, 15 tonal |
| Tono útil protegido continuo | 119 ninguno |
| Ráfagas útiles de 200 ms | 115 ninguno, 4 candidatos impulsivos; 0 confirmaciones 2/3 |
| Impulsos breves repetidos | 119 candidatos impulsivos; 118 confirmaciones 2/3 |

La banda parcialmente protegida aún puede generar candidatos tonales en su borde.
No se alteraron umbrales para ocultar ese resultado. Esta referencia no representa
el parlante, el MAX4466, el circuito ni los tiempos del ESP32.

### Comprobación independiente de PL02

La referencia reproducible [referencia_numerica.py](seguimiento/PL02-fondo-impulsivo/referencia_numerica.py)
usa numpy y semilla 20261106. Calibra 32 bloques de fondo sintético con
transitorios recurrentes; obtuvo RMS 0.006678, corto P95 0.029373 y pico P95
0.054152. No usa grabaciones reales ni ejecuta el C++.

| Caso, 256 bloques | Confirmaciones 2/3 anteriores | Con PL02 |
|---|---:|---:|
| Mismo fondo con transitorios habituales | 254 | 0 |
| Fondo más impulsos breves más fuertes | 255 | 255 |
| Ráfagas útiles de 200 ms | 0 | 0 |

También comprueba silencio digital, NaN/infinito, recortes y que PL02 nunca
agregue candidatos que las reglas anteriores habrían rechazado. Son escenarios
controlados; P4 y silencio por micrófono siguen pendientes con PL02. El espectro
conserva PL01. No se atribuye a estos números una validación acústica de P1–P5.

### Primera comprobación después de cargar el firmware

1. Detener el audio de la computadora y dejar conectado el micrófono.
2. Reiniciar nodo 1 o escribir `fondo_diag calibrar`. Mantener silencio hasta
   `>> fondo listo | RMS ... | puede reproducir` (normalmente unos 3 s).
3. Escribir `estado` y comprobar `fondo listo` y los umbrales iniciales. Si la
   captura se hizo con audio, repetir el paso 2 antes de continuar.
4. Escribir `banda 100 1200` y después `vista debug`. Observar primero 5–10 s de
   silencio: debe predominar tipo 0, sin confirmaciones persistentes de tipo 3/5.
5. Reproducir P1 sin tocar volumen ni montaje. Revisar el pico tonal y los
   armónicos antes/después del corte relativo. Copiar los reportes completos.
6. Detener el audio y comprobar la retirada. Continuar con P2 (región limitada)
   y P4 (candidatos cortos y confirmaciones 2/3). P4 no necesita ser tipo 5 en
   todos los bloques; registrar las proporciones del intervalo.
7. Comprobar regresiones con P3 usando `banda 100 3000` y con P5 volviendo a
   `banda 100 1200`. Con P5 documentar solo la porción no protegida y posibles
   transiciones, sin exigir que informe 900–1300 completo.
8. Volver a `vista todo` para revisar tiempos, saturaciones nuevas, pérdidas y
   desbordes; el análisis extra debe caber en los 64 ms. `vista diag` vuelve al
   resumen normal. No hace falta nodo 2 para esta comprobación del clasificador.

Si cambió el ambiente, posición o ganancia, detener el audio y repetir la captura
de fondo. No recalibrar mientras suena la prueba. Repetir las señales con las
mismas condiciones permite comparar las reglas, sin ajustar por nombre de prueba.

Para validar CONFIG con las dos placas, seguir la prueba del README de
[nodo 2](../nodo2/README.md#prueba-de-banda-y-automático-con-dos-placas).

## Problemas conocidos

- **Subida lenta:** `upload_speed = 115200` en `platformio.ini`. A velocidades
  mayores la subida falló con esta placa.
- **Falla un include de ESP-DSP** (por ejemplo `dsps_fft2r.h`) después de cambiar
  dependencias: `pio run -t fullclean` y volver a compilar.
- **Basura en el monitor con el YP-05 conectado:** PlatformIO puede abrir el
  puerto equivocado. Indicar el puerto con `-p /dev/ttyUSB0`.

## FFT configurable: análisis separado del transporte

El INPUT conserva 512 float32, sus índices y un paquete por 64 ms. `n` solo cambia
el diagnóstico y los campos N/H existentes de CONFIG y DIAG; no cambia ADC,
decimación, FIR de entrada, normalización, velocidad UART ni formato binario.

| N | H | Análisis por INPUT | Resolución fs/N | Retardo espectral en la placa |
|---:|---:|---:|---:|---:|
| 1024 | 512 | 1 | 7.8125 Hz | 64 ms |
| 512 | 256 | 2 | 15.625 Hz | 32 ms |
| 256 | 128 | 4 | 31.25 Hz | 16 ms |

El historial máximo se mantiene en orden cronológico. Cada subbloque de H forma
su ventana de N; se publica un único DIAG por INPUT, correspondiente al **último
análisis**, con su inicio de ventana absoluto. El tiempo de análisis incluye
todos los subanálisis y, durante la captura de fondo, las tres referencias.
Las confirmaciones espectrales se cuentan por análisis (su duración temporal
cambia con H); la cresta, subbloques de 4 ms y mayoría impulsiva se calculan una
vez por INPUT de 512, conservando las reglas temporales PL02. Los contadores de
`DEBUG intervalo` cuentan análisis; los rangos temporales se observan por INPUT.

Al cambiar N se limpian ventana/historias de clasificación, sin reiniciar audio,
umbrales ni fondo. Durante la calibración en silencio se capturan **tres perfiles
espectrales**, uno por rejilla N, promediando los subanálisis de cada INPUT. Las
referencias temporales PL02 siguen usando bloques de 512. Cambiar N después no
aprende el sonido reproducido ni necesita otra calibración. Si la captura inicial
fue con audio, repetir `fondo_diag calibrar` en silencio como antes.

La tabla FFT se inicializa una sola vez para 1024; una ventana máxima sqrt-Hann
permite obtener las menores por submuestreo. Los búferes conservan capacidad
máxima. Los dos perfiles adicionales de fondo añaden 8208 bytes estáticos. La
captura de los tres perfiles aumenta el costo durante calibración: revisar
`análisis max`, desbordes ADC y TX tanto al arrancar como en uso normal.

Los umbrales en bins conservan sus cantidades: mediana local 31, tolerancia 1,
pico ±2, región mínima 8. Su cobertura en Hz crece al reducir N, por lo que no se
garantiza la misma clasificación fina ni bordes iguales para todos los tamaños.
No se ajustaron para memorizar P1–P5. P4 sigue como limitación conocida.

CONFIG sigue después del DIAG y se repite aproximadamente cada segundo. Banda
y N comparten `config_id`. Una placa reiniciada recupera la configuración por
repetición; un reinicio de nodo 1 se reconoce como sesión nueva. N vuelve a 1024
al arrancar. En placa, `estado` debe mostrar el nuevo N/H antes de reproducir.

Pruebas y comandos en [PRUEBA_N_CONFIGURABLE.md](../../herramientas_pc/PRUEBA_N_CONFIGURABLE.md).
No se compiló ni se validó todavía en placa esta ampliación. Las comprobaciones
numéricas de PC no ejecutan C++ ni garantizan tiempos reales.
