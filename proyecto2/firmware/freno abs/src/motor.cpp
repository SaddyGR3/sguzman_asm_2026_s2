#include <Arduino.h>
#include "motor.h"
#include "configuracion.h"
#include "registro.h"

namespace Motor {
namespace {
bool encendido = false;
uint8_t nivelSalida(bool activar) {
  return activar ? Configuracion::nivelMotorEncendido
                 : (Configuracion::nivelMotorEncendido == HIGH ? LOW : HIGH);
}
}

bool estaHabilitado() { return Configuracion::controlMotorHabilitado; }
bool estaEncendido() { return encendido; }

void iniciar() {
  encendido = false;
  if (!estaHabilitado()) {
    return;
  }
  // Preparar el nivel inactivo antes de convertir el pin en salida.
  digitalWrite(Configuracion::pinMotor, nivelSalida(false));
  pinMode(Configuracion::pinMotor, OUTPUT);
}

bool establecerEncendido(bool activar) {
  if (!estaHabilitado()) {
    Registro::emitirEvento("MOTOR_NO_HABILITADO", activar ? 1 : 0, micros());
    return false;
  }
  const uint32_t instanteUs = micros();
  digitalWrite(Configuracion::pinMotor, nivelSalida(activar));
  encendido = activar;
  // Registra una orden, no una medicion del estado fisico del motor.
  Registro::emitirEvento("MOTOR_CMD", activar ? 1 : 0, instanteUs);
  return true;
}
}
