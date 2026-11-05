# Nodo 1: emisor

Adquiere audio del micrófono MAX4466 por un canal ADC. Cada 64 ms completa
512 muestras a 8 kHz y envía INPUT + DIAG por UART1, TX GPIO18, hacia la
placa que integra los nodos 2 y 3. UART0 (USB) se usa para la consola.

## Qué hace

- **Entrada predeterminada:** micrófono por GPIO36 (ADC1 canal 0), a 24 kHz,
  12 bits y 12 dB. El ritmo lo marca la adquisición ADC, sin temporizador.
- **Procesamiento:** tabla raw → mV, FIR de 37 coeficientes con decimación ÷3
  a 8 kHz, pasa altos de 10 Hz y normalización con escala de 1200 mV.
- **Diagnóstico:** una FFT de 1024 muestras, salto de 512, piso por mediana y
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

- `banda <lo> <hi>`: cambia la banda protegida; admite `100 ≤ lo < hi ≤ 3000` Hz;
  inicialmente 100–1200 Hz.
- `estado`: muestra la banda protegida, `config_id`, la vista, los cuatro umbrales,
  el RMS mínimo, las constantes de ocupación/planitud y el diagnóstico actual.
- `umbral_diag tonal <valor>`, `umbral_diag red <valor>`,
  `umbral_diag impulsivo <valor>` y `umbral_diag banda <valor>`: ajustan razones
  lineales, sin recompilar. Admiten valores finitos en `1 < valor ≤ 100`.
  Un comando inválido informa error y conserva los umbrales. Cada ajuste válido
  borra las historias y la clasificación publicada, incluso si repite el valor.
- `vista diag`: resumen compacto, con `ADC x <min>-<max> mV` solo en modo ADC.
- `vista todo`: diagnóstico detallado, periodos, procesamiento, empaquetado,
  tamaños de paquetes, pila libre y estadísticas TX de UART1. En ADC también
  muestra crudos, mV, frecuencias, desbordes del pool, saturaciones y tiempos.

Ambas vistas nombran los seis tipos y muestran el factor de cresta y la región
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
dinámica por bloque. `análisis` y `análisis max` incluyen las características
temporales, las búsquedas, las historias y la resolución de prioridad.

| Parámetro | Valor inicial |
|---|---:|
| Umbral tonal: magnitud / piso local | 6 |
| Umbral red: magnitud / piso local por armónico | 6 |
| Umbral impulsivo: pico absoluto / RMS | 6 |
| Umbral banda: piso local / referencia global | 2 |
| RMS mínimo del bloque normalizado | 0.0001 |
| Confirmación / retirada espectral | 3 análisis completos / 3 ausencias |
| Tolerancia tonal y armónica | 1 bin, 7.8125 Hz |
| Armónicos mínimos por familia | 3 |
| Persistencia impulsiva | 2 de los últimos 3 bloques |
| Hueco máximo / anchura mínima de región | 2 / 8 bins (62.5 Hz de cobertura) |
| Ocupación mínima para banda ancha | 80 % con piso > 0.25 × referencia global |
| Planitud mínima del piso para banda ancha | 0.5 |

El pico absoluto y el RMS se calculan sobre las **512 muestras actuales**, no
sobre la ventana solapada. Un bloque con RMS menor o igual al mínimo no aporta
evidencia positiva. El epsilon numérico (`1e-12`) evita divisiones y logaritmos
inválidos; cumple una función distinta del RMS mínimo. Si aparecen NaN o infinitos,
la mitad correspondiente se sustituye por ceros solo en la copia de análisis.
Ninguna ventana que incluya esa mitad aporta evidencia espectral positiva, y ese
bloque tampoco aporta evidencia impulsiva. El audio transmitido no se modifica.

Para tonal y red solo cuentan máximos fuera de la protección que superen su
umbral local. Cada familia busca múltiplos de 50 o 60 Hz a distancia máxima de un
bin, cuenta como máximo un pico por armónico y cada pico una sola vez por familia.
Ambas familias mantienen confirmaciones separadas. Si las dos están confirmadas,
gana la de más armónicos, después la de mayor suma de magnitudes y finalmente
50 Hz. El pico publicado es el armónico más fuerte de esa familia.

