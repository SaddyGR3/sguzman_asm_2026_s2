#include "referencia.h"
#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>
#include <iostream>

bool cerca(float a, float b) { return std::fabs(a-b) < 0.001f; }
int main() {
  Referencia::reiniciar();
  assert(!Referencia::disponible() && std::isnan(Referencia::evaluar(0)));
  for (float inicial : {1500.0f, 900.0f, 333.0f}) {
    assert(Referencia::iniciarLineal(inicial,6000,100));
    assert(cerca(Referencia::evaluar(100),inicial));
    assert(cerca(Referencia::evaluar(2100),inicial*2.0f/3.0f));
    assert(cerca(Referencia::evaluar(4100),inicial/3.0f));
    assert(Referencia::evaluar(6100)==0);
    assert(Referencia::evaluar(10000)==0);
    float anterior=inicial;
    for(uint32_t t=100;t<=7000;t+=7) {
      float actual=Referencia::evaluar(t);
      assert(actual>=0 && actual<=anterior);
      anterior=actual;
    }
  }
  assert(Referencia::iniciarLineal(0,1000,0));
  assert(Referencia::evaluar(500)==0);
  assert(!Referencia::iniciarLineal(1000,0,0));
  assert(std::isnan(Referencia::evaluar(0)));
  assert(!Referencia::iniciarLineal(-1,1000,0));
  assert(!Referencia::iniciarLineal(NAN,1000,0));
  assert(!Referencia::iniciarLineal(INFINITY,1000,0));
  // La fraccion se calcula antes de multiplicar para no desbordar un float finito.
  const float grande=std::numeric_limits<float>::max();
  assert(Referencia::iniciarLineal(grande,30000,0));
  assert(std::isfinite(Referencia::evaluar(1)));
  const uint32_t inicio=UINT32_MAX-1000;
  assert(Referencia::iniciarLineal(1500,6000,inicio));
  assert(cerca(Referencia::evaluar(inicio+2000U),1000));
  assert(cerca(Referencia::evaluar(inicio+4000U),500));
  assert(Referencia::evaluar(inicio+6000U)==0);
  Referencia::reiniciar();
  assert(!Referencia::disponible() && std::isnan(Referencia::evaluar(0)));
  std::cout<<"Referencia lineal, entradas invalidas y reloj correctos\n";
}
