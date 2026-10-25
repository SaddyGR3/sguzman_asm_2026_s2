#include <cstdio>
#include <cstdlib>
#include <cmath>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_err.h"
#include "esp_timer.h"
#include "dsps_fft2r.h"
#include "generador.h"

constexpr int N_FFT = 1024;      // dos bloques de 512
constexpr int EXCLUSION = 12;    // bins que separan un pico de otro

// 512 muestras a 8 kHz = 64 ms: el temporizador marca el ritmo de un bloque.
constexpr uint64_t PERIODO_US = 64000;
constexpr uint32_t BLOQUES_VENTANA = 16;   // un resumen cada ~1.024 s

static TaskHandle_t tarea_principal = nullptr;   // la lee el callback del temporizador

// El callback corre en la tarea del temporizador (ESP_TIMER_TASK) y no en una
// interrupción, por eso se usa xTaskNotifyGive() y no la versión FromISR.
static void aviso_bloque(void*)
{
    xTaskNotifyGive(tarea_principal);
}

static float bloque[HOP];
static float muestras[N_FFT];
static float fft_buf[2 * N_FFT];        // real e imaginario intercalados
static float mag_db[N_FFT / 2 + 1];

// FFT de 1024 muestras generadas directamente sobre gen (avanza su fase).
static void analizar(Generador& gen)
{
    gen.generar(muestras, HOP);
    gen.generar(muestras + HOP, HOP);

    // Ventana de Hann periódica y parte imaginaria en cero.
    constexpr float DOS_PI = 6.283185307f;
    for (int n = 0; n < N_FFT; ++n) {
        const float w = 0.5f - 0.5f * cosf(DOS_PI * n / N_FFT);
        fft_buf[2 * n] = muestras[n] * w;
        fft_buf[2 * n + 1] = 0.0f;
    }

    dsps_fft2r_fc32(fft_buf, N_FFT);
    dsps_bit_rev_fc32(fft_buf, N_FFT);   // deja los bins en orden natural

    // Magnitud en dB y máximo global, de 0 a N/2.
    float max_db = -200.0f;
    for (int k = 0; k <= N_FFT / 2; ++k) {
        const float re = fft_buf[2 * k];
        const float im = fft_buf[2 * k + 1];
        mag_db[k] = 10.0f * log10f(re * re + im * im + 1e-20f);
        max_db = fmaxf(max_db, mag_db[k]);
    }

    // Los 4 máximos locales más altos, separados al menos EXCLUSION bins.
    int picos[4] = {-1, -1, -1, -1};
    for (int j = 0; j < 4; ++j) {
        int mejor = -1;
        for (int k = 1; k < N_FFT / 2; ++k) {
            const bool local = mag_db[k] >= mag_db[k - 1] && mag_db[k] >= mag_db[k + 1];
            bool usado = false;
            for (int i = 0; i < j; ++i) {
                if (abs(k - picos[i]) <= EXCLUSION) usado = true;
            }
            if (local && !usado && (mejor < 0 || mag_db[k] > mag_db[mejor])) mejor = k;
        }
        picos[j] = mejor;
    }

    printf("picos:");
    for (int j = 0; j < 4; ++j) {
        if (picos[j] < 0) continue;
        printf("  %.1f Hz (%.1f dB)", picos[j] * FS_HZ / N_FFT, mag_db[picos[j]] - max_db);
    }
    printf("\n");
}

extern "C" void app_main(void)
{
    Generador gen;
    const float g = 0.26f;                       // escala común: pico < 0.8
    gen.configurar(0, 300.0f,  1.00f * g);
    gen.configurar(1, 700.0f,  0.55f * g);
    gen.configurar(2, 1100.0f, 0.30f * g);
    gen.configurar(3, 2150.0f, 1.18f * g);       // interferencia, SNR de 0 dB

    // Verificación espectral, una sola vez al arrancar.
    if (dsps_fft2r_init_fc32(NULL, N_FFT) != ESP_OK) {
        printf("Error al iniciar la FFT de ESP-DSP\n");
    } else {
        analizar(gen);
    }

    // Temporizador periódico: cada 64 ms avisa a esta tarea que toca un bloque.
    tarea_principal = xTaskGetCurrentTaskHandle();
    esp_timer_create_args_t args = {};
    args.callback = aviso_bloque;
    args.dispatch_method = ESP_TIMER_TASK;
    args.name = "bloque";
    esp_timer_handle_t temporizador = nullptr;
    ESP_ERROR_CHECK(esp_timer_create(&args, &temporizador));
    ESP_ERROR_CHECK(esp_timer_start_periodic(temporizador, PERIODO_US));

    uint64_t first_sample = 0;   // índice de la primera muestra del siguiente bloque
    uint32_t overruns = 0;       // bloques que se retrasaron (acumulado)
    uint32_t bloques = 0;        // bloques generados (acumulado)

    // Valores de la ventana de resumen; se reinician al imprimir.
    uint32_t v_bloques = 0;
    uint32_t v_periodos = 0;
    uint32_t v_per_min = 0xFFFFFFFF;
    uint32_t v_per_max = 0;
    uint64_t v_per_suma = 0;
    uint32_t v_gen_max = 0;

    int64_t inicio_anterior = -1;   // la primera iteración no tiene periodo

    for (;;) {
        // Espera el aviso. Si n > 1, llegaron avisos mientras el bloque anterior
        // seguía en proceso: cada uno de más es un overrun.
        const uint32_t n = ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        if (n > 1) overruns += n - 1;

        const int64_t inicio = esp_timer_get_time();
        if (inicio_anterior >= 0) {
            const uint32_t periodo = static_cast<uint32_t>(inicio - inicio_anterior);
            if (periodo < v_per_min) v_per_min = periodo;
            if (periodo > v_per_max) v_per_max = periodo;
            v_per_suma += periodo;
            ++v_periodos;
        }
        inicio_anterior = inicio;

        // Generador continuo: la fase pasa de un bloque al siguiente.
        gen.generar(bloque, HOP);
        const uint32_t duracion = static_cast<uint32_t>(esp_timer_get_time() - inicio);
        if (duracion > v_gen_max) v_gen_max = duracion;

        first_sample += HOP;
        ++bloques;
        ++v_bloques;

        // El resumen va al final: el printf cae en el tiempo libre del periodo.
        if (v_bloques == BLOQUES_VENTANA) {
            const uint32_t prom = v_periodos ? static_cast<uint32_t>(v_per_suma / v_periodos) : 0;
            printf("bloques %lu | first_sample %llu | periodo prom %lu us (min %lu, max %lu) | generar max %lu us | overruns %lu\n",
                   (unsigned long)bloques, (unsigned long long)first_sample,
                   (unsigned long)prom, (unsigned long)v_per_min, (unsigned long)v_per_max,
                   (unsigned long)v_gen_max, (unsigned long)overruns);
            v_bloques = 0;
            v_periodos = 0;
            v_per_min = 0xFFFFFFFF;
            v_per_max = 0;
            v_per_suma = 0;
            v_gen_max = 0;
        }
    }
}
