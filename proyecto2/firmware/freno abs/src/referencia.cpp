#include "referencia.h"
#include <math.h>

namespace Referencia {
namespace {
float inicialRpm = 0.0f;
uint32_t duracion = 0;
uint32_t inicio = 0;
bool configurada = false;
Tipo tipoActual = Tipo::Lineal;
}

void reiniciar() {
  inicialRpm = 0.0f;
  duracion = inicio = 0;
  configurada = false;
}

bool disponible() { return configurada; }

bool iniciarLineal(float rpmInicial, uint32_t duracionMs, uint32_t inicioMs) {
  return iniciar(Tipo::Lineal, rpmInicial, duracionMs, inicioMs);
}

bool iniciar(Tipo tipo, float rpmInicial, uint32_t duracionMs, uint32_t inicioMs) {
  reiniciar();
  if (!isfinite(rpmInicial) || rpmInicial < 0.0f || duracionMs == 0 ||
      (tipo != Tipo::Lineal && tipo != Tipo::Exponencial)) return false;
  tipoActual = tipo;
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
  if (tipoActual == Tipo::Lineal) return inicialRpm * fraccionRestante;
  const float x = static_cast<float>(transcurrido) / duracion;
  const float fraccion = (expf(-formaExponencial*x) - expf(-formaExponencial)) /
                         (-expm1f(-formaExponencial));
  return inicialRpm * (fraccion < 0 ? 0 : (fraccion > 1 ? 1 : fraccion));
}
}
