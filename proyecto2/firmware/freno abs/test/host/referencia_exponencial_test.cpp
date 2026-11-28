#include "referencia.h"
#include <cassert>
#include <cmath>
#include <cstdint>
#include <iostream>
int main() {
  using Referencia::Tipo;
  for(float n : {333.0f,900.0f,1300.0f}) {
    for(uint32_t duracion : {3000U,6000U,12000U}) {
      assert(Referencia::iniciar(Tipo::Exponencial,n,duracion,100));
      assert(std::fabs(Referencia::evaluar(100)-n)<.001f);
      const float medio=n*(std::exp(-1.0f)-std::exp(-2.0f))/(1-std::exp(-2.0f));
      assert(std::fabs(Referencia::evaluar(100+duracion/2)-medio)<.001f);
      assert(Referencia::evaluar(100+duracion)==0);
      float anterior=n;
      for(uint32_t dt=0;dt<=duracion+100;dt+=7) {
        const float actual=Referencia::evaluar(100+dt);
        assert(actual>=0 && actual<=anterior);anterior=actual;
      }
    }
  }
  const uint32_t inicio=UINT32_MAX-1000;
  assert(Referencia::iniciar(Tipo::Exponencial,1300,6000,inicio));
  const float esperado=1300*(std::exp(-1.0f)-std::exp(-2.0f))/(1-std::exp(-2.0f));
  assert(std::fabs(Referencia::evaluar(inicio+3000U)-esperado)<.001f);
  assert(Referencia::evaluar(inicio+6000U)==0);
  assert(!Referencia::iniciar(Tipo::Exponencial,NAN,6000,0));
  assert(!Referencia::iniciar(static_cast<Tipo>(2),1300,6000,0));
  assert(!Referencia::disponible());
  std::cout<<"Exponencial normalizada, extremos, escala, monotonia y reloj correctos\n";
}
