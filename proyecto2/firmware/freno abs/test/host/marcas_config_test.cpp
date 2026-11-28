#include "Arduino.h"
#include "configuracion.h"
#include "medicion.h"
#include <cassert>
#include <cmath>
#include <iostream>
uint64_t relojUs = 0;
void (*interrupcion)() = nullptr;
std::vector<std::string> gpio;
std::vector<int> posiciones;
Puerto Serial;
void setup(); void loop();
void pulso(uint32_t periodo) { relojUs += periodo; emitirMarcaPrueba(); loop(); }
int main() {
  using namespace Configuracion;
  setup(); loop();
  const uint32_t periodo = 40000 / marcasPorVuelta;
  for (int i=0; i<2*marcasPorVuelta; ++i) pulso(periodo);
  auto l = Medicion::leerLectura();
  assert(l.valida && std::fabs(l.rpm-1500.0f)<1);
  assert(l.pulsosAceptados == 2*marcasPorVuelta);
  // El mismo limite fisico rechaza 4500 RPM con una, dos y seis marcas.
  pulso(60000000U / (4500 * marcasPorVuelta));
  l = Medicion::leerLectura();
  assert(l.pulsosRechazados == 1);
  assert(l.valida && std::fabs(l.rpm-1500.0f)<1);
  relojUs += 1000001; loop();
  assert(Medicion::leerLectura().estado == Medicion::Estado::SinSenal);
  pulso(periodo); assert(!Medicion::leerLectura().valida);
  for (int i=0; i<marcasPorVuelta; ++i) pulso(periodo);
  assert(Medicion::leerLectura().valida);
  // No producir una RPM parcial mientras se completa la primera vuelta.
  Medicion::reiniciar();
  for (int i=0; i<marcasPorVuelta; ++i) {
    pulso(periodo);
    assert(!Medicion::leerLectura().valida);
  }
  pulso(periodo);
  assert(Medicion::leerLectura().valida);
  assert(Medicion::leerLectura().periodoUs==periodo*marcasPorVuelta);
  if (marcasPorVuelta==2) {
    // Dos sectores desiguales dan la misma vuelta de 40 ms en cada actualizacion.
    Medicion::reiniciar();pulso(20000);pulso(16000);
    assert(!Medicion::leerLectura().valida);
    for (int i=0; i<12; ++i) {
      pulso(i%2 ? 16000 : 24000);
      auto medida=Medicion::leerLectura();
      assert(medida.valida && medida.periodoUs==40000);
      assert(std::fabs(medida.rpm-1500)<.01f);
      assert(std::fabs(medida.rpmCruda-medida.rpm)>100);
    }
    // Perder la cola obliga a empezar una nueva vuelta, sin unir lados de la pausa.
    for (uint32_t i=0;i<capacidadColaPulsos+4;++i) {
      relojUs+=20000;emitirMarcaPrueba();
    }
    Medicion::actualizar();
    assert(Medicion::leerLectura().estado==Medicion::Estado::Desbordamiento);
    for(int i=0;i<marcasPorVuelta;++i) {
      pulso(20000);assert(!Medicion::leerLectura().valida);
    }
    pulso(20000);assert(Medicion::leerLectura().valida);
  }
  std::cout << marcasPorVuelta << " marcas, RPM, filtro y recuperacion correctos\n";
}
