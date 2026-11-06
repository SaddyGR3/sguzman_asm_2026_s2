#include "metricas.h"
#include "espectral.h"
#include "filtros.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include <cmath>
#include <cstdio>
#include <cstring>

constexpr int H = ESPECTRAL_H;
constexpr int MODOS = 4, SIN = 0, FIR = 1, NOTCH = 2, RESTA = 3;
constexpr unsigned RETARDO_FIR = (COEFICIENTES_FIR - 1) / 2;
static_assert(RETARDO_FIR < H, "El vaciado FIR debe caber en un bloque");
static const char* const NOMBRES[MODOS] = {"SIN_FILTRO", "FIR", "NOTCH", "RESTA"};
static const unsigned RETARDOS[MODOS] = {0, RETARDO_FIR, 0, H};
constexpr int TOTAL = 4, METRICAS = 5;
constexpr uint32_t MEMORIA = MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT;

struct TiempoAcumulado {
    uint64_t suma = 0, maximo = 0;
};

struct Resumen {
    ConfiguracionMetricas configuracion;
    EnergiaEspectral energia[MODOS];  // x (= SIN FILTRO), FIR, notch, espectral
    double error[MODOS] = {};
    uint64_t muestras = 0;
    uint32_t bloques = 0;
    uint32_t id = 0;
    TiempoAcumulado tiempos[6];  // cuatro modos, total, métricas
    uint64_t cierre_us = 0;  // después del DAC; fuera del plazo por bloque
    size_t ram_libre = 0, ram_bloque = 0;
    const char* estado = "OK";
};

static Resumen actual, ultimas;
static bool activa = false, tiene_ultimas = false, tiene_anterior = false;
static bool cierre_pendiente = false;
static uint32_t siguiente_id = 0;
static float x_anterior[H], fir_anterior[H], notch_anterior[H], espectral_anterior[H];
static float historial[MODOS][ESPECTRAL_N];

static void sumar(TiempoAcumulado& tiempo, uint64_t us)
{
    tiempo.suma += us;
    if (us > tiempo.maximo) tiempo.maximo = us;
}

static uint64_t analizar(int senal)
{
    const int64_t inicio = esp_timer_get_time();
    const auto& c = actual.configuracion;
    const EnergiaEspectral energia = espectral_medir(historial[senal], c.banda_lo, c.banda_hi, c.pico_hz);
    actual.energia[senal].dentro += energia.dentro;
    actual.energia[senal].fuera += energia.fuera;
    actual.energia[senal].pico += energia.pico;
    return static_cast<uint64_t>(esp_timer_get_time() - inicio);
}

void metricas_iniciar(const ConfiguracionMetricas& configuracion)
{
    actual = {};
    actual.configuracion = configuracion;
    actual.id = ++siguiente_id;
    activa = true;
    tiene_anterior = false;
    cierre_pendiente = false;
    std::memset(historial, 0, sizeof(historial));
}

void metricas_invalidar()
{
    if (activa && std::strcmp(actual.estado, "OK") == 0) actual.estado = "CONFIG_CAMBIADA";
}

TiempoMetricas metricas_procesar(const float* x, const float* fir,
                                const float* notch, const float* espectral, bool vaciado)
{
    TiempoMetricas coste;
    if (!activa) return coste;
    const unsigned n = actual.configuracion.n, salto = n / 2;
    if (tiene_anterior) {
        for (unsigned offset = 0; offset < H; offset += salto) {
            for (int s = 0; s < MODOS; ++s)
                std::memmove(historial[s], historial[s] + salto, salto * sizeof(float));
            for (unsigned j = 0; j < salto; ++j) {
                const unsigned posicion = offset + j;
                const unsigned indice_fir = posicion + RETARDO_FIR;
                const unsigned indice_espectral = posicion + salto;
                float valores[MODOS] = {x_anterior[posicion],
                    indice_fir < H ? fir_anterior[indice_fir] : fir[indice_fir - H],
                    notch_anterior[posicion],
                    indice_espectral < H ? espectral_anterior[indice_espectral] : espectral[indice_espectral - H]};
                for (int s = 0; s < MODOS; ++s) {
                    if (!std::isfinite(valores[s])) {
                        actual.estado = "DATOS_NO_FINITOS";
                        valores[s] = 0.0f;
                    }
                    historial[s][salto + j] = valores[s];
                }
                for (int r = 1; r < MODOS; ++r) {
                    const double diferencia = static_cast<double>(valores[r]) - valores[0];
                    actual.error[r] += diferencia * diferencia;
                }
            }
            analizar(0);
            coste.fir_us += analizar(FIR);
            coste.notch_us += analizar(NOTCH);
            coste.espectral_us += analizar(RESTA);
        }
        actual.muestras += H;
        // Las cuatro FFT de borde esperan a que termine el DAC.
        if (vaciado) cierre_pendiente = true;
    }
    if (!vaciado) {
        std::memcpy(x_anterior, x, sizeof(x_anterior));
        std::memcpy(fir_anterior, fir, sizeof(fir_anterior));
        std::memcpy(notch_anterior, notch, sizeof(notch_anterior));
        std::memcpy(espectral_anterior, espectral, sizeof(espectral_anterior));
        tiene_anterior = true;
    } else {
        tiene_anterior = false;
    }
    coste.temporal_us = coste.fir_us + coste.notch_us;
    return coste;
}

