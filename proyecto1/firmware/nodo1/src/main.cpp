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

    // Tiempo de generar un bloque de 512 muestras, cada segundo.
    for (uint32_t n = 0;; ++n) {
        const int64_t t0 = esp_timer_get_time();
        gen.generar(bloque, HOP);
        const int64_t t1 = esp_timer_get_time();

        printf("bloque %lu | generar %lld us\n", (unsigned long)n, (long long)(t1 - t0));
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
