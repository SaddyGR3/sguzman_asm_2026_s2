#include "salida_dac.h"
#include "protocolo.h"
#include <cmath>
#include <cstring>
#include "driver/dac_continuous.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "sdkconfig.h"

#if !CONFIG_DAC_DMA_AUTO_16BIT_ALIGN
#error "Se requiere CONFIG_DAC_DMA_AUTO_16BIT_ALIGN para escribir códigos de 8 bits"
#endif

struct BloqueDac {
    uint8_t codigos[MUESTRAS_BLOQUE];
    bool ultimo;
};

static dac_continuous_handle_t dac = nullptr;
static QueueHandle_t pendientes = nullptr, terminadas = nullptr;
static ContadoresDac contadores;
static portMUX_TYPE cerrojo = portMUX_INITIALIZER_UNLOCKED;

// Solo la tarea DAC espera al hardware; UART y consola siguen en la tarea principal.
static void escribir(uint8_t* codigos)
{
    size_t posicion = 0;
    while (posicion < MUESTRAS_BLOQUE) {
        size_t escritos = 0;
        const esp_err_t error = dac_continuous_write(dac, codigos + posicion,
            MUESTRAS_BLOQUE - posicion, &escritos, 1000);
        portENTER_CRITICAL(&cerrojo);
        contadores.bytes += escritos;
        // Un timeout de un segundo excede ampliamente los 192 ms de DMA.
        if (error == ESP_ERR_TIMEOUT) ++contadores.desbordes;
        portEXIT_CRITICAL(&cerrojo);
        if (error != ESP_ERR_TIMEOUT) ESP_ERROR_CHECK(error);
        posicion += escritos;
    }
}

static void tarea_dac(void*)
{
    BloqueDac bloque;
    uint8_t silencio[MUESTRAS_BLOQUE];
    memset(silencio, 128, sizeof(silencio));
    for (;;) {
        if (xQueueReceive(pendientes, &bloque, 0) != pdTRUE) {
            escribir(silencio);
            continue;
        }
        escribir(bloque.codigos);
        if (bloque.ultimo) {
            // DMA: seis descriptores de 512 B físicos = tres bloques de audio.
            // Cuatro bloques silenciosos desplazan todo el audio y dejan 128 al final.
            for (int k = 0; k < 4; ++k) escribir(silencio);
            const uint8_t aviso = 1;
            const BaseType_t enviado = xQueueSend(terminadas, &aviso, 0);
            ESP_ERROR_CHECK(enviado == pdTRUE ? ESP_OK : ESP_FAIL);
        }
    }
}

void salida_dac_iniciar()
{
    pendientes = xQueueCreate(2, sizeof(BloqueDac));
    terminadas = xQueueCreate(1, sizeof(uint8_t));
    ESP_ERROR_CHECK(pendientes && terminadas ? ESP_OK : ESP_ERR_NO_MEM);
    dac_continuous_config_t cfg = {};
    cfg.chan_mask = DAC_CHANNEL_MASK_CH0;   // GPIO25
    cfg.desc_num = 6;
    cfg.buf_size = 512;
    cfg.freq_hz = 8000;
    cfg.offset = 0;
    cfg.clk_src = DAC_DIGI_CLK_SRC_APLL;
    cfg.chan_mode = DAC_CHANNEL_MODE_SIMUL;
    ESP_ERROR_CHECK(dac_continuous_new_channels(&cfg, &dac));
    ESP_ERROR_CHECK(dac_continuous_enable(dac));
    ESP_ERROR_CHECK(xTaskCreate(tarea_dac, "salida_dac", 3072, nullptr, 5, nullptr) == pdPASS
                    ? ESP_OK : ESP_ERR_NO_MEM);
}

bool salida_dac_disponible()
{
    return uxQueueSpacesAvailable(pendientes) > 0;
}

void salida_dac_input(const float* muestras, bool ultimo)
{
    BloqueDac bloque;
    bloque.ultimo = ultimo;
    for (size_t k = 0; k < MUESTRAS_BLOQUE; ++k) {
        const float v = muestras[k];
        if (!std::isfinite(v)) bloque.codigos[k] = 128;
        else if (v <= -1.0f) bloque.codigos[k] = 0;
        else if (v >= 1.0f) bloque.codigos[k] = 255;
        else bloque.codigos[k] = static_cast<uint8_t>(roundf(127.5f + 127.5f * v));
    }
    // Solo hay un productor; el consumidor únicamente libera espacio.
    const BaseType_t encolado = xQueueSend(pendientes, &bloque, 0);
    ESP_ERROR_CHECK(encolado == pdTRUE ? ESP_OK : ESP_FAIL);
}

bool salida_dac_terminada()
{
    uint8_t aviso;
    return xQueueReceive(terminadas, &aviso, 0) == pdTRUE;
}

ContadoresDac salida_dac_contadores()
{
    portENTER_CRITICAL(&cerrojo);
    const ContadoresDac copia = contadores;
    portEXIT_CRITICAL(&cerrojo);
    return copia;
}
