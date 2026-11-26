#pragma once
#include "pid.h"
namespace ControlPID {
void iniciar();
void reiniciar();
void actualizar();
const PID::Resultado &leer();
const char *nombreEstado();
uint32_t leerTiempoCalculoUs();
}
