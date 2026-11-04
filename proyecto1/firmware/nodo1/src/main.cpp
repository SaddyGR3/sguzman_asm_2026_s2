#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <cstring>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_err.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "driver/dac_continuous.h"
#include "driver/gpio.h"
#include "driver/uart.h"
#include "driver/uart_vfs.h"
#include "espectro.h"
#include "diagnostico.h"
#include "generador.h"
#include "protocolo.h"
#include "entrada_adc.h"

// Luis cambia esta constante para probar la entrada por cable en GPIO36.
enum class Fuente { GENERADOR, ADC };
constexpr Fuente FUENTE_ENTRADA = Fuente::ADC;

// true: lazo de prueba con puentes GPIO18->GPIO19 y GPIO17->GPIO16 en la misma placa.
// false: para la PC, no se copia al anillo, no se lee RX y no se compara.
constexpr bool PRUEBA_LAZO = false;

constexpr bool SALIDA_DAC = true;
constexpr gpio_num_t PIN_BOTON_DAC = GPIO_NUM_32;
constexpr bool DAC_SENAL_LIMPIA_INICIAL = false;
constexpr uint32_t FRECUENCIA_DAC = 8000;
constexpr uint32_t BUFERES_DMA_DAC = 6;
constexpr size_t TAM_BUFER_DMA_DAC = 512;  // bytes físicos: 256 muestras por búfer

static bool dac_senal_limpia = DAC_SENAL_LIMPIA_INICIAL;

constexpr int N_FFT = 1024;      // dos bloques de 512
static float banda_lo = 100.0f, banda_hi = 1200.0f;
enum class Vista { DIAG, TODO };
static Vista vista = Vista::DIAG;

// 512 muestras a 8 kHz = 64 ms: el temporizador marca el ritmo de un bloque.
constexpr uint64_t PERIODO_US = 64000;
constexpr uint32_t BLOQUES_VENTANA = 16;   // un resumen cada ~1.024 s

constexpr int BAUDIOS = 921600;
constexpr size_t TAM_ANILLO = 16384;       // potencia de 2: el índice se envuelve con una máscara
constexpr size_t MARGEN_TX = 64;

static TaskHandle_t tarea_principal = nullptr;   // la lee el callback del temporizador

// El callback corre en la tarea del temporizador (ESP_TIMER_TASK) y no en una
// interrupción, por eso se usa xTaskNotifyGive() y no la versión FromISR.
static void aviso_bloque(void*)
{
    xTaskNotifyGive(tarea_principal);
}

static float x[HOP];                    // señal contaminada: x = s + i
static float s_util[HOP];               // señal útil (referencia limpia)
static float i_interf[HOP];             // interferencia
static float xs[2 * HOP];               // x y s intercalados para INPUT_REF

static dac_continuous_handle_t dac = nullptr;
static uint8_t salida_dac[HOP];
static uint64_t bytes_dac = 0;            // bytes de 8 bits aceptados (acumulado)
static uint32_t desbordes_dac = 0;        // bloques incompletos (acumulado)

// APLL permite 8 kHz en el ESP32. El driver expande cada código a 16 bits
// con CONFIG_DAC_DMA_AUTO_16BIT_ALIGN: los seis búferes guardan tres bloques.
static void iniciar_dac()
{
    dac_continuous_config_t cfg = {};
    cfg.chan_mask = DAC_CHANNEL_MASK_CH0;   // GPIO25
    cfg.desc_num = BUFERES_DMA_DAC;
    cfg.buf_size = TAM_BUFER_DMA_DAC;
    cfg.freq_hz = FRECUENCIA_DAC;
    cfg.offset = 0;
    cfg.clk_src = DAC_DIGI_CLK_SRC_APLL;
    cfg.chan_mode = DAC_CHANNEL_MODE_SIMUL;
    ESP_ERROR_CHECK(dac_continuous_new_channels(&cfg, &dac));
    ESP_ERROR_CHECK(dac_continuous_enable(dac));
}

// Copia al DMA sin esperar espacio. Si no cabe todo, descarta el resto del
// bloque para no retrasar el siguiente periodo ni los envíos por UART.
static void escribir_dac()
{
    const float* senal = dac_senal_limpia ? s_util : x;
    for (int k = 0; k < HOP; ++k) {
        int codigo = static_cast<int>(roundf(127.5f + 127.5f * senal[k]));
        if (codigo < 0) codigo = 0;
        if (codigo > 255) codigo = 255;
        salida_dac[k] = static_cast<uint8_t>(codigo);
    }

    size_t escritos = 0;
    const esp_err_t error = dac_continuous_write(dac, salida_dac, sizeof(salida_dac),
                                                &escritos, 0);
    bytes_dac += escritos;
    if (escritos < sizeof(salida_dac)) ++desbordes_dac;
    if (error != ESP_ERR_TIMEOUT) ESP_ERROR_CHECK(error);
}

