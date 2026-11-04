#include "entrada_adc.h"
#include "coeficientes_decimacion.h"
#include <cmath>
#include <cstdio>
#include <cstring>
#include "freertos/FreeRTOS.h"
#include "esp_adc/adc_continuous.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_attr.h"
#include "esp_err.h"
#include "esp_timer.h"
#include "soc/soc_caps.h"

constexpr size_t SALIDAS_BLOQUE = 512;
constexpr size_t FACTOR_DECIMACION = 3;
constexpr size_t CRUDAS_BLOQUE = SALIDAS_BLOQUE * FACTOR_DECIMACION;
constexpr uint32_t FRECUENCIA_ADC = 24000;
constexpr uint32_t VREF_DEFECTO_MV = 1100;

static adc_continuous_handle_t adc = nullptr;
static adc_cali_handle_t calibracion = nullptr;
static uint8_t lectura[1024];
// Trabajo por tramo de lectura para medir las etapas con pocas marcas de tiempo.
static float voltajes[sizeof(lectura) / SOC_ADC_DIGI_RESULT_BYTES];
static size_t posicion_lectura = 0, bytes_lectura = 0;
static float historial[N_COEFICIENTES_DECIMACION];
static size_t posicion_fir = 0, fase = 0;
static bool historial_listo = false, dc_listo = false;
static float v_anterior = 0.0f, y_anterior = 0.0f, polo_dc = 0.0f;
static float limite_superior = 0.0f;
static portMUX_TYPE cerrojo_pool = portMUX_INITIALIZER_UNLOCKED;
static uint32_t desbordes_pool = 0;
static uint32_t saturaciones = 0;
static ResumenAdc ventana;
static uint64_t crudas_ventana = 0, salidas_ventana = 0;
static int64_t inicio_ventana_us = 0;

// Solo cuenta el evento desde ISR. No se reinician el ADC ni los estados.
static bool IRAM_ATTR aviso_desborde(adc_continuous_handle_t,
                                    const adc_continuous_evt_data_t*, void*)
{
    portENTER_CRITICAL_ISR(&cerrojo_pool);
    ++desbordes_pool;
    portEXIT_CRITICAL_ISR(&cerrojo_pool);
    return false;
}

void entrada_adc_iniciar()
{
    adc_cali_line_fitting_efuse_val_t tipo;
    ESP_ERROR_CHECK(adc_cali_scheme_line_fitting_check_efuse(&tipo));
    adc_cali_line_fitting_config_t cal = {};
    cal.unit_id = ADC_UNIT_1;
    cal.atten = ADC_ATTEN_DB_12;
    cal.bitwidth = ADC_BITWIDTH_12;
    cal.default_vref = VREF_DEFECTO_MV;
    ESP_ERROR_CHECK(adc_cali_create_scheme_line_fitting(&cal, &calibracion));
    if (tipo == ADC_CALI_LINE_FITTING_EFUSE_VAL_EFUSE_TP) {
        printf("ADC: calibración line fitting, eFuse Two Point\n");
    } else if (tipo == ADC_CALI_LINE_FITTING_EFUSE_VAL_EFUSE_VREF) {
        printf("ADC: calibración line fitting, eFuse Vref\n");
    } else {
        printf("ADC: AVISO sin calibración eFuse; line fitting con Vref por defecto %lu mV\n",
               (unsigned long)VREF_DEFECTO_MV);
    }

    adc_continuous_handle_cfg_t memoria = {};
    memoria.max_store_buf_size = 16384;
    memoria.conv_frame_size = sizeof(lectura);
    ESP_ERROR_CHECK(adc_continuous_new_handle(&memoria, &adc));
    adc_digi_pattern_config_t patron = {};
    patron.atten = ADC_ATTEN_DB_12;
    patron.channel = ADC_CHANNEL_0;   // GPIO36 (VP)
    patron.unit = ADC_UNIT_1;
    patron.bit_width = ADC_BITWIDTH_12;
    adc_continuous_config_t cfg = {};
    cfg.pattern_num = 1;
    cfg.adc_pattern = &patron;
    cfg.sample_freq_hz = FRECUENCIA_ADC;
    cfg.conv_mode = ADC_CONV_SINGLE_UNIT_1;
    // ESP-IDF 6.1 selecciona TYPE1 automáticamente en el ESP32 clásico.
    ESP_ERROR_CHECK(adc_continuous_config(adc, &cfg));
    adc_continuous_evt_cbs_t eventos = {};
    eventos.on_pool_ovf = aviso_desborde;
    ESP_ERROR_CHECK(adc_continuous_register_event_callbacks(adc, &eventos, nullptr));
    polo_dc = static_cast<float>(exp(-2.0 * 3.14159265358979323846 * 10.0 / 8000.0));
    limite_superior = nextafterf(1.0f, 0.0f);
    printf("ADC1 canal 0 GPIO36: 24000 Hz, 12 bits, 12 dB, DMA 1024 B, pool 16384 B | "
           "FIR 37, decimación /3, salida 8000 Hz | DC 10 Hz, escala 1200 mV\n");
    inicio_ventana_us = esp_timer_get_time();
    ESP_ERROR_CHECK(adc_continuous_start(adc));
}

