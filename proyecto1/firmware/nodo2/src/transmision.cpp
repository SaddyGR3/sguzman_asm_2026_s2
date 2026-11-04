#include "transmision.h"
#include "protocolo.h"
#include "driver/gpio.h"
#include "driver/uart.h"
#include "esp_err.h"
#include "esp_random.h"

constexpr size_t TAM_TX_DRIVER = 8192;
constexpr size_t MARGEN_TX = 64;

static uint8_t trabajo[R_INPUT];
static uint8_t cable[CABLE_INPUT];
static uint32_t sesion = 0;
static uint32_t secuencia = 0;
static uint64_t enviados = 0;
static uint64_t descartados = 0;

void transmision_iniciar()
{
    uart_config_t cfg = {};
    cfg.baud_rate = 921600;
    cfg.data_bits = UART_DATA_8_BITS;
    cfg.parity = UART_PARITY_DISABLE;
    cfg.stop_bits = UART_STOP_BITS_1;
    cfg.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    cfg.source_clk = UART_SCLK_DEFAULT;
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_2, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(UART_NUM_2, 17, 16, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    ESP_ERROR_CHECK(gpio_set_pull_mode(GPIO_NUM_16, GPIO_PULLUP_ONLY));
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_2, 256, TAM_TX_DRIVER, 0, nullptr, 0));

    sesion = esp_random();
    const uint8_t cero = 0;
    ESP_ERROR_CHECK(uart_write_bytes(UART_NUM_2, &cero, 1) == 1 ? ESP_OK : ESP_FAIL);
}

void transmision_enviar(const float* muestras, uint64_t first_sample)
{
    const uint32_t actual = secuencia++;
    const uint16_t flags = actual == 0 ? FLAG_REINICIO : 0;
    const size_t largo = armar_fir_out(muestras, flags, sesion, actual, first_sample,
                                     trabajo, cable);
    size_t libre = 0;
    ESP_ERROR_CHECK(uart_get_tx_buffer_free_size(UART_NUM_2, &libre));
    if (libre < largo + MARGEN_TX) {
        ++descartados;
        return;
    }
    if (uart_write_bytes(UART_NUM_2, cable, largo) == static_cast<int>(largo)) {
        ++enviados;
    } else {
        ++descartados;
    }
}

uint64_t transmision_enviados()
{
    return enviados;
}

uint64_t transmision_descartados()
{
    return descartados;
}
