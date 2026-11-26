#include <Arduino.h>
#include "control_pid.h"
#include "configuracion.h"
#include "ensayos.h"
#include "medicion.h"
#include "referencia.h"

namespace ControlPID {
namespace {
PID::Controlador controlador;
uint32_t tiempoCalculoUs = 0;
}
void iniciar() {
  controlador.configurar({Configuracion::pidKp, Configuracion::pidKi,
      Configuracion::pidKd, Configuracion::pidTauDerivadaS,
      Configuracion::periodoPidUs, Configuracion::intervaloMaximoPidUs});
  tiempoCalculoUs = 0;
}
void reiniciar() { controlador.reiniciar(); tiempoCalculoUs = 0; }
const PID::Resultado &leer() { return controlador.leer(); }
uint32_t leerTiempoCalculoUs() { return tiempoCalculoUs; }

void actualizar() {
  if (Ensayos::leerEstado() != Ensayos::Estado::Fijo || !Referencia::disponible()) return;
  const uint32_t inicioCalculo = micros();
  const Medicion::Lectura l = Medicion::leerLectura();
  const uint32_t ahora = micros();
  const float referencia = Referencia::evaluar(millis());
  if (controlador.actualizar(referencia, {l.rpm, l.instanteUs, l.valida}, ahora))
    tiempoCalculoUs = micros() - inicioCalculo;
  // Modo de observacion. Aqui no se escribe al servo ni al motor.
}
const char *nombreEstado() {
  switch (controlador.leer().estado) {
    case PID::Estado::Inactivo: return "INACTIVO";
    case PID::Estado::SinConfigurar: return "SIN_CONFIGURAR";
    case PID::Estado::Valido:
      return Configuracion::pidKp == 0 && Configuracion::pidKi == 0 && Configuracion::pidKd == 0
          ? "GANANCIAS_CERO" : "OBSERVACION";
    case PID::Estado::MedicionInvalida: return "MEDICION_INVALIDA";
    case PID::Estado::EntradaInvalida: return "ENTRADA_INVALIDA";
    case PID::Estado::TiempoExcedido: return "TIEMPO_EXCEDIDO";
    case PID::Estado::ErrorNumerico: return "ERROR_NUMERICO";
  }
  return "DESCONOCIDO";
}
}
