#include "salida_dac.h"
#include "protocolo.h"
#include <cmath>
#include <cstring>
#include "driver/dac_continuous.h"
#include "esp_err.h"
#include "sdkconfig.h"

// Origen: configuración y conversión DAC de nodo1/src/main.cpp.
// En ESP32 cada código ocupa 16 bits físicos: seis búferes alojan tres bloques.
#if !CONFIG_DAC_DMA_AUTO_16BIT_ALIGN
#error "Se requiere CONFIG_DAC_DMA_AUTO_16BIT_ALIGN para escribir códigos de 8 bits"
#endif

static dac_continuous_handle_t dac = nullptr;
static uint8_t codigos[MUESTRAS_BLOQUE];
static ContadoresDac contadores;

void salida_dac_iniciar()
{
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
}

// Sin espera ni reintento: el resto de un bloque incompleto se descarta.
static void escribir_codigos()
{
    size_t escritos = 0;
    const esp_err_t error = dac_continuous_write(dac, codigos, sizeof(codigos), &escritos, 0);
    contadores.bytes += escritos;
    if (escritos < sizeof(codigos)) ++contadores.desbordes;
    if (error != ESP_ERR_TIMEOUT) ESP_ERROR_CHECK(error);
}

void salida_dac_input(const float* muestras)
{
    for (size_t k = 0; k < MUESTRAS_BLOQUE; ++k) {
        const float v = muestras[k];
        if (!std::isfinite(v)) {
            codigos[k] = 128;
        } else if (v <= -1.0f) {
            codigos[k] = 0;
        } else if (v >= 1.0f) {
            codigos[k] = 255;
        } else {
            codigos[k] = static_cast<uint8_t>(roundf(127.5f + 127.5f * v));
        }
    }
    escribir_codigos();
}

void salida_dac_silencio()
{
    memset(codigos, 128, sizeof(codigos));
    escribir_codigos();
}

const ContadoresDac& salida_dac_contadores()
{
    return contadores;
}
