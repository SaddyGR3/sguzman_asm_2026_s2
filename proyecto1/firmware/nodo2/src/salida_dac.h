#pragma once
#include <cstdint>

struct ContadoresDac {
    uint64_t bytes = 0;
    uint32_t desbordes = 0;
};

void salida_dac_iniciar();
// Recibe los 2048 bytes little-endian de un INPUT ya validado.
void salida_dac_input(const uint8_t* datos);
void salida_dac_silencio();
const ContadoresDac& salida_dac_contadores();
