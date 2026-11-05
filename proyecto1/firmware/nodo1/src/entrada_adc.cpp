#include "entrada_adc.h"
#include "coeficientes_decimacion.h"
#include <cmath>
#include <climits>
#include <cstdio>
#include <cstring>
#include "freertos/FreeRTOS.h"
#include "esp_adc/adc_continuous.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_attr.h"
#include "esp_err.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "soc/soc_caps.h"

constexpr size_t SALIDAS_BLOQUE = 512;
constexpr size_t FACTOR_DECIMACION = 3;
constexpr size_t CRUDAS_BLOQUE = SALIDAS_BLOQUE * FACTOR_DECIMACION;
constexpr uint32_t FRECUENCIA_ADC = 24000;
constexpr uint32_t VREF_DEFECTO_MV = 1100;
constexpr size_t CODIGOS_ADC = 4096;

struct EstadoCanal {
    float historial[N_COEFICIENTES_DECIMACION] = {};
    size_t posicion = 0;
    unsigned fase = 0;
    bool historial_listo = false, dc_listo = false;
    float v_anterior = 0.0f, y_anterior = 0.0f;
    ResumenCanalAdc ventana;
    uint32_t crudas_ventana = 0, salidas_ventana = 0;
    uint32_t saturaciones = 0;
};

static adc_continuous_handle_t adc = nullptr;
static adc_cali_handle_t calibracion = nullptr;
// Una tabla en RAM interna, reservada al arrancar: 8 KB si cabe en int16_t,
// o 16 KB en int32_t. Sin reservas ni llamadas de calibración en el lazo.
static int16_t* tabla16 = nullptr;
static int32_t* tabla32 = nullptr;
static uint8_t lectura[1024];
static float voltajes[512];
static size_t posicion_lectura = 0, bytes_lectura = 0;
static EstadoCanal canal_x;
static float polo_dc = 0.0f, limite_superior = 0.0f;
static portMUX_TYPE cerrojo_pool = portMUX_INITIALIZER_UNLOCKED;
static uint32_t desbordes_pool = 0;
static ResumenAdc ventana;
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

static void iniciar_tabla_calibracion()
{
    bool cabe16 = true;
    for (size_t raw = 0; raw < CODIGOS_ADC; ++raw) {
        int mv;
        ESP_ERROR_CHECK(adc_cali_raw_to_voltage(calibracion, raw, &mv));
        if (mv < INT16_MIN || mv > INT16_MAX) cabe16 = false;
    }
    if (cabe16) {
        tabla16 = static_cast<int16_t*>(heap_caps_malloc(CODIGOS_ADC * sizeof(int16_t),
                                                        MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT));
        ESP_ERROR_CHECK(tabla16 ? ESP_OK : ESP_ERR_NO_MEM);
    } else {
        tabla32 = static_cast<int32_t*>(heap_caps_malloc(CODIGOS_ADC * sizeof(int32_t),
                                                        MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT));
        ESP_ERROR_CHECK(tabla32 ? ESP_OK : ESP_ERR_NO_MEM);
    }
    for (size_t raw = 0; raw < CODIGOS_ADC; ++raw) {
        int mv;
        ESP_ERROR_CHECK(adc_cali_raw_to_voltage(calibracion, raw, &mv));
        if (tabla16) tabla16[raw] = static_cast<int16_t>(mv);
        else tabla32[raw] = mv;
    }
    printf("ADC: tabla raw->mV de 4096 valores para x, %s (%u B)\n",
           cabe16 ? "int16_t" : "int32_t", cabe16 ? 8192u : 16384u);
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
    iniciar_tabla_calibracion();

    adc_continuous_handle_cfg_t memoria = {};
    memoria.max_store_buf_size = 16384;
    memoria.conv_frame_size = sizeof(lectura);
    ESP_ERROR_CHECK(adc_continuous_new_handle(&memoria, &adc));
    adc_digi_pattern_config_t patron = {};
    patron.channel = ADC_CHANNEL_0;   // GPIO36: x
    patron.atten = ADC_ATTEN_DB_12;
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
    polo_dc = expf(-2.0f * 3.14159265358979323846f * 10.0f * (1.0f / 8000.0f));
    limite_superior = nextafterf(1.0f, 0.0f);
    printf("ADC1 GPIO36 canal 0 = x: 24000 Hz, 12 bits, 12 dB, "
           "DMA 1024 B, pool 16384 B | FIR 37 /3, salida 8000 Hz | "
           "DC 10 Hz, escala 1200 mV\n");
    inicio_ventana_us = esp_timer_get_time();
    ESP_ERROR_CHECK(adc_continuous_start(adc));
}

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