void metricas_registrar_tiempos(const TiempoMetricas& coste,
                               uint64_t filtros_temporales_us, uint64_t espectral_us,
                               uint64_t total_us, uint64_t metricas_us)
{
    if (!activa) return;
    ++actual.bloques;
    // FIR y notch comparten filtros_procesar: se informa ese coste conjunto
    // en ambos, NO se deben sumar sus filas para obtener el coste real.
    sumar(actual.tiempos[SIN], 0);  // identidad y energía de x, coste común
    sumar(actual.tiempos[FIR], filtros_temporales_us + coste.fir_us);
    sumar(actual.tiempos[NOTCH], filtros_temporales_us + coste.notch_us);
    sumar(actual.tiempos[RESTA], espectral_us + coste.espectral_us);
    sumar(actual.tiempos[TOTAL], total_us);
    sumar(actual.tiempos[METRICAS], metricas_us);
}

void metricas_finalizar()
{
    if (!activa) return;
    if (cierre_pendiente) {
        const int64_t inicio = esp_timer_get_time();
        const unsigned salto = actual.configuracion.n / 2;
        // Misma ventana de borde y misma energía que antes, sin MSE extra.
        for (int s = 0; s < MODOS; ++s) {
            std::memmove(historial[s], historial[s] + salto, salto * sizeof(float));
            std::memset(historial[s] + salto, 0, salto * sizeof(float));
            analizar(s);
        }
        actual.cierre_us = static_cast<uint64_t>(esp_timer_get_time() - inicio);
        cierre_pendiente = false;
    }
    actual.ram_libre = heap_caps_get_free_size(MEMORIA);
    actual.ram_bloque = heap_caps_get_largest_free_block(MEMORIA);
    if (!actual.muestras) actual.estado = "SIN_MUESTRAS";
    ultimas = actual;
    tiene_ultimas = true;
    activa = false;
}

// No inventar un dB finito con un epsilon. El CSV usa NA para valores indefinidos.
static double razon_db(double numerador, double denominador)
{
    return numerador > 0.0 && denominador > 0.0
        ? 10.0 * std::log10(numerador / denominador) : NAN;
}

static void numero(char* destino, size_t capacidad, double valor)
{
    if (std::isfinite(valor)) std::snprintf(destino, capacidad, "%.6g", valor);
    else std::snprintf(destino, capacidad, "NA");
}

