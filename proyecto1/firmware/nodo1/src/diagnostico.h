#pragma once
#include <cstdint>

constexpr float DIAG_UMBRAL_TONAL_INICIAL = 6.0f;
constexpr float DIAG_UMBRAL_RED_INICIAL = 6.0f;
constexpr float DIAG_UMBRAL_IMPULSIVO_INICIAL = 6.0f;
constexpr float DIAG_UMBRAL_BANDA_INICIAL = 2.0f;
constexpr float DIAG_RMS_MINIMO = 0.0001f;
constexpr float DIAG_OCUPACION_MINIMA = 0.80f;
constexpr float DIAG_FRACCION_PISO = 0.25f;
constexpr float DIAG_PLANITUD_MINIMA = 0.50f;
constexpr unsigned DIAG_FONDO_BLOQUES = 32, DIAG_FONDO_ESPERA = 8;
constexpr int DIAG_SUBBLOQUE = 32, DIAG_SUBBLOQUES_MAX = 4;
constexpr float DIAG_ANCHURA_MAXIMA_HZ = 1000.0f;
constexpr unsigned DIAG_FONDO_PERCENTIL = 95;
constexpr float DIAG_MARGEN_TRANSITORIOS = 1.5f;

struct UmbralesDiagnostico {
    float tonal = DIAG_UMBRAL_TONAL_INICIAL;
    float red = DIAG_UMBRAL_RED_INICIAL;
    float impulsivo = DIAG_UMBRAL_IMPULSIVO_INICIAL;
    float banda = DIAG_UMBRAL_BANDA_INICIAL;
    float fondo = 2.0f;          // RMS / fondo y piso espectral / fondo
    float tonal_pct = 20.0f;     // energía del pico / exceso fuera de protección
    float red_rel = 25.0f;       // magnitud mínima, % del armónico más fuerte
    float red_pct = 20.0f;       // energía de la familia / exceso fuera de protección
    float region_pct = 35.0f;    // exceso de piso en la región / fuera de protección
    float rafaga = 3.0f;         // RMS subbloque / max(mediana de subbloques, fondo)
    float pico_fondo = 3.0f;     // pico temporal / RMS del fondo
};

struct FondoDiagnostico {
    bool listo = false;
    unsigned bloques = 0, espera = DIAG_FONDO_ESPERA;
    float rms = 0.0f;
    // Percentil de máximos por bloque; mismas escalas usadas por impulsivo.
    float corto_p95 = 0.0f, pico_p95 = 0.0f;
};
// Captura explícita y congelada del ambiente; no aprende durante una señal.
void diagnostico_calibrar_fondo();
const FondoDiagnostico& diagnostico_fondo();

struct ResultadoDiagnostico {
    bool parcial = true;
    uint8_t calentamiento = 1;
    uint8_t tipo_ruido = 0;
    uint8_t filtro_n2 = 0;
    uint8_t metodo = 0;
    float pico_hz = -1.0f;
    float banda_detectada_lo = -1.0f;
    float banda_detectada_hi = -1.0f;
    float factor_cresta = 0.0f;
    float contraste_publicado_db = -1.0f;
    // Características del candidato tonal actual, separado del pico publicado.
    float magnitud_candidato = -1.0f;
    float piso_local = -1.0f;
    float contraste_db = -1.0f;
    float piso_resumen = -1.0f;
    float dc = 0.0f;
    uint64_t inicio_ventana = 0;
    uint32_t tiempo_us = 0;
};

constexpr int DIAG_DEBUG_MAX_PICOS = 8;
struct PicoDebug {
    float hz = -1.0f;
    float magnitud = 0.0f;
    float piso = 0.0f;
};
struct GrupoPicosDebug {
    unsigned cantidad = 0;  // total; el arreglo conserva los ocho más fuertes
    PicoDebug picos[DIAG_DEBUG_MAX_PICOS];
};
struct MedidaDebug {
    float actual = -1.0f, minimo = -1.0f, maximo = -1.0f;
};
struct EnergiaPicoDebug {
    float hz = -1.0f;
    double energia = 0.0;
    double porcentaje = 0.0;
};
struct DiagnosticoDebug {
    bool activo = false, ventana_valida = false;
    GrupoPicosDebug red_50, red_60, publicada_50, publicada_60, maximos;
    unsigned confirmaciones_50 = 0, confirmaciones_60 = 0;
    unsigned ausencias_50 = 0, ausencias_60 = 0;
    unsigned armonicos_publicados_50 = 0, armonicos_publicados_60 = 0;
    unsigned familia_elegida = 0;
    float candidato_tonal_hz = -1.0f;
    MedidaDebug rms, pico_temporal, cresta, ocupacion, planitud;
    float referencia_global = -1.0f, umbral_limitada = -1.0f;
    bool ancha_evaluada = false, ancha_candidata = false, ancha_confirmada = false;
    unsigned confirmaciones_ancha = 0, ausencias_ancha = 0;
    float limitada_candidata_lo = -1.0f, limitada_candidata_hi = -1.0f;
    float limitada_publicada_lo = -1.0f, limitada_publicada_hi = -1.0f;
    double energia_region = 0.0, energia_analisis = 0.0;
    EnergiaPicoDebug energia_publicado, energia_candidato;
    unsigned confirmaciones_limitada = 0, ausencias_limitada = 0;
    uint32_t bloques = 0, supera_cresta = 0, confirma_impulsivo = 0;
    uint32_t candidatas_ancha = 0, confirmadas_ancha = 0;
    uint32_t candidatas_limitada = 0, confirmadas_limitada = 0;
    uint32_t tipos[6] = {};
    bool nivel_suficiente = false, impulso_candidato = false;
    unsigned subbloques_fuertes = 0, armonicos_brutos_50 = 0, armonicos_brutos_60 = 0;
    float razon_rafaga = 0.0f;
    float pico_evaluado_hz = -1.0f;
    double exceso_fuera = 0.0, tonal_porcentaje = 0.0;
    double red_porcentaje_50 = 0.0, red_porcentaje_60 = 0.0, region_porcentaje = 0.0;
    uint32_t candidatas_impulsivo = 0;
    float corto_max = 0.0f, corto_min_fondo = 0.0f, pico_min_fondo = 0.0f;
    bool impulso_sobre_fondo = false;
    uint32_t impulsos_rechazados_fondo = 0;
};

// Observación de solo lectura; activar/desactivar no reinicia el clasificador.
void diagnostico_debug_activar(bool activar);
const DiagnosticoDebug& diagnostico_debug();
void diagnostico_debug_reiniciar_contadores();

// INPUT siempre 512; análisis N configurable, H=N/2, fs=8000. Una sola tarea.
bool diagnostico_cambiar_n(unsigned n);
void diagnostico_iniciar(bool calibrar_fondo = true);
void diagnostico_banda(float lo, float hi);
const UmbralesDiagnostico& diagnostico_umbrales();
// Nombres de UmbralesDiagnostico; valores finitos en (1, 100].
// Un ajuste válido borra la clasificación, sin reiniciar la ventana de audio.
bool diagnostico_ajustar_umbral(const char* nombre, float valor);
const ResultadoDiagnostico& diagnostico_procesar(const float* x, uint64_t first_sample);
const ResultadoDiagnostico& diagnostico_resultado();
