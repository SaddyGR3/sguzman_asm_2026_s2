#pragma once
#include <stdint.h>

// Generador independiente del sensor, del servo y del futuro PID.
namespace Referencia {
enum class Tipo { Lineal = 0, Exponencial = 1 };
constexpr float formaExponencial = 2.0f;
bool iniciar(Tipo tipo, float rpmInicial, uint32_t duracionMs, uint32_t inicioMs);
bool iniciarLineal(float rpmInicial, uint32_t duracionMs, uint32_t inicioMs);
float evaluar(uint32_t ahoraMs);
void reiniciar();
bool disponible();
}
