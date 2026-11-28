#pragma once
#include "pid.h"
namespace ControlPID {
void iniciar();
bool listoParaActuar();
void reiniciar();
bool precargarArranque(float accion);
void actualizar();
const PID::Resultado &leer();
const char *nombreEstado();
uint32_t leerTiempoCalculoUs();
}
