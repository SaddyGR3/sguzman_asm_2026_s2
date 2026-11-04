#include "espectro.h"
#include <cmath>
#include "dsps_fft2r.h"

constexpr int N_MAX = 1024;
static int longitud = 0;
alignas(16) static float fft[2 * N_MAX];
alignas(16) static float tabla[N_MAX];
static float ventana[N_MAX];
static float vecinos[31];

esp_err_t espectro_iniciar(int n)
{
    if (n != 256 && n != 512 && n != 1024) return ESP_ERR_INVALID_ARG;
    // Tabla máxima compartida: también permite transformar las longitudes menores.
    const esp_err_t error = dsps_fft2r_init_fc32(tabla, N_MAX);
    if (error != ESP_OK) return error;
    longitud = n;
    // Replica sim/nodo3.py::ventana_sqrt_hann(), periódica (denominador N).
    for (int j = 0; j < n; ++j) {
        const double hann = 0.5 * (1.0 - cos(2.0 * 3.14159265358979323846 * j / n));
        ventana[j] = static_cast<float>(sqrt(hann));
    }
    return ESP_OK;
}

float espectro_magnitudes(const float* x, float* M, int inicio)
{
    // Replica la FFT y abs(espectro) de sim/nodo3.py::_procesar_tramas().
    // Se retira además la media en la copia de análisis, sin cambiar la entrada.
    double suma = 0.0;
    for (int j = 0; j < longitud; ++j) suma += x[j];
    const float media = static_cast<float>(suma / longitud);
    for (int j = 0; j < longitud; ++j) {
        const int k = (inicio + j) & (longitud - 1);
        fft[2 * j] = (x[k] - media) * ventana[j];
        fft[2 * j + 1] = 0.0f;
    }
    ESP_ERROR_CHECK(dsps_fft2r_fc32(fft, longitud));
    ESP_ERROR_CHECK(dsps_bit_rev_fc32(fft, longitud));
    for (int k = 0; k <= longitud / 2; ++k) {
        M[k] = hypotf(fft[2 * k], fft[2 * k + 1]);
    }
    return media;
}

void espectro_piso(const float* M, float* P)
{
    // Replica sim/nodo3.py::suavizar_piso(perfil, 31): np.pad(mode="reflect")
    // no repite el extremo. El perfil de esta tanda es el espectro actual.
    const int ultimo = longitud / 2;
    for (int k = 0; k <= ultimo; ++k) {
        for (int j = 0; j < 31; ++j) {
            int indice = k + j - 15;
            if (indice < 0) indice = -indice;
            if (indice > ultimo) indice = 2 * ultimo - indice;
            // Inserción ordenada de los 31 vecinos, sin memoria dinámica.
            const float valor = M[indice];
            int p = j;
            while (p > 0 && vecinos[p - 1] > valor) {
                vecinos[p] = vecinos[p - 1];
                --p;
            }
            vecinos[p] = valor;
        }
        P[k] = vecinos[15];
    }
}

float espectro_bin_a_hz(int bin, float fs)
{
    // Misma rejilla que np.fft.rfftfreq(N, 1/fs) en sim/nodo3.py.
    return bin * fs / longitud;
}

float espectro_hz_a_bin(float hz, float fs)
{
    // Inversa de la rejilla de sim/nodo3.py; el llamador decide el redondeo.
    return hz * longitud / fs;
}
