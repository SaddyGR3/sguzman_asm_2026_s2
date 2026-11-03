#include <cstdio>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_err.h"
#include "esp_timer.h"
#include "filtros.h"
#include "protocolo.h"
#include "recepcion.h"
#include "salida_dac.h"

enum class ModoFiltro { SIN_FILTRO, FIR, NOTCH };
constexpr ModoFiltro MODO_INICIAL = ModoFiltro::SIN_FILTRO;
constexpr gpio_num_t PIN_BOTON = GPIO_NUM_32;

static ModoFiltro modo = MODO_INICIAL;
static int boton_anterior = 1;
static float salida[MUESTRAS_BLOQUE];

static const char* nombre_modo()
{
    static const char* const nombres[] = {"SIN FILTRO", "FIR", "NOTCH"};
    return nombres[static_cast<int>(modo)];
}

static void procesar_input(const uint8_t* datos)
{
    // Una lectura del botón por INPUT, incluso si RX trae varios paquetes juntos.
    const int boton_actual = gpio_get_level(PIN_BOTON);
    if (boton_anterior == 1 && boton_actual == 0) {
        switch (modo) {
            case ModoFiltro::SIN_FILTRO: modo = ModoFiltro::FIR; break;
            case ModoFiltro::FIR: modo = ModoFiltro::NOTCH; break;
            case ModoFiltro::NOTCH: modo = ModoFiltro::SIN_FILTRO; break;
        }
        printf("Filtro: %s\n", nombre_modo());
    }
    boton_anterior = boton_actual;

    for (size_t k = 0; k < MUESTRAS_BLOQUE; ++k) {
        const float x = get_f32(datos + 4 * k);
        float fir, notch;
        filtros_procesar(x, fir, notch);
        switch (modo) {
            case ModoFiltro::SIN_FILTRO: salida[k] = x; break;
            case ModoFiltro::FIR: salida[k] = fir; break;
            case ModoFiltro::NOTCH: salida[k] = notch; break;
        }
    }
    salida_dac_input(salida);
}

extern "C" void app_main(void)
{
    gpio_config_t led = {};
    led.pin_bit_mask = 1ULL << GPIO_NUM_4;
    led.mode = GPIO_MODE_OUTPUT;
    led.intr_type = GPIO_INTR_DISABLE;
    ESP_ERROR_CHECK(gpio_config(&led));
    ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_4, 1));

    gpio_config_t boton = {};
    boton.pin_bit_mask = 1ULL << PIN_BOTON;
    boton.mode = GPIO_MODE_INPUT;
    boton.pull_up_en = GPIO_PULLUP_ENABLE;
    boton.pull_down_en = GPIO_PULLDOWN_DISABLE;
    boton.intr_type = GPIO_INTR_DISABLE;
    ESP_ERROR_CHECK(gpio_config(&boton));
    boton_anterior = gpio_get_level(PIN_BOTON);

    filtros_iniciar();
    salida_dac_iniciar();
    recepcion_iniciar(procesar_input);
    const auto& c = filtros_coeficientes();
    printf("Nodo 2: UART1 RX GPIO19 TX GPIO18 sin uso, 921600 8N1, RX 16384 B | "
           "DAC GPIO25 8000 Hz APLL DMA 6x512 B, timeout 0 ms | LED GPIO4 | "
           "watchdog INPUT 200 ms | monitor UART0 115200 | Filtro: %s | botón GPIO32 | "
           "FIR primeros 3 [%.12f, %.12f, %.12f] | "
           "notch b [%.12f, %.12f, %.12f] a [%.12f, %.12f, %.12f]\n",
           nombre_modo(), c.fir[0], c.fir[1], c.fir[2],
           c.b[0], c.b[1], c.b[2], c.a[0], c.a[1], c.a[2]);

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
            printf("Filtro: %s | INPUT %llu | DIAG %llu | err_trama %llu | err_cobs %llu | "
                   "err_crc %llu | err_cabecera %llu | perdidos %llu | sesiones %llu | "
                   "DAC %llu B | desbordes_dac %lu\n",
                   nombre_modo(),
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
