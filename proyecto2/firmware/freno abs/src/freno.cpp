#include <Arduino.h>
#include <ESP32Servo.h>
#include "freno.h"
#include "configuracion.h"
#include "registro.h"

namespace Freno {
using namespace Configuracion;
namespace {
Servo servo;
int posicionActual = anguloLiberado;
int pasoGrados = 1;
bool moviendo = false;
uint32_t tiempoAnteriorServoMs = 0;
}

void iniciar() {
  servo.setPeriodHertz(50);
  servo.attach(pinServo, 500, 2400);
  servo.write(posicionActual);
}

void fijarAngulo(int nuevoAngulo) {
  if (nuevoAngulo < anguloMinimo || nuevoAngulo > anguloMaximo) {
    Registro::emitirEvento("ANGULO_INVALIDO", nuevoAngulo, micros());
    return;
  }

  moviendo = false;
  posicionActual = nuevoAngulo;
  const uint32_t instanteUs = micros();
  servo.write(posicionActual);
  Registro::emitirEvento("SERVO_CMD", posicionActual, instanteUs);
}

int leerAngulo() { return posicionActual; }
int leerPaso() { return pasoGrados; }

void fijarPaso(int paso) {
  if (paso < 1 || paso > 10) {
    Registro::emitirEvento("PASO_INVALIDO", 0, micros());
    return;
  }
  pasoGrados = paso;
  Registro::emitirEvento("PASO_GRADOS", pasoGrados, micros());
}

void iniciarRampa() {
  moviendo = true;
  tiempoAnteriorServoMs = millis();
  Registro::emitirEvento("RAMPA_INICIO", 0, micros());
}

void detenerRampa() {
  moviendo = false;
  Registro::emitirEvento("RAMPA_DETENIDA", posicionActual, micros());
}

void actualizarRampa() {
  if (!moviendo) {
    return;
  }

  const uint32_t intervalo = posicionActual > puntoDesaceleracion
                                 ? velocidadNormal : velocidadLenta;
  if (millis() - tiempoAnteriorServoMs < intervalo) {
    return;
  }
  tiempoAnteriorServoMs = millis();
  if (posicionActual > anguloMinimo) {
    --posicionActual;
    servo.write(posicionActual);
  } else {
    moviendo = false;
    Registro::emitirEvento("RAMPA_FIN", posicionActual, micros());
  }
}
}
