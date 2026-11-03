#pragma once
#include <cstdint>

struct ContadoresDac {
    uint64_t bytes = 0;
    uint32_t desbordes = 0;
};

void salida_dac_iniciar();
// Recibe las 512 muestras de la salida seleccionada, antes de cuantizar.
void salida_dac_input(const float* muestras);
void salida_dac_silencio();
const ContadoresDac& salida_dac_contadores();
