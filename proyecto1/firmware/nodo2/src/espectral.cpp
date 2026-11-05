#include "espectral.h"
#include <cmath>
#include <cstring>
#include "dsps_fft2r.h"

// Origen: nodo1/src/espectro.cpp (raíz de Hann periódica, tabla y FFT ESP-DSP).
// Se conserva el espectro complejo completo y la media para reconstruir la entrada.
alignas(16) static float fft[2 * ESPECTRAL_N];
alignas(16) static float tabla[ESPECTRAL_N];
static float ventana[ESPECTRAL_N];
static float historial[ESPECTRAL_N];
static float solape[ESPECTRAL_H];

void espectral_reiniciar()
{
    std::memset(historial, 0, sizeof(historial));
    std::memset(solape, 0, sizeof(solape));
}

esp_err_t espectral_iniciar()
{
    const esp_err_t error = dsps_fft2r_init_fc32(tabla, ESPECTRAL_N);
    if (error != ESP_OK) return error;
    for (int j = 0; j < ESPECTRAL_N; ++j) {
        const double hann = 0.5 * (1.0 - std::cos(2.0 * 3.14159265358979323846 * j / ESPECTRAL_N));
        ventana[j] = static_cast<float>(std::sqrt(hann));
    }
    espectral_reiniciar();
    return ESP_OK;
}

static void modificar_espectro()
{
    // Paso 6b-1: ganancia unitaria. En 6b-2 se calculará aquí la ganancia por bin.
    // Reponer el conjugado de cada bin positivo conserva una salida real.
    for (int k = 0; k <= ESPECTRAL_N / 2; ++k) {
        const float ganancia = 1.0f;
        fft[2 * k] *= ganancia;
        fft[2 * k + 1] *= ganancia;
        if (k > 0 && k < ESPECTRAL_N / 2) {
            fft[2 * (ESPECTRAL_N - k)] = fft[2 * k];
            fft[2 * (ESPECTRAL_N - k) + 1] = -fft[2 * k + 1];
        }
    }
    // DC y Nyquist son reales y no tienen una pareja distinta.
    fft[1] = 0.0f;
    fft[ESPECTRAL_N + 1] = 0.0f;
}

void espectral_procesar(const float* entrada, float* salida)
{
    std::memcpy(historial, historial + ESPECTRAL_H, ESPECTRAL_H * sizeof(float));
    std::memcpy(historial + ESPECTRAL_H, entrada, ESPECTRAL_H * sizeof(float));
    for (int j = 0; j < ESPECTRAL_N; ++j) {
        fft[2 * j] = historial[j] * ventana[j];
        fft[2 * j + 1] = 0.0f;
    }
    ESP_ERROR_CHECK(dsps_fft2r_fc32(fft, ESPECTRAL_N));
    ESP_ERROR_CHECK(dsps_bit_rev_fc32(fft, ESPECTRAL_N));
    modificar_espectro();

    // ESP-DSP entrega la FFT sin normalizar: IFFT(X) = conj(FFT(conj(X))) / N.
    for (int j = 0; j < ESPECTRAL_N; ++j) fft[2 * j + 1] = -fft[2 * j + 1];
    ESP_ERROR_CHECK(dsps_fft2r_fc32(fft, ESPECTRAL_N));
    ESP_ERROR_CHECK(dsps_bit_rev_fc32(fft, ESPECTRAL_N));
    constexpr float ESCALA = 1.0f / ESPECTRAL_N;

    // Solo se usa la parte real: el conjugado final no la cambia.
    // La normalización 1/N se aplica aquí, junto a la ventana de síntesis.
    // w[j]^2 + w[j+H]^2 = Hann[j] + Hann[j+H] = 1, sin otra escala.
    // La primera salida corresponde a H ceros; la segunda reconstruye el bloque 0.
    for (int j = 0; j < ESPECTRAL_H; ++j) {
        salida[j] = solape[j] + fft[2 * j] * ESCALA * ventana[j];
        solape[j] = fft[2 * (j + ESPECTRAL_H)] * ESCALA * ventana[j + ESPECTRAL_H];
    }
}
