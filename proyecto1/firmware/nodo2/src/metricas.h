#pragma once
#include <cstdint>

struct ConfiguracionMetricas {
    double banda_lo = 100.0, banda_hi = 1200.0;
    double pico_hz = -1.0;
    double notch_hz = 2150.0, notch_q = 8.5;
    double alfa = 3.0, ganancia_minima = 0.05;
};

struct TiempoMetricas {
    uint64_t temporal_us = 0;  // suma de FFT FIR y notch, para el monitor
    uint64_t fir_us = 0, notch_us = 0;
    uint64_t espectral_us = 0;
};

// Toda la API se usa en la tarea principal. Conserva el último informe terminado.
void metricas_iniciar(const ConfiguracionMetricas& configuracion);
void metricas_invalidar();  // cambio de configuración durante la reproducción
// Cuatro bloques de H=512 antes del DAC; SIN FILTRO reutiliza x.
// El último es el vaciado existente.
// Devuelve el coste de analizar cada salida; el análisis de x es coste común.
TiempoMetricas metricas_procesar(const float* x, const float* fir,
                                const float* notch, const float* espectral, bool vaciado);
// Tiempos completos por llamada, incluido el vaciado; independientes del monitor.
void metricas_registrar_tiempos(const TiempoMetricas& coste,
                               uint64_t filtros_temporales_us, uint64_t espectral_us,
                               uint64_t total_us, uint64_t metricas_us);
// Captura RAM y resultados antes de aplicar parámetros pendientes o imprimir.
void metricas_finalizar();
void metricas_imprimir();
