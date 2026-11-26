#include "referencia.h"
#include <math.h>

namespace Referencia {
namespace {
float inicialRpm = 0.0f;
uint32_t duracion = 0;
uint32_t inicio = 0;
bool configurada = false;
}

void reiniciar() {
  inicialRpm = 0.0f;
  duracion = inicio = 0;
  configurada = false;
}

bool disponible() { return configurada; }

bool iniciarLineal(float rpmInicial, uint32_t duracionMs, uint32_t inicioMs) {
  reiniciar();
  if (!isfinite(rpmInicial) || rpmInicial < 0.0f || duracionMs == 0) return false;
  inicialRpm = rpmInicial;
  duracion = duracionMs;
  inicio = inicioMs;
  configurada = true;
  return true;
}

float evaluar(uint32_t ahoraMs) {
  if (!configurada) return NAN;
  const uint32_t transcurrido = ahoraMs - inicio;
  if (transcurrido >= duracion) return 0.0f;
  const float fraccionRestante = static_cast<float>(duracion - transcurrido) /
                                static_cast<float>(duracion);
  return inicialRpm * fraccionRestante;
}
}
