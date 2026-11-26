#include <Arduino.h>
#include "control_pid.h"
#include "configuracion.h"
#include "ensayos.h"
#include "medicion.h"
#include "referencia.h"
#include "freno.h"
#include "registro.h"
#include <math.h>

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
bool listoParaActuar() {
  return Configuracion::actuacionPIDHabilitada &&
      controlador.leer().estado != PID::Estado::SinConfigurar &&
      (Configuracion::pidKp > 0 || Configuracion::pidKi > 0 || Configuracion::pidKd > 0);
}
void reiniciar() { controlador.reiniciar(); tiempoCalculoUs = 0; }
const PID::Resultado &leer() { return controlador.leer(); }
uint32_t leerTiempoCalculoUs() { return tiempoCalculoUs; }

void actualizar() {
  const bool actuando = Ensayos::leerEstado() == Ensayos::Estado::Pid;
  if ((!actuando && Ensayos::leerEstado() != Ensayos::Estado::Fijo) || !Referencia::disponible()) return;
  const uint32_t inicioCalculo = micros();
  const Medicion::Lectura l = Medicion::leerLectura();
  const uint32_t ahora = micros();
  const float referencia = Referencia::evaluar(millis());
  const bool calculado = controlador.actualizar(referencia, {l.rpm, l.instanteUs, l.valida}, ahora);
  if (calculado) tiempoCalculoUs = micros() - inicioCalculo;
  if (!actuando) return; // El ensayo fijo conserva su angulo.
  const PID::Resultado &r = controlador.leer();
  if (r.disponible) {
    if (calculado && !Freno::aplicarAccion(r.limitada))
      Ensayos::fallarControl("PID_ACCION_INVALIDA");
    return;
  }
  if (r.estado == PID::Estado::MedicionInvalida) {
    // Liberar durante la espera. El fallo persistente lo gestiona el ensayo.
    Freno::aplicarAccion(0);
  } else if (r.estado == PID::Estado::TiempoExcedido) {
    Registro::emitirEvento("PID_RETRASO_US", static_cast<int>(r.dtUs), micros());
    Ensayos::fallarControl("PID_FALLO_TIEMPO");
  } else if (r.estado == PID::Estado::ErrorNumerico) {
    Ensayos::fallarControl("PID_ERROR_NUMERICO");
  } else {
    Ensayos::fallarControl("PID_DATOS_INVALIDOS");
  }
}
const char *nombreEstado() {
  switch (controlador.leer().estado) {
    case PID::Estado::Inactivo: return "INACTIVO";
    case PID::Estado::SinConfigurar: return "SIN_CONFIGURAR";
    case PID::Estado::Valido:
      return Configuracion::pidKp == 0 && Configuracion::pidKi == 0 && Configuracion::pidKd == 0
          ? "GANANCIAS_CERO" : (Ensayos::leerEstado() == Ensayos::Estado::Pid ? "CONTROLANDO" : "OBSERVACION");
    case PID::Estado::MedicionInvalida: return "MEDICION_INVALIDA";
    case PID::Estado::EntradaInvalida: return "ENTRADA_INVALIDA";
    case PID::Estado::TiempoExcedido: return "TIEMPO_EXCEDIDO";
    case PID::Estado::ErrorNumerico: return "ERROR_NUMERICO";
  }
  return "DESCONOCIDO";
}
}