static void imprimir_diagnostico(const ResultadoDiagnostico& r)
{
    printf("banda protegida %.1f %.1f Hz | parcial %u calentamiento %u | tipo %u "
           "pico_Hz %.4f | candidato M %.6g piso local %.6g contraste contra piso %.2f dB | "
           "piso_resumen %.6g | análisis %lu us\n",
           banda_lo, banda_hi, r.parcial ? 1u : 0u, static_cast<unsigned>(r.calentamiento),
           static_cast<unsigned>(r.tipo_ruido), r.pico_hz, r.magnitud_candidato,
           r.piso_local, r.contraste_db, r.piso_resumen, (unsigned long)r.tiempo_us);
}

static void imprimir_linea_diag(const ResultadoDiagnostico& r, const ResumenAdc* adc,
                                uint32_t desbordes, uint32_t overruns, uint32_t saturaciones)
{
    printf("DIAG | banda %g-%g Hz | tipo %u %s", banda_lo, banda_hi,
           static_cast<unsigned>(r.tipo_ruido), r.tipo_ruido == 1 ? "tonal" : "ninguno");
    if (r.tipo_ruido == 1) {
        printf(" | pico %.1f Hz", r.pico_hz);
        if (r.contraste_db >= 0.0f) printf(" | contraste %.1f dB", r.contraste_db);
        else printf(" | contraste --");
    } else {
        printf(" | pico -- | contraste --");
    }
    if (r.parcial || r.calentamiento) printf(" | calentando");
    if (adc != nullptr) printf(" | ADC %d-%d mV", adc->mv_min, adc->mv_max);
    if (desbordes || overruns || saturaciones) {
        printf(" | ALERTA desbordes %lu overruns %lu saturaciones %lu",
               (unsigned long)desbordes, (unsigned long)overruns, (unsigned long)saturaciones);
    }
    printf("\n");
}

static void ayuda_consola()
{
    printf(">> comando no reconocido. Comandos: banda <lo> <hi>, estado, vista diag|todo\n");
}

static void comando_consola(const char* linea)
{
    char comando[16], modo[16], extra;
    float lo, hi;
    if (sscanf(linea, " %15s", comando) != 1) return;
    if (strcmp(comando, "banda") == 0 &&
        sscanf(linea, " %15s %f %f %c", comando, &lo, &hi, &extra) == 3) {
        if (std::isfinite(lo) && std::isfinite(hi) && lo >= 0.0f && lo < hi && hi <= 4000.0f) {
            banda_lo = lo;
            banda_hi = hi;
            diagnostico_banda(lo, hi);
            printf(">> banda protegida: %g-%g Hz\n", lo, hi);
        } else {
            ayuda_consola();
        }
    } else if (strcmp(comando, "vista") == 0 &&
               sscanf(linea, " %15s %15s %c", comando, modo, &extra) == 2 &&
               (strcmp(modo, "diag") == 0 || strcmp(modo, "todo") == 0)) {
        vista = strcmp(modo, "diag") == 0 ? Vista::DIAG : Vista::TODO;
        printf(">> vista: %s\n", vista == Vista::DIAG ? "diag" : "todo");
    } else if (strcmp(comando, "estado") == 0 &&
               sscanf(linea, " %15s %c", comando, &extra) == 1) {
        printf(">> banda protegida: %g-%g Hz\n>> vista: %s\n>> ",
               banda_lo, banda_hi, vista == Vista::DIAG ? "diag" : "todo");
        imprimir_linea_diag(diagnostico_resultado(), nullptr, 0, 0, 0);
    } else {
        ayuda_consola();
    }
}

static void leer_consola()
{
    static char linea[96];
    static size_t usados = 0;
    static bool descartar = false;
    static uint8_t datos[64];
    static int posicion = 0, recibidos = 0;
    // Lectura acotada y sin espera: no drena indefinidamente la consola.
    if (posicion == recibidos) {
        const int n = uart_read_bytes(UART_NUM_0, datos, sizeof(datos), 0);
        if (n <= 0) return;
        posicion = 0;
        recibidos = n;
    }
    while (posicion < recibidos) {
        const char c = static_cast<char>(datos[posicion++]);
        if (c == '\r' || c == '\n') {
            const bool hubo_comando = descartar || usados > 0;
            if (descartar) ayuda_consola();
            else if (usados > 0) {
                linea[usados] = '\0';
                comando_consola(linea);
            }
            usados = 0;
            descartar = false;
            // Una respuesta por bloque; conserva el resto para la próxima vuelta.
            if (hubo_comando) return;
        } else if (!descartar) {
            if (c == '\b' || c == 127) {
                if (usados > 0) --usados;
            } else if (c >= 32 && c < 127) {
                if (usados + 1 < sizeof(linea)) linea[usados++] = c;
                else descartar = true;
            }
        }
    }
}