void metricas_imprimir()
{
    if (!tiene_ultimas) {
        printf("Métricas: todavía no hay una reproducción terminada\n");
        return;
    }
    const auto& m = ultimas;
    const auto& c = m.configuracion;
    const bool valida = std::strcmp(m.estado, "OK") == 0;
    const bool tiene_pico = std::isfinite(c.pico_hz) && c.pico_hz >= 100.0 && c.pico_hz <= 3000.0;
    const double divisor = m.bloques ? m.bloques : 1;
    const double proc_total = m.tiempos[TOTAL].suma / divisor;
    const double proc_metricas = m.tiempos[METRICAS].suma / divisor;
    printf("\nMétricas estimadas sin referencia limpia | reproducción %lu | %s | %llu muestras\n",
           (unsigned long)m.id, m.estado, (unsigned long long)m.muestras);
    printf("N %u H %u | banda %.6g-%.6g Hz | pico %.6g Hz | atenuación: %s | MSE respecto de x decodificada\n",
           c.n, c.n / 2, c.banda_lo, c.banda_hi, c.pico_hz, tiene_pico ? "bin del pico ±2" : "fuera de banda");
    printf("Ruta       Modo         SNR x dB   SNR y dB   Delta dB   E banda %%  Aten dB    MSE(x)     Ret ms  Proc ms prom/max  Carga %%\n");
    for (int r = 0; r < MODOS; ++r) {
        const auto& entrada = m.energia[0];
        const auto& salida = m.energia[r];
        const double snr_x = valida ? razon_db(entrada.dentro, entrada.fuera) : NAN;
        const double snr_y = valida ? razon_db(salida.dentro, salida.fuera) : NAN;
        const double conservada = valida && entrada.dentro > 0.0 ? 100.0 * salida.dentro / entrada.dentro : NAN;
        const double atenuacion = valida ? razon_db(tiene_pico ? entrada.pico : entrada.fuera,
                                                   tiene_pico ? salida.pico : salida.fuera) : NAN;
        const double mse = valida && m.muestras ? m.error[r] / m.muestras : NAN;
        const double retardo_ms = (r == RESTA ? c.n / 2 : RETARDOS[r]) / 8.0;
        const double proc_us = m.tiempos[r].suma / divisor;
        const double max_us = m.tiempos[r].maximo;
        const char* ruta = r == RESTA ? "espectral" : "temporal";
        const char* modo = NOMBRES[r];
        char valores[6][24];
        numero(valores[0], sizeof(valores[0]), snr_x);
        numero(valores[1], sizeof(valores[1]), snr_y);
        numero(valores[2], sizeof(valores[2]), snr_y - snr_x);
        numero(valores[3], sizeof(valores[3]), conservada);
        numero(valores[4], sizeof(valores[4]), atenuacion);
        numero(valores[5], sizeof(valores[5]), mse);
        printf("%-10s %-12s %-10s %-10s %-10s %-10s %-10s %-10s %6.2f  %.3f/%.3f  %.2f\n",
               ruta, modo, valores[0], valores[1], valores[2], valores[3], valores[4], valores[5],
               retardo_ms, proc_us / 1000.0, max_us / 1000.0, proc_us / 640.0);
    }
    printf("Proc FIR/NOTCH incluye el cálculo temporal conjunto; no sumar filas. SIN FILTRO reutiliza x.\n");
    printf("Total cuatro modos + métricas + encolado: %.3f ms prom / %.3f ms max | carga %.2f %% prom / %.2f %% max\n",
           proc_total / 1000.0, m.tiempos[TOTAL].maximo / 1000.0,
           proc_total / 640.0, m.tiempos[TOTAL].maximo / 640.0);
    printf("Métricas: %.3f ms prom / %.3f ms max (incluidas en total) | RAM interna libre %lu B, mayor bloque %lu B\n",
           proc_metricas / 1000.0, m.tiempos[METRICAS].maximo / 1000.0,
           (unsigned long)m.ram_libre, (unsigned long)m.ram_bloque);
    printf("Cierre de métricas después del DAC: %.3f ms (fuera de proc/carga por bloque y del CSV METRICAS)\n",
           m.cierre_us / 1000.0);
    if (m.tiempos[TOTAL].maximo >= 64000) printf("Métricas: máximo total alcanzó o superó el plazo de 64 ms\n");
    // Orden fijo CSV v3 (cuatro modos, 35 campos con N/H al final); ninguna cifra usa separador decimal dependiente de consola.
    for (int r = 0; r < MODOS; ++r) {
        const auto& entrada = m.energia[0];
        const auto& salida = m.energia[r];
        const double sx = valida ? razon_db(entrada.dentro, entrada.fuera) : NAN;
        const double sy = valida ? razon_db(salida.dentro, salida.fuera) : NAN;
        char valores[6][24];
        numero(valores[0], sizeof(valores[0]), sx);
        numero(valores[1], sizeof(valores[1]), sy);
        numero(valores[2], sizeof(valores[2]), sy - sx);
        numero(valores[3], sizeof(valores[3]), valida && entrada.dentro > 0.0 ? 100.0 * salida.dentro / entrada.dentro : NAN);
        numero(valores[4], sizeof(valores[4]), valida ? razon_db(tiene_pico ? entrada.pico : entrada.fuera,
                                                               tiene_pico ? salida.pico : salida.fuera) : NAN);
        numero(valores[5], sizeof(valores[5]), valida && m.muestras ? m.error[r] / m.muestras : NAN);
        printf("METRICAS,3,%lu,%s,%s,%s,%.6g,%.6g,%.6g,%s,%s,%s,%s,%s,%s,%.3f,%.3f,%.3f,%.3f,%lu,%lu,%llu,%lu,%.3f,%.3f,%.3f,%.3f,%.3f,%.6g,%.6g,%.6g,%.6g,%s,%u,%u\n",
               (unsigned long)m.id, m.estado, r == RESTA ? "espectral" : "temporal", NOMBRES[r],
               c.banda_lo, c.banda_hi, c.pico_hz, valores[0], valores[1], valores[2], valores[3], valores[4], valores[5],
               (r == RESTA ? c.n / 2 : RETARDOS[r]) / 8.0,
               m.tiempos[r].suma / divisor / 1000.0, m.tiempos[r].maximo / 1000.0,
               m.tiempos[r].suma / divisor / 640.0,
               (unsigned long)m.ram_libre, (unsigned long)m.ram_bloque,
               (unsigned long long)m.muestras, (unsigned long)m.bloques,
               proc_total / 1000.0, m.tiempos[TOTAL].maximo / 1000.0, proc_total / 640.0,
               proc_metricas / 1000.0, m.tiempos[METRICAS].maximo / 1000.0,
               c.notch_hz, c.notch_q, c.alfa, c.ganancia_minima,
               tiene_pico ? "pico" : "fuera_banda", c.n, c.n / 2);
    }
}