Cuando una familia reúne tres armónicos instantáneos, sus picos se excluyen del
candidato tonal independiente desde ese análisis, antes de confirmar la familia.
El resto compite por magnitud con tolerancia tonal de un bin y tres confirmaciones.
Un tono publicado que desaparece conserva su frecuencia y contraste durante las
dos primeras ausencias; se retira en la tercera. Las familias conservan igualmente
su último pico hasta retirarse. Un patrón compatible con red no prueba su origen
eléctrico: una señal útil armónica fuera de la protección puede confundirse.

El detector impulsivo confirma cuando al menos dos comparaciones de cresta de los
últimos tres bloques superan el umbral. Se retira cuando deja de existir esa
mayoría, sin sumar tres ausencias adicionales.

La banda ancha evalúa **todo 100–3000 Hz, incluso la protección**, con las reglas
de ocupación y planitud de la tabla. La planitud es la media geométrica dividida
por la aritmética del piso. Exige tres análisis completos y tiene preferencia
sobre banda limitada cuando ambas están confirmadas.

La banda limitada marca el piso que supera su umbral fuera de la protección.
Une huecos de hasta dos bins sin cruzar la protección ni los extremos de análisis,
descarta regiones menores de ocho bins y elige la de mayor energía espectral.
En empate gana la de menor frecuencia inicial. Para confirmar tres análisis
consecutivos, la intersección de cada pareja de regiones debe cubrir al menos la
mitad de la menor. Los límites publicados son los centros de los bins extremos;
se conservan durante la retirada y no se reemplazan por candidatos sin confirmar.
No se decide banda ancha por superar una anchura fija de 1 kHz.

Un **cambio real** de banda protegida borra todas las historias y la clasificación
publicada; repetir la misma banda las conserva. Los ajustes de umbral también
reinician la clasificación. Ninguno reinicia la adquisición ni la ventana de
audio. El calentamiento vuelve a contar tres análisis completos válidos.

La distribución espectral no distingue perfectamente ruido ancho de señal útil
ancha. P6 se evalúa con estas mismas reglas, sin identificar archivos ni memorizar
señales: mezclas de ruidos o señales útiles similares pueden ser ambiguas.

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
muestra del próximo INPUT. Usa fs=8000, N=1024, H=512, método=0, opcode=1 y
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

## Validación

La implementación de la tanda 2 se revisa sin compilar ni cargar firmware.
No se ejecutaron comprobaciones con los WAV P1–P5 porque `simulacion/` quedó fuera
del alcance autorizado. Pasaron `git diff --check`, la comprobación de alcance y
base de rama, y la comparación estática de las funciones de temporizador, UART,
INPUT y CONTROL CONFIG con `development`. `clang-format` pudo analizar los tres
archivos C++ modificados sin indicar formato incompleto; esto no comprueba tipos
ni sustituye una compilación.

Se ejecutó además una **referencia numérica independiente en Python**, temporal
y en memoria, con once escenarios sintéticos. Usó 1024 muestras, sqrt-Hann,
mediana local de 31 bins y las reglas de características anteriores. No ejecutó
el C++ ni sus historias de persistencia. Los resultados siguientes corresponden
a candidatos instantáneos de esa referencia, no a clasificaciones del ESP32:

| Entrada sintética | Resultado de la referencia en PC |
|---|---|
| Silencio, tono de amplitud `1e-6` y bloque con NaN | Sin actividad positiva |
| Tono de 2150 Hz | Pico tonal 2148.4375 Hz |
| Tonos 1250, 1350, 1450 Hz | Tres armónicos de 50 Hz; sin candidato tonal independiente |
| Tonos 1260, 1380, 1500 Hz | Tres armónicos de 60 Hz, dos de 50 Hz; sin tonal independiente |
| Tonos 1250 y 1350 Hz | Dos armónicos; no cumplen mínimo de familia |
| Tonos protegidos 300, 700, 1100 Hz | Cero armónicos contados y sin tonal independiente; región candidata 1203.125–1414.0625 Hz |
| Ruido gaussiano con protección 100–3000 | Cumple ocupación y planitud de banda ancha |
| Ruido con bins 256–358, de 2000 a 2796.875 Hz | Región candidata limitada 1898.4375–3000 Hz; sin banda ancha |
| Un impulso en el bloque actual | Cresta 22.6274; también cumple características de banda ancha |

Los tonos usaron amplitud 0.1 por componente, salvo el de nivel bajo. El ruido
gaussiano usó desviación 0.1 y `random.Random(572602)`; a continuación, el mismo
generador produjo fases uniformes para bins 256–358 de magnitud 1 y sus conjugados,
seguidos de transformada inversa normalizada. El impulso tuvo amplitud 0.5.

