#include "diagnostico.h"
#include "espectro.h"
#include <cmath>
#include <cstdlib>
#include <cstring>
#include "esp_timer.h"

constexpr int N = 1024, H = 512;
constexpr float FS = 8000.0f;
static float historial[N];
static float magnitudes[N / 2 + 1], piso[N / 2 + 1];
static int mitad = 0;
static bool primera = true;
static float banda_lo = 100.0f, banda_hi = 1200.0f;
static int completos = 0, candidato_anterior = -1, entradas = 0;
static int publicado = -1, ausencias = 0;
static ResultadoDiagnostico resultado;

void diagnostico_iniciar()
{
    memset(historial, 0, sizeof(historial));
    mitad = 0;
    primera = true;
    completos = entradas = ausencias = 0;
    candidato_anterior = publicado = -1;
    resultado = ResultadoDiagnostico{};
}

void diagnostico_banda(float lo, float hi)
{
    banda_lo = lo;
    banda_hi = hi;
    completos = entradas = ausencias = 0;
    candidato_anterior = -1;
    // Se reinician las cuentas. Un publicado previo conserva la retirada de
    // tres ausencias; así banda 100 3000 lo retira tras tres análisis completos.
}

static void persistencia(int candidato)
{
    if (candidato >= 0) {
        entradas = candidato_anterior >= 0 && abs(candidato - candidato_anterior) <= 1
            ? (entradas < 3 ? entradas + 1 : 3) : 1;
    } else {
        entradas = 0;
    }
    candidato_anterior = candidato;

    if (publicado >= 0) {
        if (candidato >= 0 && abs(candidato - publicado) <= 1) {
            publicado = candidato;  // Sigue al bin actual, sin interpolación.
            ausencias = 0;
        } else if (++ausencias >= 3) {
            publicado = -1;
            ausencias = 0;
        }
    }
    if (publicado < 0 && entradas >= 3) {
        publicado = candidato;
        ausencias = 0;
    }
}

const ResultadoDiagnostico& diagnostico_procesar(const float* x, uint64_t first_sample)
{
    memcpy(historial + mitad * H, x, H * sizeof(float));
    resultado = ResultadoDiagnostico{};
    resultado.parcial = primera;
    resultado.inicio_ventana = primera ? 0 : first_sample - H;
    // Primera: bloque + ceros a la derecha. Después: mitad anterior + actual.
    const int inicio = primera ? 0 : (1 - mitad) * H;
    mitad = 1 - mitad;
    primera = false;

    const int64_t comienzo = esp_timer_get_time();
    resultado.dc = espectro_magnitudes(historial, magnitudes, inicio);
    espectro_piso(magnitudes, piso);
    double cuadrados = 0.0;
    for (int k = 0; k <= N / 2; ++k) cuadrados += static_cast<double>(piso[k]) * piso[k];
    resultado.piso_resumen = static_cast<float>(sqrt(cuadrados / (N / 2 + 1)));

    int candidato = -1;
    if (!resultado.parcial) {
        if (completos < 3) ++completos;
        const int desde = static_cast<int>(ceilf(espectro_hz_a_bin(100.0f, FS)));
        const int hasta = static_cast<int>(floorf(espectro_hz_a_bin(3000.0f, FS)));
        for (int k = desde; k <= hasta; ++k) {
            const float hz = espectro_bin_a_hz(k, FS);
            if (hz >= banda_lo && hz <= banda_hi) continue;
            if (magnitudes[k] < magnitudes[k - 1] || magnitudes[k] < magnitudes[k + 1]) continue;
            if (magnitudes[k] <= 6.0f * fmaxf(piso[k], 1e-12f)) continue;
            if (candidato < 0 || magnitudes[k] > magnitudes[candidato]) candidato = k;
        }
        persistencia(candidato);
    }
    resultado.calentamiento = completos < 3 ? 1 : 0;
    if (candidato >= 0) {
        resultado.magnitud_candidato = magnitudes[candidato];
        resultado.piso_local = piso[candidato];
        resultado.contraste_db = 20.0f * log10f(magnitudes[candidato] / fmaxf(piso[candidato], 1e-12f));
    }
    if (publicado >= 0) {
        resultado.tipo_ruido = 1;
        resultado.filtro_n2 = 2;
        resultado.metodo = 1;
        resultado.pico_hz = espectro_bin_a_hz(publicado, FS);
    }
    resultado.tiempo_us = static_cast<uint32_t>(esp_timer_get_time() - comienzo);
    return resultado;
}

const ResultadoDiagnostico& diagnostico_resultado()
{
    return resultado;
}
