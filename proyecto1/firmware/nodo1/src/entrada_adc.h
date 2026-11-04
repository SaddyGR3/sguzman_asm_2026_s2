#pragma once
#include <cstdint>

struct ContadoresAdc {
    uint32_t desbordes_pool = 0;   // eventos, no cantidad exacta de muestras perdidas
    uint32_t desalineaciones = 0;
    uint32_t saturaciones = 0;
};

struct ResumenCanalAdc {
    uint16_t crudo_min = 4095;
    uint16_t crudo_max = 0;
    int mv_min = 0;
    int mv_max = 0;
    double frecuencia_adc = 0.0;
    double frecuencia_salida = 0.0;
};

struct ResumenAdc {
    ResumenCanalAdc x, s;
    uint32_t procesamiento_max_us = 0;
    uint32_t calibracion_max_us = 0;
    uint32_t filtrado_max_us = 0;
    ContadoresAdc acumulados;
};

void entrada_adc_iniciar();
// Completa 512 salidas por canal consumiendo 1536 pares. Devuelve el tiempo
// de procesamiento del bloque en us, excluidas las esperas de adquisición.
uint32_t entrada_adc_leer_bloque(float* x, float* s);
ContadoresAdc entrada_adc_contadores();
// Cierra la ventana de medición; reinicia sus estadísticas, no los acumulados.
ResumenAdc entrada_adc_resumen();