La referencia muestra dos limitaciones de los valores iniciales: la fuga de tonos
útiles protegidos puede elevar el piso fuera de la protección y formar una región
espuria, y los bordes de una banda de ruido pueden ensancharse considerablemente.
Se conservan las reglas y umbrales del plan; no se ajustaron para ocultar esos
resultados. La coincidencia de un impulso con banda ancha se resuelve por la
prioridad y persistencia, que aún requieren comprobar el firmware.

Las expectativas P1–P5 siguientes son pruebas pendientes, no resultados medidos
del firmware ni de la referencia sintética en PC.

Recibir UART1 con [receptor_nodo1.py](../../herramientas_pc/README.md), usando
`--enlace n2 --solo-protocolo` y el puerto del adaptador, o conectar directamente
la placa de los nodos 2 y 3. Verificar INPUT + DIAG sin errores en ambos modos.

En ADC, comprobar en reposo x alrededor de 1340 mV, frecuencias próximas a
24000 Hz y 8000 Hz, y cero desbordes del pool. Reproducir un tono fuera de la
banda protegida (por ejemplo, 2150 Hz) o P1 desde el parlante de la laptop hacia
el micrófono y verificar detección tras calentamiento y persistencia. Revisar
los tiempos y contadores con `vista todo`.

Para la etapa posterior autorizada, conservar los audios y condiciones originales,
probar las tres semillas de cada caso y registrar por bloque tipos, picos,
regiones y transiciones. Una referencia independiente en PC debe usar solo el
canal 0 (`x`) del WAV estéreo y distinguirse de los resultados del ESP32; el canal
1 es la señal limpia y no se entrega al clasificador.

| Caso pendiente | Protección | Observación esperada, sin garantía previa |
|---|---|---|
| P1 | 100–1200 | Tonal próximo a 2148.4375 Hz, filtro 2 y método 1 |
| P2 | 100–1200 | Banda limitada próxima a 2000–2800; tonos protegidos no cuentan como red |
| P3 | 100–3000 | Banda ancha, filtro 1 y método 2, aun con protección completa |
| P4 | 100–1200 | Impulsivo en bloques con evidencia, sin exigir tipo 5 en todo el audio |
| P5 | 100–1200 | Región parcial por encima de 1200 o ausencia; no reconstruir 900–1300 |
| P5 adicional, mismo audio | 100–800 | Registrar si el tono útil de 1100 Hz gana por prioridad |
| Silencio digital | Ambas bandas | Ninguno confirmado después de la retirada, sin divisiones inválidas |

Comprobar además con entradas sintéticas temporales familias de 50 y 60 Hz con
al menos tres armónicos fuera de la protección; uno o dos no deben confirmar red.
Verificar que 300, 700 y 1100 Hz protegidos no cuenten como red; comprobar la
retirada de un tono, cambios e invalidez de umbrales, RMS bajo, NaN/infinito,
mayoría impulsiva, retirada de regiones y prioridad ante categorías simultáneas.
Estas pruebas funcionales también quedan pendientes de ejecución del firmware.

En placa, repetir P1–P5 por el micrófono tres veces y registrar tiempos, pérdidas
y desbordes, además de clasificación y ajustes por consola. Una comprobación con
WAV no representa la respuesta del parlante, micrófono y circuito. Para P6 aplicar
las reglas generales y documentar ambigüedades. La clasificación no sustituye MSE,
SNR, energía, atenuación ni latencia; en P5 debe mostrarse el compromiso entre
reducir ruido y conservar señal útil.

Para validar CONFIG con las dos placas, seguir la prueba de banda y automático
del README de [nodo 2](../nodo2/README.md#prueba-de-banda-y-automático-con-dos-placas).

## Problemas conocidos

- **Subida lenta:** `upload_speed = 115200` en `platformio.ini`. A velocidades
  mayores la subida falló con esta placa.
- **Falla un include de ESP-DSP** (por ejemplo `dsps_fft2r.h`) después de cambiar
  dependencias: `pio run -t fullclean` y volver a compilar.
- **Basura en el monitor con el YP-05 conectado:** PlatformIO puede abrir el
  puerto equivocado. Indicar el puerto con `-p /dev/ttyUSB0`.