// Búferes de paquetes (estáticos: la pila de app_main es pequeña).
static uint8_t trabajo[TAM_TRABAJO];          // cabecera + datos + CRC, antes de COBS
static uint8_t sal_input[CABLE_INPUT];
static uint8_t sal_ref[CABLE_INPUT_REF];
static uint8_t sal_diag2[CABLE_DIAG];         // DIAG hacia el nodo 2
static uint8_t sal_diag3[CABLE_DIAG];         // DIAG hacia el nodo 3
static uint8_t diag64[TAM_DIAG];
static uint32_t session_id = 0;

// Un enlace UART hacia otro nodo, con sus contadores y, para el lazo, el anillo
// con una copia de lo enviado.
struct Enlace {
    const char* nombre;
    uart_port_t puerto;
    uint64_t enviados = 0;        // bytes escritos en el búfer del driver (acumulado)
    uint32_t desbordes_tx = 0;    // bloques descartados por falta de espacio (acumulado)
    uint32_t esc_max_us = 0;      // máximo tiempo de escritura de la ventana
    // Lazo de prueba.
    uint8_t anillo[TAM_ANILLO];
    uint32_t pos_esc = 0;         // dónde se copia el siguiente byte enviado
    uint32_t pos_lect = 0;        // contra qué byte se compara el siguiente recibido
    uint64_t recibidos = 0;
    uint32_t diferencias = 0;
    bool desincronizado = false;

    Enlace(const char* n, uart_port_t p) : nombre(n), puerto(p) {}   // el anillo queda en .bss
};

static Enlace enlace_n2("N2", UART_NUM_1);
static Enlace enlace_n3("N3", UART_NUM_2);
static uint8_t buf_rx[1024];      // búfer de lectura compartido por los dos enlaces