static float calibrar(EstadoCanal& c, uint16_t crudo)
{
    const int mv = tabla16 ? tabla16[crudo] : tabla32[crudo];
    if (c.crudas_ventana == 0 || mv < c.ventana.mv_min) c.ventana.mv_min = mv;
    if (c.crudas_ventana == 0 || mv > c.ventana.mv_max) c.ventana.mv_max = mv;
    if (crudo < c.ventana.crudo_min) c.ventana.crudo_min = crudo;
    if (crudo > c.ventana.crudo_max) c.ventana.crudo_max = crudo;
    ++c.crudas_ventana;
    return static_cast<float>(mv);
}

static float decimar(EstadoCanal& c, float mv)
{
    if (!c.historial_listo) {
        for (auto& valor : c.historial) valor = mv;
        c.historial_listo = true;
    }
    c.historial[c.posicion] = mv;
    float filtrado = 0.0f;
    if (c.fase == 0) {
        size_t j = c.posicion;
        for (size_t k = 0; k < N_COEFICIENTES_DECIMACION; ++k) {
            filtrado += COEFICIENTES_DECIMACION[k] * c.historial[j];
            j = j == 0 ? N_COEFICIENTES_DECIMACION - 1 : j - 1;
        }
    }
    if (++c.posicion == N_COEFICIENTES_DECIMACION) c.posicion = 0;
    return filtrado;
}

static float quitar_dc_normalizar(EstadoCanal& c, float v)
{
    if (!c.dc_listo) {
        c.v_anterior = v;
        c.y_anterior = 0.0f;
        c.dc_listo = true;
    }
    const float y = v - c.v_anterior + polo_dc * c.y_anterior;
    c.v_anterior = v;
    c.y_anterior = y;
    const float normalizado = y * (1.0f / 1200.0f);
    if (normalizado < -1.0f) {
        ++c.saturaciones;
        return -1.0f;
    }
    if (normalizado > limite_superior) {
        ++c.saturaciones;
        return limite_superior;
    }
    return normalizado;
}

uint32_t entrada_adc_leer_bloque(float* x)
{
    size_t crudas = 0, salidas = 0;
    uint32_t calibracion_us = 0, filtrado_us = 0;
    while (crudas < CRUDAS_BLOQUE) {
        if (bytes_lectura - posicion_lectura < SOC_ADC_DIGI_RESULT_BYTES) completar_lectura();
        const int64_t inicio = esp_timer_get_time();
        size_t validos = 0;
        while (posicion_lectura + SOC_ADC_DIGI_RESULT_BYTES <= bytes_lectura &&
               crudas < CRUDAS_BLOQUE && validos < sizeof(voltajes) / sizeof(voltajes[0])) {
            adc_digi_output_data_t dato;
            memcpy(&dato, lectura + posicion_lectura, sizeof(dato));
            posicion_lectura += SOC_ADC_DIGI_RESULT_BYTES;
            if (dato.type1.channel == ADC_CHANNEL_0) {
                voltajes[validos++] = calibrar(canal_x, dato.type1.data);
                ++crudas;
            }
        }
        const int64_t fin_calibracion = esp_timer_get_time();
        for (size_t j = 0; j < validos; ++j) {
            const float vx = decimar(canal_x, voltajes[j]);
            if (canal_x.fase == 0) {
                x[salidas++] = quitar_dc_normalizar(canal_x, vx);
                ++canal_x.salidas_ventana;
            }
            if (++canal_x.fase == FACTOR_DECIMACION) canal_x.fase = 0;
        }
        const int64_t fin_filtrado = esp_timer_get_time();
        calibracion_us += static_cast<uint32_t>(fin_calibracion - inicio);
        filtrado_us += static_cast<uint32_t>(fin_filtrado - fin_calibracion);
    }
    const uint32_t procesamiento_us = calibracion_us + filtrado_us;
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
    c.saturaciones = canal_x.saturaciones;
    return c;
}

static ResumenCanalAdc cerrar_ventana(EstadoCanal& c, double segundos)
{
    ResumenCanalAdc resumen = c.ventana;
    if (segundos > 0.0) {
        resumen.frecuencia_adc = c.crudas_ventana / segundos;
        resumen.frecuencia_salida = c.salidas_ventana / segundos;
    }
    c.ventana = ResumenCanalAdc{};
    c.crudas_ventana = c.salidas_ventana = 0;
    return resumen;
}

ResumenAdc entrada_adc_resumen()
{
    const int64_t ahora = esp_timer_get_time();
    const double segundos = static_cast<double>(ahora - inicio_ventana_us) / 1000000.0;
    ResumenAdc resumen = ventana;
    resumen.x = cerrar_ventana(canal_x, segundos);
    resumen.acumulados = entrada_adc_contadores();
    ventana = ResumenAdc{};
    inicio_ventana_us = ahora;
    return resumen;
}
