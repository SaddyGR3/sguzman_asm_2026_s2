#include "espectral.h"
#include <algorithm>
#include <cmath>
#include <cstring>
#include "dsps_fft2r.h"

// Origen: nodo1/src/espectro.cpp (raíz de Hann periódica, tabla y FFT ESP-DSP).
// Se conserva el espectro complejo completo para modificarlo y reconstruir audio real.
alignas(16) static float fft[2 * ESPECTRAL_N];
alignas(16) static float tabla[ESPECTRAL_N];
static float ventana[ESPECTRAL_N];
static float historial[ESPECTRAL_N];
static float solape[ESPECTRAL_H];

constexpr int BINS = ESPECTRAL_N / 2 + 1;
constexpr int TRAMAS_RUIDO = 8;
constexpr int SUAVIZADO_BINS = 31;
static_assert(SUAVIZADO_BINS % 2 == 1 && SUAVIZADO_BINS <= BINS,
              "La ventana de mediana debe ser impar y caber en el espectro");

// Historial de magnitudes originales, antes de aplicar cualquier ganancia.
// Todos los búferes del estimador son estáticos: no se reserva memoria por bloque.
static float magnitudes[BINS];
static float historia_ruido[TRAMAS_RUIDO][BINS];
static float perfil_ruido[BINS];
static float piso_ruido[BINS];
static float trabajo_mediana[SUAVIZADO_BINS];
static_assert(TRAMAS_RUIDO <= SUAVIZADO_BINS, "El trabajo debe caber en el búfer de mediana");
static int siguiente_trama = 0;
static int tramas_ruido = 0;
static bool primera_trama = true;
static ConfiguracionEspectral configuracion;
constexpr float EPSILON = 1e-12f;

bool espectral_configurar(double alfa, double ganancia_minima)
{
    if (!std::isfinite(alfa) || !std::isfinite(ganancia_minima) ||
        alfa < 0.5 || alfa > 10.0 || ganancia_minima < 0.0 || ganancia_minima > 0.5) {
        return false;
    }
    configuracion.alfa = static_cast<float>(alfa);
    configuracion.ganancia_minima = static_cast<float>(ganancia_minima);
    // Cambiar la intensidad no invalida las magnitudes originales del historial.
    return true;
}

const ConfiguracionEspectral& espectral_configuracion()
{
    return configuracion;
}

void espectral_reiniciar()
{
    std::memset(historial, 0, sizeof(historial));
    std::memset(solape, 0, sizeof(solape));
    std::memset(magnitudes, 0, sizeof(magnitudes));
    std::memset(historia_ruido, 0, sizeof(historia_ruido));
    std::memset(perfil_ruido, 0, sizeof(perfil_ruido));
    std::memset(piso_ruido, 0, sizeof(piso_ruido));
    siguiente_trama = 0;
    tramas_ruido = 0;
    primera_trama = true;
}

// Ordena solo los valores cargados en el búfer auxiliar compartido.
static float mediana(int cantidad)
{
    std::sort(trabajo_mediana, trabajo_mediana + cantidad);
    const int centro = cantidad / 2;
    if (cantidad % 2 != 0) return trabajo_mediana[centro];
    return 0.5f * (trabajo_mediana[centro - 1] + trabajo_mediana[centro]);
}

static void estimar_ruido()
{
    for (int k = 0; k < BINS; ++k) {
        magnitudes[k] = std::hypot(fft[2 * k], fft[2 * k + 1]);
    }

    // La primera FFT contiene H ceros de arranque: no representa una trama real.
    if (primera_trama) {
        primera_trama = false;
        return;
    }

    std::memcpy(historia_ruido[siguiente_trama], magnitudes, sizeof(magnitudes));
    siguiente_trama = (siguiente_trama + 1) % TRAMAS_RUIDO;
    if (tramas_ruido < TRAMAS_RUIDO) ++tramas_ruido;
    // Hasta completar ocho tramas, el estimador permanece en calentamiento.
    if (tramas_ruido < TRAMAS_RUIDO) return;

    // La mediana no depende del orden circular. Incluye la trama actual y siete
    // anteriores; ninguna decisión requiere muestras futuras de la grabación.
    for (int k = 0; k < BINS; ++k) {
        for (int t = 0; t < TRAMAS_RUIDO; ++t) {
            trabajo_mediana[t] = historia_ruido[t][k];
        }
        perfil_ruido[k] = mediana(TRAMAS_RUIDO);
    }

    // Mediana frecuencial de 31 bins, reflejando los extremos sin repetirlos.
    // Se escribe en otro búfer para no alterar vecinos aún por procesar.
    constexpr int RADIO = SUAVIZADO_BINS / 2;
    for (int k = 0; k < BINS; ++k) {
        for (int j = 0; j < SUAVIZADO_BINS; ++j) {
            int vecino = k + j - RADIO;
            if (vecino < 0) vecino = -vecino;
            else if (vecino >= BINS) vecino = 2 * (BINS - 1) - vecino;
            trabajo_mediana[j] = perfil_ruido[vecino];
        }
        piso_ruido[k] = mediana(SUAVIZADO_BINS);
    }
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
    // Sin ocho tramas reales aún no hay piso estimado: dejar pasar la entrada.
    const bool listo = tramas_ruido == TRAMAS_RUIDO;
    // Reponer el conjugado de cada bin positivo conserva una salida real.
    for (int k = 0; k <= ESPECTRAL_N / 2; ++k) {
        float ganancia = 1.0f;
        if (listo) {
            const float magnitud = std::max(magnitudes[k], EPSILON);
            const float resta = 1.0f - configuracion.alfa * piso_ruido[k] / magnitud;
            ganancia = std::max(configuracion.ganancia_minima, std::min(resta, 1.0f));
        }
        // Una ganancia real común a ambas partes conserva la fase de este bin.
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
    estimar_ruido();
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
