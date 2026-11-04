#include "recepcion.h"
#include "protocolo.h"
#include "salida_dac.h"
#include "driver/gpio.h"
#include "driver/uart.h"
#include "esp_err.h"
#include "esp_timer.h"

constexpr int TAM_RX_DRIVER = 16384;
constexpr int64_t AUSENCIA_INPUT_US = 200000;
constexpr int64_t ERROR_RECIENTE_US = 500000;

static uint8_t lectura[1024];
static uint8_t trama[CABLE_INPUT];
static uint8_t decodificado[R_INPUT];
static size_t acumulados = 0;
static bool sincronizado = false;
static bool descartando = false;
static bool tiene_sesion = false;
static uint32_t sesion = 0;
static uint32_t secuencia = 0;
static bool tiene_input = false;
static bool silencio_enviado = false;
static int64_t ultimo_input_us = 0;  // al iniciar sirve de referencia para el watchdog
static int64_t ultimo_error_us = -1;
static ContadoresRecepcion contadores;
static void (*al_recibir_input)(const uint8_t*, uint64_t) = nullptr;

void recepcion_iniciar(void (*procesar_input)(const uint8_t*, uint64_t))
{
    al_recibir_input = procesar_input;
    crc32_iniciar();
    uart_config_t cfg = {};
    cfg.baud_rate = 921600;
    cfg.data_bits = UART_DATA_8_BITS;
    cfg.parity = UART_PARITY_DISABLE;
    cfg.stop_bits = UART_STOP_BITS_1;
    cfg.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    cfg.source_clk = UART_SCLK_DEFAULT;
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_1, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(UART_NUM_1, 18, 19, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    // Evita recibir ruido cuando se desconecta el cable.
    ESP_ERROR_CHECK(gpio_set_pull_mode(GPIO_NUM_19, GPIO_PULLUP_ONLY));
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_1, TAM_RX_DRIVER, 0, 0, nullptr, 0));
    ultimo_input_us = esp_timer_get_time();
}

static void registrar_error(uint64_t& contador)
{
    ++contador;
    ultimo_error_us = esp_timer_get_time();
}

static bool cabecera_valida(const Cabecera& c, size_t n)
{
    if (c.magic != PROTO_MAGIC || c.version != PROTO_VERSION ||
        c.src != NODO_1 || c.dst != NODO_2 ||
        c.payload_bytes != n - TAM_CABECERA - TAM_CRC) return false;

    if (c.tipo == TIPO_INPUT) {
        return c.sample_count == MUESTRAS_BLOQUE && c.format == FORMATO_FLOAT32 &&
               c.channels == 1 && c.payload_bytes == TAM_DATOS_INPUT;
    }
    if (c.tipo == TIPO_DIAG) {
        return c.sample_count == 0 && c.format == FORMATO_META &&
               c.channels == 0 && c.payload_bytes == TAM_DIAG;
    }
    return false;
}

static void seguir_secuencia(const Cabecera& c)
{
    if (!tiene_sesion || c.session_id != sesion) {
        tiene_sesion = true;
        sesion = c.session_id;
        secuencia = c.sequence;
        ++contadores.sesiones;
        return;
    }

    // Resta modular: también funciona al pasar de UINT32_MAX a cero.
    // Duplicados y secuencias anteriores no retroceden el seguimiento ni suman pérdidas.
    const uint32_t salto = c.sequence - secuencia;
    if (salto > 0 && salto < 0x80000000u) {
        if (salto > 1) {
            contadores.perdidos += salto - 1;
            ultimo_error_us = esp_timer_get_time();
        }
        secuencia = c.sequence;
    }
}

static void procesar_trama()
{
    const size_t n = cobs_decodificar(trama, acumulados, decodificado, sizeof(decodificado));
    if (n == 0) {
        registrar_error(contadores.err_cobs);
        return;
    }
    if (n < TAM_CRC) {
        registrar_error(contadores.err_cabecera);
        return;
    }
    if (crc32(decodificado, n - TAM_CRC) != get_u32(decodificado + n - TAM_CRC)) {
        registrar_error(contadores.err_crc);
        return;
    }
    if (n < TAM_CABECERA + TAM_CRC) {
        registrar_error(contadores.err_cabecera);
        return;
    }
    const Cabecera c = leer_cabecera(decodificado);
    if (!cabecera_valida(c, n)) {
        registrar_error(contadores.err_cabecera);
        return;
    }

    seguir_secuencia(c);
    if (c.tipo == TIPO_INPUT) {
        ++contadores.input;
        tiene_input = true;
        ultimo_input_us = esp_timer_get_time();
        silencio_enviado = false;
        al_recibir_input(decodificado + TAM_CABECERA, c.first_sample);
    } else {
        ++contadores.diag;
    }
}

static void consumir(const uint8_t* datos, size_t n)
{
    for (size_t k = 0; k < n; ++k) {
        const uint8_t b = datos[k];
        if (b == 0) {
            // El primer delimitador cierra el fragmento inicial, sin contarlo como error.
            if (sincronizado && !descartando && acumulados > 0) procesar_trama();
            sincronizado = true;
            descartando = false;
            acumulados = 0;
        } else if (!sincronizado || descartando) {
            continue;
        } else if (acumulados == sizeof(trama)) {
            registrar_error(contadores.err_trama);
            descartando = true;
            acumulados = 0;
        } else {
            trama[acumulados++] = b;
        }
    }
}

bool recepcion_leer()
{
    bool recibidos = false;
    for (;;) {
        const int n = uart_read_bytes(UART_NUM_1, lectura, sizeof(lectura), 0);
        if (n <= 0) return recibidos;
        recibidos = true;
        consumir(lectura, static_cast<size_t>(n));
    }
}

bool recepcion_actualizar(int64_t ahora_us)
{
    const bool vencido = ahora_us - ultimo_input_us >= AUSENCIA_INPUT_US;
    if (vencido && !silencio_enviado) {
        // Un único intento por ausencia, incluso si no cabe todo el bloque.
        silencio_enviado = true;
        salida_dac_silencio();
    }
    return !tiene_input || vencido ||
           (ultimo_error_us >= 0 && ahora_us - ultimo_error_us < ERROR_RECIENTE_US);
}

const ContadoresRecepcion& recepcion_contadores()
{
    return contadores;
}
