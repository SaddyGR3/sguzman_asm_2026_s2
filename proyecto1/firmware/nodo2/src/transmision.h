#pragma once
#include <cstdint>

void transmision_iniciar();
// Encola la salida seleccionada para el nodo 3, conservando el índice del INPUT.
void transmision_enviar(const float* muestras, uint64_t first_sample);
uint64_t transmision_enviados();
uint64_t transmision_descartados();
