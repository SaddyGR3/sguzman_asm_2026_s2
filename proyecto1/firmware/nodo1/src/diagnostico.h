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

struct UmbralesDiagnostico {
    float tonal = DIAG_UMBRAL_TONAL_INICIAL;
    float red = DIAG_UMBRAL_RED_INICIAL;
    float impulsivo = DIAG_UMBRAL_IMPULSIVO_INICIAL;
    float banda = DIAG_UMBRAL_BANDA_INICIAL;
};

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

// N fijo de este nodo: 1024, H=512 y fs=8000. Una sola tarea.
void diagnostico_iniciar();
void diagnostico_banda(float lo, float hi);
const UmbralesDiagnostico& diagnostico_umbrales();
// Nombres: tonal, red, impulsivo y banda; valores finitos en (1, 100].
// Un ajuste válido borra la clasificación, sin reiniciar la ventana de audio.
bool diagnostico_ajustar_umbral(const char* nombre, float valor);
const ResultadoDiagnostico& diagnostico_procesar(const float* x, uint64_t first_sample);
const ResultadoDiagnostico& diagnostico_resultado();
