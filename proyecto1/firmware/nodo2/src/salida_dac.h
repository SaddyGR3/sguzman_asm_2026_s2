#pragma once
#include <cstdint>

struct ContadoresDac {
    uint64_t bytes = 0;
    uint32_t desbordes = 0;
};

void salida_dac_iniciar();
bool salida_dac_disponible();
// Encola 512 muestras; llamar solo cuando haya espacio. El último bloque drena a silencio.
void salida_dac_input(const float* muestras, bool ultimo);
bool salida_dac_terminada();
ContadoresDac salida_dac_contadores();
