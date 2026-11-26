#pragma once
#include <stdint.h>

// Generador independiente del sensor, del servo y del futuro PID.
namespace Referencia {
bool iniciarLineal(float rpmInicial, uint32_t duracionMs, uint32_t inicioMs);
float evaluar(uint32_t ahoraMs);
void reiniciar();
bool disponible();
}
