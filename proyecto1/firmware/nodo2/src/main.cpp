#include <cstdio>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_err.h"
#include "esp_timer.h"
#include "recepcion.h"
#include "salida_dac.h"

extern "C" void app_main(void)
{
    gpio_config_t led = {};
    led.pin_bit_mask = 1ULL << GPIO_NUM_4;
    led.mode = GPIO_MODE_OUTPUT;
    led.intr_type = GPIO_INTR_DISABLE;
    ESP_ERROR_CHECK(gpio_config(&led));
    ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_4, 1));

    salida_dac_iniciar();
    recepcion_iniciar();
    printf("Nodo 2: UART1 RX GPIO19 TX GPIO18 sin uso, 921600 8N1, RX 16384 B | "
           "DAC GPIO25 8000 Hz APLL DMA 6x512 B, timeout 0 ms | LED GPIO4 | "
           "watchdog INPUT 200 ms | monitor UART0 115200\n");

    int64_t ultimo_resumen_us = esp_timer_get_time();
    int64_t ultimo_error_dac_us = -1;
    uint32_t desbordes_anteriores = 0;
    for (;;) {
        const bool hubo_bytes = recepcion_leer();
        const int64_t ahora_us = esp_timer_get_time();
        const bool error_rx = recepcion_actualizar(ahora_us);
        const auto& d = salida_dac_contadores();
        if (d.desbordes != desbordes_anteriores) {
            ultimo_error_dac_us = ahora_us;
            desbordes_anteriores = d.desbordes;
        }
        const bool error_dac = ultimo_error_dac_us >= 0 && ahora_us - ultimo_error_dac_us < 500000;
        ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_4, error_rx || error_dac ? 1 : 0));

        if (ahora_us - ultimo_resumen_us >= 1000000) {
            const auto& r = recepcion_contadores();
            printf("INPUT %llu | DIAG %llu | err_trama %llu | err_cobs %llu | "
                   "err_crc %llu | err_cabecera %llu | perdidos %llu | sesiones %llu | "
                   "DAC %llu B | desbordes_dac %lu\n",
                   (unsigned long long)r.input, (unsigned long long)r.diag,
                   (unsigned long long)r.err_trama, (unsigned long long)r.err_cobs,
                   (unsigned long long)r.err_crc, (unsigned long long)r.err_cabecera,
                   (unsigned long long)r.perdidos, (unsigned long long)r.sesiones,
                   (unsigned long long)d.bytes, (unsigned long)d.desbordes);
            ultimo_resumen_us = ahora_us;
        }
        // Un tick son 10 ms con la configuración actual; RX se drena antes de dormir.
        if (!hubo_bytes) vTaskDelay(1);
    }
}
