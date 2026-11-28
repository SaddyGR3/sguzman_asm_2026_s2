#pragma once
#include <Arduino.h>

namespace Medicion {
enum class Estado { SinPulsos, UnaMarca, Reciente, Antigua, SinSenal, Sospechosa, Desbordamiento };
struct Lectura {
  float rpm;  // NaN cuando no es utilizable. Nunca inventa un cero de control.
  float rpmUltimaValida;
  float rpmCruda;
  uint32_t periodoUs;  // Duracion de la vuelta usada para RPM, no del ultimo sector.
  uint32_t antiguedadUs;
  uint32_t instanteUs;
  uint32_t pulsosAceptados;
  uint32_t pulsosRechazados;
  uint32_t saltosRechazados;
  uint32_t perdidosCola;
  uint32_t ultimoPeriodoRechazadoUs;
  bool disponible;
  bool valida;
  Estado estado;
};
void iniciar();
void actualizar();
bool diagnosticoActivo();
void configurarDiagnostico(bool activo);
void registrarDiagnostico();
void reiniciar();
Lectura leerLectura();
const char *nombreEstado(Estado estado);
bool leerInicio(uint32_t &inicio);
float calcularRPM(uint32_t ahoraUs);  // Solo presentacion historica.
void leerConteos(uint32_t &aceptados, uint32_t &rechazados);
}
