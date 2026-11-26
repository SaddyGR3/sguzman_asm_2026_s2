#include <Arduino.h>
#include <math.h>
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
float accionAplicada = NAN;
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
  accionAplicada = NAN;
  posicionActual = nuevoAngulo;
  const uint32_t instanteUs = micros();
  servo.write(posicionActual);
  Registro::emitirEvento("SERVO_CMD", posicionActual, instanteUs);
}

int anguloParaAccion(float accion) {
  if (!isfinite(accion)) return -1;
  if (accion < 0) accion = 0;
  if (accion > 1) accion = 1;
  const float angulo = anguloLiberado - (anguloLiberado - anguloMinimoEnsayo) * accion;
  return static_cast<int>(angulo + 0.5f);
}

bool aplicarAccion(float accion) {
  const int angulo = anguloParaAccion(accion);
  if (angulo < anguloMinimoEnsayo || angulo > anguloLiberado) return false;
  moviendo = false;
  // No volver a escribir ni emitir un evento si no cambia el grado ordenado.
  if (angulo != posicionActual) fijarAngulo(angulo);
  accionAplicada = static_cast<float>(anguloLiberado - angulo) /
                   (anguloLiberado - anguloMinimoEnsayo);
  return true;
}

float leerAccionAplicada() { return accionAplicada; }

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
  accionAplicada = NAN;
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
