#include <Arduino.h>
#include "comandos.h"
#include "control_pid.h"
#include "ensayos.h"
#include "freno.h"
#include "medicion.h"
#include "motor.h"
#include "registro.h"

void setup() {
  Serial.begin(115200);
  Motor::iniciar();
  Freno::iniciar();
  Medicion::iniciar();
  Registro::anunciarInicio();
  Ensayos::iniciar();
  ControlPID::iniciar();
}

void loop() {
  Medicion::actualizar();
  Comandos::leerComandos();
  Ensayos::actualizar();
  ControlPID::actualizar();
  Freno::actualizarRampa();
  Registro::registrarMedicion();
  Medicion::registrarDiagnostico();
}
