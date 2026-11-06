#include "espectral.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include "dsps_fft2r.h"
#include "esp_timer.h"

// Origen: nodo1/src/espectro.cpp (raíz de Hann periódica, tabla y FFT ESP-DSP).
// Se conserva el espectro complejo completo para modificarlo y reconstruir audio real.
alignas(16) static float fft[2 * ESPECTRAL_N];
alignas(16) static float tabla[ESPECTRAL_N];
static float ventana[ESPECTRAL_N];
static float historial[ESPECTRAL_N];
static float solape[ESPECTRAL_H];

constexpr int BINS_MAX = ESPECTRAL_N / 2 + 1;
static int n_actual = ESPECTRAL_N, h_actual = ESPECTRAL_H, bins_actual = BINS_MAX;
constexpr int TRAMAS_RUIDO = 8;
constexpr int SUAVIZADO_BINS = 31;
static_assert(SUAVIZADO_BINS % 2 == 1 && SUAVIZADO_BINS <= BINS_MAX,
              "La ventana de mediana debe ser impar y caber en el espectro");

// Historial de magnitudes originales, antes de aplicar cualquier ganancia.
// Todos los búferes del estimador son estáticos: no se reserva memoria por bloque.
static float magnitudes[BINS_MAX];
static float historia_ruido[TRAMAS_RUIDO][BINS_MAX];
static float perfil_ruido[BINS_MAX];
static float piso_ruido[BINS_MAX];
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
    for (int k = 0; k < bins_actual; ++k) {
        magnitudes[k] = std::hypot(fft[2 * k], fft[2 * k + 1]);
    }

    // La primera FFT contiene H ceros de arranque: no representa una trama real.
    if (primera_trama) {
        primera_trama = false;
        return;
    }

    std::memcpy(historia_ruido[siguiente_trama], magnitudes, bins_actual * sizeof(float));
    siguiente_trama = (siguiente_trama + 1) % TRAMAS_RUIDO;
    if (tramas_ruido < TRAMAS_RUIDO) ++tramas_ruido;
    // Hasta completar ocho tramas, el estimador permanece en calentamiento.
    if (tramas_ruido < TRAMAS_RUIDO) return;

    // La mediana no depende del orden circular. Incluye la trama actual y siete
    // anteriores; ninguna decisión requiere muestras futuras de la grabación.
    for (int k = 0; k < bins_actual; ++k) {
        for (int t = 0; t < TRAMAS_RUIDO; ++t) {
            trabajo_mediana[t] = historia_ruido[t][k];
        }
        perfil_ruido[k] = mediana(TRAMAS_RUIDO);
    }

    // Mediana frecuencial de 31 bins, reflejando los extremos sin repetirlos.
    // Se escribe en otro búfer para no alterar vecinos aún por procesar.
    constexpr int RADIO = SUAVIZADO_BINS / 2;
    for (int k = 0; k < bins_actual; ++k) {
        for (int j = 0; j < SUAVIZADO_BINS; ++j) {
            int vecino = k + j - RADIO;
            if (vecino < 0) vecino = -vecino;
            else if (vecino >= bins_actual) vecino = 2 * (bins_actual - 1) - vecino;
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

bool espectral_validar_fft()
{
    constexpr int N = 256;
    constexpr double PI = 3.14159265358979323846;
    const int64_t inicio = esp_timer_get_time();
    // Alineación explícita para ESP-DSP sin aumentar la pila ni los estáticos.
    void* reserva = std::malloc(3 * N * sizeof(float) + 15);
    double error_max = NAN, relativo = NAN;
    bool finitos = false;
    if (reserva) {
        const uintptr_t direccion = (reinterpret_cast<uintptr_t>(reserva) + 15) & ~uintptr_t(15);
        float* espectro = reinterpret_cast<float*>(direccion);
        float* entrada = espectro + 2 * N;
        for (int j = 0; j < N; ++j) {
            const double t = j / 8000.0;
            entrada[j] = static_cast<float>(0.1 + 0.5 * std::sin(2 * PI * 437 * t)
                                               + 0.2 * std::cos(2 * PI * 1234 * t));
            espectro[2 * j] = entrada[j];
            espectro[2 * j + 1] = 0.0f;
        }
        // Misma tabla máxima inicializada por espectral_iniciar(), signo,
        // escala y orden natural que en la ruta de audio. Sin ventana aquí.
        esp_err_t error = dsps_fft2r_fc32(espectro, N);
        if (error == ESP_OK) error = dsps_bit_rev_fc32(espectro, N);
        if (error == ESP_OK) {
            error_max = 0.0;
            double referencia_max = 0.0;
            finitos = true;
            for (int k = 0; k < N; ++k) {
                // DFT por definición, sin FFT ni recurrencias de referencia.
                // Se usa exactamente la entrada float de ESP-DSP, convertida a double.
                double real = 0.0, imaginaria = 0.0;
                for (int j = 0; j < N; ++j) {
                    const double angulo = 2 * PI * k * j / N;
                    real += static_cast<double>(entrada[j]) * std::cos(angulo);
                    imaginaria -= static_cast<double>(entrada[j]) * std::sin(angulo);
                }
                const double diferencia = std::hypot(espectro[2 * k] - real,
                                                     espectro[2 * k + 1] - imaginaria);
                const double referencia = std::hypot(real, imaginaria);
                if (!std::isfinite(diferencia) || !std::isfinite(referencia)) finitos = false;
                else {
                    error_max = std::max(error_max, diferencia);
                    referencia_max = std::max(referencia_max, referencia);
                }
            }
            if (referencia_max > 0.0) relativo = error_max / referencia_max;
        } else {
            printf("Autoprueba FFT: error ESP-DSP %s\n", esp_err_to_name(error));
        }
        std::free(reserva);
    } else {
        printf("Autoprueba FFT: no se pudo reservar memoria temporal\n");
    }
    const bool pasa = finitos && std::isfinite(relativo) && relativo < 1e-4;
    const int64_t duracion = esp_timer_get_time() - inicio;
    printf("Validación FFT ESP-DSP vs DFT directa (N 256): error máx %.9g, relativo %.9g → %s\n",
           error_max, relativo, pasa ? "PASS" : "FAIL");
    printf("Autoprueba FFT: %.3f ms (incluye señal, FFT, DFT, comparación y memoria temporal)\n",
           duracion / 1000.0);
    return pasa;
}

static void modificar_espectro()
{
    // Sin ocho tramas reales aún no hay piso estimado: dejar pasar la entrada.
    const bool listo = tramas_ruido == TRAMAS_RUIDO;
    // Reponer el conjugado de cada bin positivo conserva una salida real.
    for (int k = 0; k <= n_actual / 2; ++k) {
        float ganancia = 1.0f;
        if (listo) {
            const float magnitud = std::max(magnitudes[k], EPSILON);
            const float resta = 1.0f - configuracion.alfa * piso_ruido[k] / magnitud;
            ganancia = std::max(configuracion.ganancia_minima, std::min(resta, 1.0f));
        }
        // Una ganancia real común a ambas partes conserva la fase de este bin.
        fft[2 * k] *= ganancia;
        fft[2 * k + 1] *= ganancia;
        if (k > 0 && k < n_actual / 2) {
            fft[2 * (n_actual - k)] = fft[2 * k];
            fft[2 * (n_actual - k) + 1] = -fft[2 * k + 1];
        }
    }
    // DC y Nyquist son reales y no tienen una pareja distinta.
    fft[1] = 0.0f;
    fft[n_actual + 1] = 0.0f;
}

static void procesar_salto(const float* entrada, float* salida)
{
    std::memcpy(historial, historial + h_actual, h_actual * sizeof(float));
    std::memcpy(historial + h_actual, entrada, h_actual * sizeof(float));
    for (int j = 0; j < n_actual; ++j) {
        fft[2 * j] = historial[j] * ventana[j * (ESPECTRAL_N / n_actual)];
        fft[2 * j + 1] = 0.0f;
    }
    ESP_ERROR_CHECK(dsps_fft2r_fc32(fft, n_actual));
    ESP_ERROR_CHECK(dsps_bit_rev_fc32(fft, n_actual));
    estimar_ruido();
    modificar_espectro();

    // ESP-DSP entrega la FFT sin normalizar: IFFT(X) = conj(FFT(conj(X))) / N.
    for (int j = 0; j < n_actual; ++j) fft[2 * j + 1] = -fft[2 * j + 1];
    ESP_ERROR_CHECK(dsps_fft2r_fc32(fft, n_actual));
    ESP_ERROR_CHECK(dsps_bit_rev_fc32(fft, n_actual));
    const float ESCALA = 1.0f / n_actual;

    // Solo se usa la parte real: el conjugado final no la cambia.
    // La normalización 1/N se aplica aquí, junto a la ventana de síntesis.
    // w[j]^2 + w[j+H]^2 = Hann[j] + Hann[j+H] = 1, sin otra escala.
    // La primera salida corresponde a H ceros; la segunda reconstruye el bloque 0.
    for (int j = 0; j < h_actual; ++j) {
        salida[j] = solape[j] + fft[2 * j] * ESCALA * ventana[j * (ESPECTRAL_N / n_actual)];
        solape[j] = fft[2 * (j + h_actual)] * ESCALA * ventana[(j + h_actual) * (ESPECTRAL_N / n_actual)];
    }
}

void espectral_procesar(const float* entrada, float* salida)
{
    for (int offset = 0; offset < ESPECTRAL_H; offset += h_actual)
        procesar_salto(entrada + offset, salida + offset);
}

unsigned espectral_n() { return static_cast<unsigned>(n_actual); }
unsigned espectral_h() { return static_cast<unsigned>(h_actual); }

bool espectral_cambiar_n(unsigned n)
{
    if (n != 256 && n != 512 && n != 1024) return false;
    if (n == static_cast<unsigned>(n_actual)) return true;
    n_actual = static_cast<int>(n);
    h_actual = n_actual / 2;
    bins_actual = h_actual + 1;
    espectral_reiniciar();
    return true;
}

EnergiaEspectral espectral_medir(const float* muestras, double banda_lo,
                                double banda_hi, double pico_hz)
{
    // El audio de la llamada anterior ya está reconstruido. Se puede reutilizar
    // fft sin modificar historial, solape, magnitudes ni la historia del ruido.
    for (int j = 0; j < n_actual; ++j) {
        fft[2 * j] = muestras[j] * ventana[j * (ESPECTRAL_N / n_actual)];
        fft[2 * j + 1] = 0.0f;
    }
    ESP_ERROR_CHECK(dsps_fft2r_fc32(fft, n_actual));
    ESP_ERROR_CHECK(dsps_bit_rev_fc32(fft, n_actual));
    const bool tiene_pico = std::isfinite(pico_hz) && pico_hz >= 100.0 && pico_hz <= 3000.0;
    const int bin_pico = tiene_pico ? static_cast<int>(std::lround(pico_hz * n_actual / 8000.0)) : -10;
    EnergiaEspectral energia;
    for (int k = 0; k <= n_actual / 2; ++k) {
        const double hz = k * 8000.0 / n_actual;
        if (hz < 100.0 || hz > 3000.0) continue;
        const double real = fft[2 * k], imaginaria = fft[2 * k + 1];
        const double peso = k == 0 || k == n_actual / 2 ? 1.0 : 2.0;
        const double potencia = peso * (real * real + imaginaria * imaginaria) / n_actual;
        if (hz >= banda_lo && hz <= banda_hi) energia.dentro += potencia;
        else energia.fuera += potencia;
        if (tiene_pico && k >= bin_pico - 2 && k <= bin_pico + 2) energia.pico += potencia;
    }
    return energia;
}
