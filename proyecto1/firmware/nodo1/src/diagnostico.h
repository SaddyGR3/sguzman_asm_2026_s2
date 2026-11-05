#pragma once
#include <cstdint>

struct ResultadoDiagnostico {
    bool parcial = true;
    uint8_t calentamiento = 1;
    uint8_t tipo_ruido = 0;
    uint8_t filtro_n2 = 0;
    uint8_t metodo = 0;
    float pico_hz = -1.0f;
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
const ResultadoDiagnostico& diagnostico_procesar(const float* x, uint64_t first_sample);
const ResultadoDiagnostico& diagnostico_resultado();