// Configura una UART a 921600 8N1 sin control de flujo, sin cola de eventos.
static void iniciar_uart(uart_port_t puerto, int tx, int rx, int buf_tx, int buf_rx_tam)
{
    uart_config_t cfg = {};
    cfg.baud_rate = BAUDIOS;
    cfg.data_bits = UART_DATA_8_BITS;
    cfg.parity = UART_PARITY_DISABLE;
    cfg.stop_bits = UART_STOP_BITS_1;
    cfg.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    cfg.source_clk = UART_SCLK_DEFAULT;
    ESP_ERROR_CHECK(uart_param_config(puerto, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(puerto, tx, rx, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    // Pull-up en RX, después de uart_set_pin: con PRUEBA_LAZO = false los RX quedan sin
    // conectar, y sin pull-up captan ruido que la UART interpreta como bytes y errores.
    ESP_ERROR_CHECK(gpio_set_pull_mode(static_cast<gpio_num_t>(rx), GPIO_PULLUP_ONLY));
    ESP_ERROR_CHECK(uart_driver_install(puerto, buf_rx_tam, buf_tx, 0, NULL, 0));
}

// Copia al anillo lo que se acaba de escribir, en el mismo orden.
static void copiar_al_anillo(Enlace& e, const uint8_t* datos, size_t n)
{
    for (size_t k = 0; k < n; ++k) {
        e.anillo[e.pos_esc] = datos[k];
        e.pos_esc = (e.pos_esc + 1) & (TAM_ANILLO - 1);
    }
}

// Envía un bloque (datos + DIAG) sin bloquear: si no hay espacio en el búfer de TX
// se descarta completo. uart_write_bytes copia al búfer del driver y vuelve, así que
// los búferes de salida se pueden reutilizar en el bloque siguiente.
static void enviar_bloque(Enlace& e, const uint8_t* datos, size_t l1,
                          const uint8_t* diag, size_t l2)
{
    const int64_t t0 = esp_timer_get_time();
    size_t libre = 0;
    ESP_ERROR_CHECK(uart_get_tx_buffer_free_size(e.puerto, &libre));

    // El margen de 64 B cubre la descripción (20 B), los encabezados (8 B por trozo) y el
    // relleno a múltiplo de 4 de las dos escrituras, que la función no descuenta del todo.
    if (libre >= l1 + l2 + MARGEN_TX) {
        if (l1 > 0) uart_write_bytes(e.puerto, datos, l1);
        uart_write_bytes(e.puerto, diag, l2);
        const int64_t t1 = esp_timer_get_time();
        const uint32_t escritura = static_cast<uint32_t>(t1 - t0);
        if (escritura > e.esc_max_us) e.esc_max_us = escritura;
        if (PRUEBA_LAZO) {
            copiar_al_anillo(e, datos, l1);
            copiar_al_anillo(e, diag, l2);
        }
        e.enviados += l1 + l2;
    } else {
        // Sin reintento: el audio vencido se descarta. Los sequence ya asignados dejan un
        // salto que el receptor cuenta como pérdida.
        ++e.desbordes_tx;
        const uint32_t escritura = static_cast<uint32_t>(esp_timer_get_time() - t0);
        if (escritura > e.esc_max_us) e.esc_max_us = escritura;
    }
}

// Lee lo que llegó por RX y lo compara con el anillo. No decodifica nada.
static void leer_lazo(Enlace& e)
{
    if (e.desincronizado) return;
    size_t disponible = 0;
    ESP_ERROR_CHECK(uart_get_buffered_data_len(e.puerto, &disponible));
    while (disponible > 0) {
        // Si lo pendiente supera el anillo, ya se sobrescribieron bytes sin comparar.
        if (static_cast<int64_t>(e.enviados - e.recibidos) > static_cast<int64_t>(TAM_ANILLO)) {
            e.desincronizado = true;
            printf("lazo %s desincronizado: pendientes %llu\n", e.nombre,
                   (unsigned long long)(e.enviados - e.recibidos));
            return;
        }
        const size_t pedir = disponible < sizeof(buf_rx) ? disponible : sizeof(buf_rx);
        const int n = uart_read_bytes(e.puerto, buf_rx, pedir, 0);
        if (n <= 0) break;
        for (int k = 0; k < n; ++k) {
            if (buf_rx[k] != e.anillo[e.pos_lect]) ++e.diferencias;
            e.pos_lect = (e.pos_lect + 1) & (TAM_ANILLO - 1);
        }
        e.recibidos += n;
        disponible -= n;
    }
    if (static_cast<int64_t>(e.enviados - e.recibidos) > static_cast<int64_t>(TAM_ANILLO)) {
        e.desincronizado = true;
        printf("lazo %s desincronizado: pendientes %llu\n", e.nombre,
               (unsigned long long)(e.enviados - e.recibidos));
    }
}

// INPUT hacia el nodo 2. Un arreglo de float no tiene relleno y el ESP32 es
// little-endian con IEEE 754, así que los bytes de x ya son los del protocolo.
static size_t paquete_input(uint32_t seq, uint16_t flags, uint64_t muestra)
{
    return armar_paquete(TIPO_INPUT, NODO_1, NODO_2, flags, session_id, seq, muestra,
                         HOP, FORMATO_FLOAT32, 1,
                         reinterpret_cast<const uint8_t*>(x), TAM_DATOS_INPUT,
                         trabajo, sal_input);
}

// INPUT_REF hacia el nodo 3: xs ya tiene x[0], s[0], x[1], s[1], ...
static size_t paquete_ref(uint32_t seq, uint16_t flags, uint64_t muestra)
{
    return armar_paquete(TIPO_INPUT_REF, NODO_1, NODO_3, flags | FLAG_REFERENCIA, session_id,
                         seq, muestra, HOP, FORMATO_FLOAT32, 2,
                         reinterpret_cast<const uint8_t*>(xs), TAM_DATOS_INPUT_REF,
                         trabajo, sal_ref);
}

// DIAG ya armado en diag64, hacia el destino indicado.
static size_t paquete_diag(uint8_t dst, uint32_t seq, uint64_t muestra, uint16_t flags, uint8_t* salida)
{
    return armar_paquete(TIPO_DIAG, NODO_1, dst, flags, session_id, seq, muestra,
                         0, FORMATO_META, 0, diag64, TAM_DIAG, trabajo, salida);
}

// Imprime los 32 B de la cabecera que quedaron en 'trabajo' (antes de COBS).
static void imprimir_cabecera(const char* nombre)
{
    printf("cabecera %s:", nombre);
    for (size_t k = 0; k < TAM_CABECERA; ++k) printf(" %02X", trabajo[k]);
    printf("\n");
}

// Pruebas del CRC y del COBS con vectores conocidos.
static void pruebas_protocolo()
{
    const uint8_t texto[] = {'1', '2', '3', '4', '5', '6', '7', '8', '9'};
    const uint32_t crc = crc32(texto, sizeof(texto));
    printf("CRC \"123456789\": %s (0x%08lX)\n", crc == 0xCBF43926u ? "PASS" : "FAIL",
           (unsigned long)crc);

    const uint8_t entrada[] = {0x11, 0x00, 0x22};
    const uint8_t esperado[] = {0x02, 0x11, 0x02, 0x22};
    uint8_t salida[8];
    const size_t n = cobs_codificar(entrada, sizeof(entrada), salida);
    bool ok = (n == sizeof(esperado));
    for (size_t k = 0; ok && k < n; ++k) ok = (salida[k] == esperado[k]);
    printf("COBS 11 00 22: %s (", ok ? "PASS" : "FAIL");
    for (size_t k = 0; k < n; ++k) printf(k ? " %02X" : "%02X", salida[k]);
    printf(")\n");
}

extern "C" void app_main(void)
{
    // Dos generadores: señal útil s e interferencia i. x = s + i.
    Generador gen_s;
    Generador gen_i;
    const float g = 0.26f;                       // escala común: pico < 0.8
    gen_s.configurar(0, 300.0f,  1.00f * g);
    gen_s.configurar(1, 700.0f,  0.55f * g);
    gen_s.configurar(2, 1100.0f, 0.30f * g);
    gen_i.configurar(0, 2150.0f, 1.18f * g);     // interferencia, SNR de 0 dB

    crc32_iniciar();                             // antes de cualquier CRC
    pruebas_protocolo();

    // Identificador del ensayo. Sin Wi-Fi esp_random() es pseudoaleatorio,
    // pero basta para distinguir una sesión de otra.
    session_id = esp_random();

    // Cabeceras del primer INPUT y del primer INPUT_REF (la cabecera no depende de los datos).
    paquete_input(0, FLAG_REINICIO, 0);
    imprimir_cabecera("INPUT");
    if (FUENTE_ENTRADA == Fuente::GENERADOR) {
        paquete_ref(0, FLAG_REINICIO, 0);
        imprimir_cabecera("INPUT_REF");
    }

    // UART1 -> nodo 2 y UART2 -> nodo 3. El anillo de TX del driver es NOSPLIT con ítem
    // máximo ALIGN4(tamaño/2) - 8: con 8 KB el tope es 4088 B y uart_get_tx_buffer_free_size
    // daría descartes falsos para el bloque de N3 (~4246 B); con 16 KB el tope es 8184 B.
    // En UART1 el INPUT (~2086 B) cabe con 8 KB.
    iniciar_uart(UART_NUM_1, 18, 19, 8192, 8192);
    iniciar_uart(UART_NUM_2, 17, 16, 16384, 8192);
    uint32_t baud1 = 0, baud2 = 0;
    ESP_ERROR_CHECK(uart_get_baudrate(UART_NUM_1, &baud1));
    ESP_ERROR_CHECK(uart_get_baudrate(UART_NUM_2, &baud2));
    printf("UART1 baud real %lu | UART2 baud real %lu\n", (unsigned long)baud1, (unsigned long)baud2);

    // Análisis común sobre la x transmitida; no avanza los generadores.
    ESP_ERROR_CHECK(espectro_iniciar(N_FFT));
    diagnostico_iniciar();
    diagnostico_banda(banda_lo, banda_hi);
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0, 1024, 4096, 0, nullptr, 0));
    // Los resúmenes se copian a TX; su transmisión a 115200 no frena el bloque.
    uart_vfs_dev_use_driver(UART_NUM_0);
    printf("Consola: banda <lo> <hi>, estado | banda protegida inicial 100 1200 Hz\n");

    // Vacía RX para que el ruido del arranque no cuente en el lazo.
    ESP_ERROR_CHECK(uart_flush_input(UART_NUM_1));
    ESP_ERROR_CHECK(uart_flush_input(UART_NUM_2));

    // Un único 0x00 en cada UART. Si el emisor se reinicia a mitad de un paquete, ese paquete
    // queda cortado sin su 0x00; el receptor juntaría esos restos con el primer paquete de la
    // sesión nueva (sequence 0, bandera 0x0004) y fallaría el CRC. El 0x00 cierra los restos
    // como una trama aparte y el receptor descarta las tramas vacías (resincronización COBS).
    static const uint8_t cero = 0;
    uart_write_bytes(enlace_n2.puerto, &cero, 1);
    uart_write_bytes(enlace_n3.puerto, &cero, 1);
    if (PRUEBA_LAZO) {
        // Para que el lazo siga dando 0 diferencias, el 0x00 también entra al anillo.
        copiar_al_anillo(enlace_n2, &cero, 1);
        copiar_al_anillo(enlace_n3, &cero, 1);
        enlace_n2.enviados += 1;
        enlace_n3.enviados += 1;
    }

    int boton_dac_anterior = 1;
    if (FUENTE_ENTRADA == Fuente::GENERADOR) {
        if (SALIDA_DAC) iniciar_dac();

        gpio_config_t boton_dac_cfg = {};
        boton_dac_cfg.pin_bit_mask = 1ULL << PIN_BOTON_DAC;
        boton_dac_cfg.mode = GPIO_MODE_INPUT;
        boton_dac_cfg.pull_up_en = GPIO_PULLUP_ENABLE;
        boton_dac_cfg.pull_down_en = GPIO_PULLDOWN_DISABLE;
        boton_dac_cfg.intr_type = GPIO_INTR_DISABLE;
        ESP_ERROR_CHECK(gpio_config(&boton_dac_cfg));
        boton_dac_anterior = gpio_get_level(PIN_BOTON_DAC);
        printf("DAC: señal %s (%c)\n", dac_senal_limpia ? "limpia" : "contaminada",
               dac_senal_limpia ? 's' : 'x');

        // Solo el generador usa el temporizador de 64 ms.
        tarea_principal = xTaskGetCurrentTaskHandle();
        esp_timer_create_args_t args = {};
        args.callback = aviso_bloque;
        args.dispatch_method = ESP_TIMER_TASK;
        args.name = "bloque";
        esp_timer_handle_t temporizador = nullptr;
        ESP_ERROR_CHECK(esp_timer_create(&args, &temporizador));
        ESP_ERROR_CHECK(esp_timer_start_periodic(temporizador, PERIODO_US));
    } else {
        printf("Fuente ADC: DAC local desactivado por uso compartido de I2S0; "
               "GPIO32 sin función; escuchar en nodo 2. UART2 solo DIAG, sin INPUT_REF.\n");
        entrada_adc_iniciar();
    }

    uint64_t first_sample = 0;   // índice de la primera muestra del siguiente bloque
    uint32_t overruns = 0;       // bloques que se retrasaron (acumulado)
    uint32_t bloques = 0;        // bloques generados (acumulado)

    // Un contador de secuencia por enlace; el primer paquete de cada enlace lleva reinicio.
    uint32_t seq_n2 = 0;
    uint32_t seq_n3 = 0;
    bool primer_n2 = true;
    bool primer_n3 = true;

    // Valores de la ventana de resumen; se reinician al imprimir.
    uint32_t v_bloques = 0;
    uint32_t v_periodos = 0;
    uint32_t v_per_min = 0xFFFFFFFF;
    uint32_t v_per_max = 0;
    uint64_t v_per_suma = 0;
    uint32_t v_gen_max = 0;
    uint32_t v_emp_max = 0;
    uint32_t v_analisis_max = 0;
    uint32_t desbordes_previos = 0, overruns_previos = 0, saturaciones_previas = 0;
    size_t cable_input = 0, cable_ref = 0, cable_diag = 0, cable_diag3 = 0;

    int64_t inicio_anterior = -1;   // la primera iteración no tiene periodo

    for (;;) {
        // Espera el aviso. Si n > 1, llegaron avisos mientras el bloque anterior
        // seguía en proceso: cada uno de más es un overrun.
        if (FUENTE_ENTRADA == Fuente::GENERADOR) {
            const uint32_t n = ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
            if (n > 1) overruns += n - 1;

            const int boton_dac_actual = gpio_get_level(PIN_BOTON_DAC);
            if (boton_dac_anterior == 1 && boton_dac_actual == 0) {
                dac_senal_limpia = !dac_senal_limpia;
                printf("DAC: señal %s (%c)\n", dac_senal_limpia ? "limpia" : "contaminada",
                       dac_senal_limpia ? 's' : 'x');
            }
            boton_dac_anterior = boton_dac_actual;
        }

        const int64_t inicio = esp_timer_get_time();
        if (inicio_anterior >= 0) {
            const uint32_t periodo = static_cast<uint32_t>(inicio - inicio_anterior);
            if (periodo < v_per_min) v_per_min = periodo;
            if (periodo > v_per_max) v_per_max = periodo;
            v_per_suma += periodo;
            ++v_periodos;
        }
        inicio_anterior = inicio;

        // Todos los paquetes del bloque llevan el índice de su primera muestra.
        const uint64_t muestra_inicial = first_sample;

        uint32_t procesamiento_adc_us = 0;
        if (FUENTE_ENTRADA == Fuente::GENERADOR) {
            // Generadores continuos: la fase pasa de un bloque al siguiente.
            gen_s.generar(s_util, HOP);
            gen_i.generar(i_interf, HOP);
            for (int k = 0; k < HOP; ++k) x[k] = s_util[k] + i_interf[k];
        } else {
            // Bloquea hasta adquirir 1536 muestras válidas y obtener 512 salidas.
            procesamiento_adc_us = entrada_adc_leer_bloque(x);
        }
        const int64_t fin_gen = esp_timer_get_time();
        const uint32_t duracion = FUENTE_ENTRADA == Fuente::GENERADOR
            ? static_cast<uint32_t>(fin_gen - inicio) : procesamiento_adc_us;
        if (duracion > v_gen_max) v_gen_max = duracion;

        leer_consola();
        const auto& diagnostico = diagnostico_procesar(x, muestra_inicial);
        if (diagnostico.tiempo_us > v_analisis_max) v_analisis_max = diagnostico.tiempo_us;
        uint16_t flags_analisis = 0;
        if (diagnostico.parcial) flags_analisis |= FLAG_VENTANA_PARCIAL;
        if (diagnostico.calentamiento) flags_analisis |= FLAG_CALENTAMIENTO;
        const int64_t inicio_empaquetado = esp_timer_get_time();

        first_sample += HOP;
        ++bloques;
        ++v_bloques;

        // Empaquetado: energía, intercalado de xs y los 4 paquetes.
        float energia = 0.0f;
        for (int k = 0; k < HOP; ++k) {
            energia += x[k] * x[k];
            if (FUENTE_ENTRADA == Fuente::GENERADOR) {
                xs[2 * k] = x[k];
                xs[2 * k + 1] = s_util[k];
            }
        }

        Diag d;
        d.fs = static_cast<uint32_t>(FS_HZ);
        d.N = N_FFT;
        d.H = HOP;
        d.pico_Hz = diagnostico.pico_hz;
        d.banda_lo = d.banda_hi = -1.0f;
        d.piso_resumen = diagnostico.piso_resumen;
        d.DC = diagnostico.dc;
        d.metodo = diagnostico.metodo;
        d.tipo_ruido = diagnostico.tipo_ruido;
        d.filtro_n2 = diagnostico.filtro_n2;
        d.calentamiento = diagnostico.calentamiento;
        d.energia = energia;
        d.tiempo_us = diagnostico.tiempo_us;
        d.overruns = overruns;
        if (FUENTE_ENTRADA == Fuente::ADC) {
            const ContadoresAdc adc = entrada_adc_contadores();
            d.perdidas = adc.desbordes_pool;
            d.saturaciones = adc.saturaciones;
        }
        d.inicio_ventana = diagnostico.inicio_ventana;
        armar_diag(d, diag64);

        // Enlace N1 -> N2: INPUT y DIAG.
        cable_input = paquete_input(seq_n2++, flags_analisis | (primer_n2 ? FLAG_REINICIO : 0), muestra_inicial);
        primer_n2 = false;
        cable_diag = paquete_diag(NODO_2, seq_n2++, muestra_inicial, flags_analisis, sal_diag2);

        // Enlace N1 -> N3: INPUT_REF y DIAG.
        if (FUENTE_ENTRADA == Fuente::GENERADOR) {
            cable_ref = paquete_ref(seq_n3++, flags_analisis | (primer_n3 ? FLAG_REINICIO : 0), muestra_inicial);
            primer_n3 = false;
        }
        cable_diag3 = paquete_diag(NODO_3, seq_n3++, muestra_inicial, flags_analisis, sal_diag3);

        const uint32_t empaquetado = static_cast<uint32_t>(esp_timer_get_time() - inicio_empaquetado);
        if (empaquetado > v_emp_max) v_emp_max = empaquetado;

        // Envío por UART: datos y después DIAG, un bloque por enlace.
        enviar_bloque(enlace_n2, sal_input, cable_input, sal_diag2, cable_diag);
        enviar_bloque(enlace_n3, FUENTE_ENTRADA == Fuente::GENERADOR ? sal_ref : nullptr,
                     cable_ref, sal_diag3, cable_diag3);

        // El DAC va después de ambos envíos y no espera espacio en el DMA.
        if (FUENTE_ENTRADA == Fuente::GENERADOR && SALIDA_DAC) escribir_dac();

        // Lazo de prueba: lee RX al final, así el envío (con plazo) va primero.
        if (PRUEBA_LAZO) {
            leer_lazo(enlace_n2);
            leer_lazo(enlace_n3);
        }

        // El resumen va al final: el printf cae en el tiempo libre del periodo.
        if (v_bloques == BLOQUES_VENTANA) {
            ContadoresAdc contadores_resumen;
            if (vista == Vista::DIAG) {
                ResumenAdc adc;
                if (FUENTE_ENTRADA == Fuente::ADC) {
                    adc = entrada_adc_resumen();
                    contadores_resumen = adc.acumulados;
                }
                imprimir_linea_diag(diagnostico_resultado(),
                    FUENTE_ENTRADA == Fuente::ADC ? &adc : nullptr,
                    contadores_resumen.desbordes_pool - desbordes_previos,
                    overruns - overruns_previos,
                    contadores_resumen.saturaciones - saturaciones_previas);
            } else {
                imprimir_diagnostico(diagnostico_resultado());
                printf("análisis max %lu us\n", (unsigned long)v_analisis_max);
                const uint32_t prom = v_periodos ? static_cast<uint32_t>(v_per_suma / v_periodos) : 0;
                printf("bloques %lu | first_sample %llu | periodo prom %lu us (min %lu, max %lu) | generar max %lu us | empaquetar max %lu us | cable INPUT %lu REF %lu DIAG %lu | pila libre %lu B | overruns %lu | DAC %llu B | desbordes_dac %lu\n",
                       (unsigned long)bloques, (unsigned long long)first_sample,
                       (unsigned long)prom, (unsigned long)v_per_min, (unsigned long)v_per_max,
                       (unsigned long)v_gen_max, (unsigned long)v_emp_max,
                       (unsigned long)cable_input, (unsigned long)cable_ref, (unsigned long)cable_diag,
                       (unsigned long)uxTaskGetStackHighWaterMark(NULL),
                       (unsigned long)overruns, (unsigned long long)bytes_dac,
                       (unsigned long)desbordes_dac);
                printf("tx N2 %llu B (esc max %lu us, desb %lu) | tx N3 %llu B (esc max %lu us, desb %lu)\n",
                       (unsigned long long)enlace_n2.enviados, (unsigned long)enlace_n2.esc_max_us,
                       (unsigned long)enlace_n2.desbordes_tx,
                       (unsigned long long)enlace_n3.enviados, (unsigned long)enlace_n3.esc_max_us,
                       (unsigned long)enlace_n3.desbordes_tx);
                if (FUENTE_ENTRADA == Fuente::ADC) {
                    const ResumenAdc adc = entrada_adc_resumen();
                    contadores_resumen = adc.acumulados;
                    printf("ADC crudo min %u max %u | mV min %d max %d | frecuencia ADC %.1f Hz "
                           "salida %.1f Hz | desbordes_pool %lu | saturaciones %lu | "
                           "procesamiento max %lu us (sin espera) | calibración max %lu us | "
                           "FIR+pasa altos+normalización max %lu us\n",
                           static_cast<unsigned>(adc.crudo_min), static_cast<unsigned>(adc.crudo_max),
                           adc.mv_min, adc.mv_max, adc.frecuencia_adc, adc.frecuencia_salida,
                           (unsigned long)adc.acumulados.desbordes_pool,
                           (unsigned long)adc.acumulados.saturaciones,
                           (unsigned long)adc.procesamiento_max_us,
                           (unsigned long)adc.calibracion_max_us,
                           (unsigned long)adc.filtrado_max_us);
                }
                if (PRUEBA_LAZO) {
                    printf("lazo N2: rx %llu dif %lu pend %lld | N3: rx %llu dif %lu pend %lld\n",
                           (unsigned long long)enlace_n2.recibidos, (unsigned long)enlace_n2.diferencias,
                           (long long)(enlace_n2.enviados - enlace_n2.recibidos),
                           (unsigned long long)enlace_n3.recibidos, (unsigned long)enlace_n3.diferencias,
                           (long long)(enlace_n3.enviados - enlace_n3.recibidos));
                }
            }
            // Referencia de alertas por periodo, también al mostrar vista todo.
            desbordes_previos = contadores_resumen.desbordes_pool;
            overruns_previos = overruns;
            saturaciones_previas = contadores_resumen.saturaciones;
            enlace_n2.esc_max_us = 0;
            enlace_n3.esc_max_us = 0;
            v_bloques = 0;
            v_periodos = 0;
            v_per_min = 0xFFFFFFFF;
            v_per_max = 0;
            v_per_suma = 0;
            v_gen_max = 0;
            v_emp_max = 0;
            v_analisis_max = 0;
        }
    }
}