// Conserva bytes pendientes incluso si una lectura termina dentro de un resultado.
static void completar_lectura()
{
    const size_t sobrantes = bytes_lectura - posicion_lectura;
    memmove(lectura, lectura + posicion_lectura, sobrantes);
    posicion_lectura = 0;
    bytes_lectura = sobrantes;
    while (bytes_lectura < SOC_ADC_DIGI_RESULT_BYTES) {
        uint32_t recibidos = 0;
        const esp_err_t error = adc_continuous_read(adc, lectura + bytes_lectura,
                                                   sizeof(lectura) - bytes_lectura,
                                                   &recibidos, 1000);
        if (error == ESP_ERR_TIMEOUT) continue;
        ESP_ERROR_CHECK(error);
        bytes_lectura += recibidos;
    }
}

static float decimar(float mv)
{
    if (!historial_listo) {
        for (auto& valor : historial) valor = mv;
        historial_listo = true;
    }
    historial[posicion_fir] = mv;
    float filtrado = 0.0f;
    if (fase == 0) {
        size_t j = posicion_fir;
        for (size_t k = 0; k < N_COEFICIENTES_DECIMACION; ++k) {
            filtrado += COEFICIENTES_DECIMACION[k] * historial[j];
            j = j == 0 ? N_COEFICIENTES_DECIMACION - 1 : j - 1;
        }
    }
    posicion_fir = (posicion_fir + 1) % N_COEFICIENTES_DECIMACION;
    return filtrado;
}

static float quitar_dc_normalizar(float v)
{
    if (!dc_listo) {
        v_anterior = v;
        y_anterior = 0.0f;
        dc_listo = true;
    }
    const float y = v - v_anterior + polo_dc * y_anterior;
    v_anterior = v;
    y_anterior = y;
    const float normalizado = y / 1200.0f;
    if (normalizado < -1.0f) {
        ++saturaciones;
        return -1.0f;
    }
    if (normalizado > limite_superior) {
        ++saturaciones;
        return limite_superior;
    }
    return normalizado;
}

uint32_t entrada_adc_leer_bloque(float* x)
{
    size_t crudas = 0, salidas = 0;
    uint32_t procesamiento_us = 0;
    uint32_t calibracion_us = 0, filtrado_us = 0;
    while (crudas < CRUDAS_BLOQUE) {
        if (bytes_lectura - posicion_lectura < SOC_ADC_DIGI_RESULT_BYTES) completar_lectura();
        const int64_t inicio = esp_timer_get_time();
        size_t validas = 0;
        while (posicion_lectura + SOC_ADC_DIGI_RESULT_BYTES <= bytes_lectura && crudas < CRUDAS_BLOQUE) {
            adc_digi_output_data_t dato;
            memcpy(&dato, lectura + posicion_lectura, sizeof(dato));
            posicion_lectura += SOC_ADC_DIGI_RESULT_BYTES;
            if (dato.type1.channel != ADC_CHANNEL_0) continue;
            const uint16_t crudo = dato.type1.data;
            int mv = 0;
            ESP_ERROR_CHECK(adc_cali_raw_to_voltage(calibracion, crudo, &mv));
            if (crudas_ventana == 0 || mv < ventana.mv_min) ventana.mv_min = mv;
            if (crudas_ventana == 0 || mv > ventana.mv_max) ventana.mv_max = mv;
            if (crudo < ventana.crudo_min) ventana.crudo_min = crudo;
            if (crudo > ventana.crudo_max) ventana.crudo_max = crudo;
            ++crudas_ventana;
            ++crudas;
            voltajes[validas++] = static_cast<float>(mv);
        }
        const int64_t fin_calibracion = esp_timer_get_time();
        for (size_t j = 0; j < validas; ++j) {
            const float v = decimar(voltajes[j]);
            // Misma fase que filtrar(x)[::3]: entradas 0, 3, 6, ...
            if (fase == 0) {
                x[salidas++] = quitar_dc_normalizar(v);
                ++salidas_ventana;
            }
            fase = (fase + 1) % FACTOR_DECIMACION;
        }
        const int64_t fin_filtrado = esp_timer_get_time();
        calibracion_us += static_cast<uint32_t>(fin_calibracion - inicio);
        filtrado_us += static_cast<uint32_t>(fin_filtrado - fin_calibracion);
        procesamiento_us += static_cast<uint32_t>(fin_filtrado - inicio);
    }
    // Se consumen también las dos entradas posteriores a la salida 512: cada
    // bloque contiene exactamente 1536 entradas y mantiene la fase global.
    if (procesamiento_us > ventana.procesamiento_max_us) ventana.procesamiento_max_us = procesamiento_us;
    if (calibracion_us > ventana.calibracion_max_us) ventana.calibracion_max_us = calibracion_us;
    if (filtrado_us > ventana.filtrado_max_us) ventana.filtrado_max_us = filtrado_us;
    return procesamiento_us;
}

ContadoresAdc entrada_adc_contadores()
{
    ContadoresAdc c;
    portENTER_CRITICAL(&cerrojo_pool);
    c.desbordes_pool = desbordes_pool;
    portEXIT_CRITICAL(&cerrojo_pool);
    c.saturaciones = saturaciones;
    return c;
}

ResumenAdc entrada_adc_resumen()
{
    const int64_t ahora = esp_timer_get_time();
    const double segundos = static_cast<double>(ahora - inicio_ventana_us) / 1000000.0;
    ResumenAdc resumen = ventana;
    if (segundos > 0.0) {
        resumen.frecuencia_adc = crudas_ventana / segundos;
        resumen.frecuencia_salida = salidas_ventana / segundos;
    }
    resumen.acumulados = entrada_adc_contadores();
    ventana = ResumenAdc{};
    crudas_ventana = salidas_ventana = 0;
    inicio_ventana_us = ahora;
    return resumen;
}
