#include <Arduino.h>
#include <math.h>
#include "ensayos.h"
#include "configuracion.h"
#include "freno.h"
#include "medicion.h"
#include "motor.h"
#include "registro.h"
#include "referencia.h"
#include "control_pid.h"

namespace Ensayos {
using namespace Configuracion;
namespace {
Estado estado = Estado::Reposo;
uint32_t inicioPreparacionMs = 0;
uint32_t inicioEnsayoMs = 0;
uint32_t pulsosAlPreparar = 0;
uint32_t duracionMs = duracionEnsayoFijoMs;
uint32_t numeroEnsayo = 0;
bool esperandoRecuperacion = false;
uint32_t inicioInvalidaMs = 0;
uint32_t tiempoEnsayoFinalMs = 0;
bool confirmandoFin = false;
uint32_t inicioConfirmacionMs = 0;


void cambiarEstado(Estado nuevo) {
  estado = nuevo;
  informarEstado();
}

void terminar(Estado destino, const char *motivo) {
  const bool eraPID = estado == Estado::Pid;
  if (estado == Estado::Fijo || eraPID) tiempoEnsayoFinalMs = millis() - inicioEnsayoMs;
  esperandoRecuperacion = false;
  confirmandoFin = false;
  ControlPID::reiniciar();
  if (destino != Estado::Finalizado) Referencia::reiniciar();
  Motor::establecerEncendido(false);
  // La orden directa tambien detiene cualquier rampa pendiente.
  if (eraPID) Freno::aplicarAccion(0);
  else Freno::fijarAngulo(anguloLiberado);
  Registro::emitirEvento(motivo, static_cast<int>(numeroEnsayo), micros());
  cambiarEstado(destino);
}
}

const char *nombreEstado() {
  switch (estado) {
    case Estado::Reposo: return "REPOSO";
    case Estado::Preparacion: return "PREPARACION";
    case Estado::Fijo: return "FIJO";
    case Estado::Pid: return "PID";
    case Estado::Finalizado: return "FINALIZADO";
    case Estado::Cancelado: return "CANCELADO";
    case Estado::Fallo: return "FALLO";
  }
  return "DESCONOCIDO";
}


Estado leerEstado() { return estado; }

bool estaActivo() {
  return estado == Estado::Preparacion || estado == Estado::Fijo || estado == Estado::Pid;
}

void informarEstado() {
  // Texto de diagnostico separado del CSV y de los eventos numericos.
  Serial.print("#ESTADO,");
  Serial.println(nombreEstado());
}

void iniciar() {
  estado = Estado::Reposo;
  duracionMs = duracionEnsayoFijoMs;
  numeroEnsayo = 0;
  Referencia::reiniciar();
  informarEstado();
}

void configurarDuracion(int nuevaDuracionMs) {
  if (estaActivo()) {
    Registro::emitirEvento("ENSAYO_OCUPADO", 0, micros());
    return;
  }
  if (nuevaDuracionMs < static_cast<int>(duracionMinimaEnsayoMs) ||
      nuevaDuracionMs > static_cast<int>(duracionMaximaEnsayoMs)) {
    Registro::emitirEvento("DURACION_INVALIDA", nuevaDuracionMs, micros());
    return;
  }
  duracionMs = static_cast<uint32_t>(nuevaDuracionMs);
  Registro::emitirEvento("ENSAYO_DURACION_MS", nuevaDuracionMs, micros());
}

void preparar() {
  if (estaActivo()) {
    Registro::emitirEvento("ENSAYO_OCUPADO", 0, micros());
    return;
  }
  if (!Motor::estaHabilitado()) {
    Registro::emitirEvento("MOTOR_NO_HABILITADO", 1, micros());
    return;
  }
  Referencia::reiniciar();
  ControlPID::reiniciar();
  Freno::fijarAngulo(anguloLiberado);
  uint32_t rechazados;
  Medicion::leerConteos(pulsosAlPreparar, rechazados);
  if (!Motor::establecerEncendido(true)) {
    terminar(Estado::Fallo, "FALLO_MOTOR");
    return;
  }
  inicioPreparacionMs = millis();
  esperandoRecuperacion = false;
  tiempoEnsayoFinalMs = 0;
  cambiarEstado(Estado::Preparacion);
}

namespace {
void iniciarEnsayo(Estado modo, int angulo) {
  if (estado != Estado::Preparacion) {
    Registro::emitirEvento("REQUIERE_PREPARAR", 0, micros());
    return;
  }
  if (millis() - inicioPreparacionMs >= tiempoMaximoPreparacionMs) {
    terminar(Estado::Fallo, "FALLO_TIEMPO_PREPARACION");
    return;
  }
  if (angulo < anguloMinimoEnsayo || angulo > anguloMaximoEnsayo) {
    Registro::emitirEvento("ANGULO_ENSAYO_INVALIDO", angulo, micros());
    return;
  }
  const Medicion::Lectura lectura = Medicion::leerLectura();
  if (!lectura.valida || !isfinite(lectura.rpm) || lectura.rpm <= 0.0f ||
      lectura.antiguedadUs > antiguedadMaximaInicioUs ||
      lectura.pulsosAceptados - pulsosAlPreparar < 2) {
    // Se puede reintentar mientras no venza el tiempo de preparacion.
    Registro::emitirEvento("MEDICION_INICIO_INVALIDA", 0, micros());
    return;
  }
  if (!Motor::establecerEncendido(false)) {
    terminar(Estado::Fallo, "FALLO_MOTOR");
    return;
  }
  ++numeroEnsayo;
  inicioEnsayoMs = millis();
  ControlPID::reiniciar();
  if (!Referencia::iniciarLineal(lectura.rpm, duracionMs, inicioEnsayoMs)) {
    terminar(Estado::Fallo, "FALLO_REFERENCIA");
    return;
  }
  esperandoRecuperacion = false;
  tiempoEnsayoFinalMs = 0;
  Registro::emitirEvento(modo == Estado::Pid ? "ENSAYO_PID_INICIO" : "ENSAYO_FIJO_INICIO", static_cast<int>(numeroEnsayo), micros());
  Registro::emitirEvento("ENSAYO_DURACION_MS", static_cast<int>(duracionMs), micros());
  Registro::emitirEvento("RPM_INICIAL_X100", static_cast<int>(lectura.rpm * 100.0f + 0.5f), micros());
  Registro::emitirEvento("REFERENCIA_LINEAL_MS", static_cast<int>(duracionMs), micros());
  Freno::fijarAngulo(angulo);
  if (modo == Estado::Pid) Freno::aplicarAccion(0);
  confirmandoFin = false;
  cambiarEstado(modo);
}

}

void iniciarFijo(int angulo) { iniciarEnsayo(Estado::Fijo, angulo); }

void iniciarPID() {
  if (!actuacionPIDHabilitada) {
    Registro::emitirEvento("PID_ACTUACION_DESHABILITADA", 0, micros());
    return;
  }
  if (!ControlPID::listoParaActuar()) {
    Registro::emitirEvento("PID_GANANCIAS_NO_CONFIGURADAS", 0, micros());
    return;
  }
  iniciarEnsayo(Estado::Pid, anguloLiberado);
}

void fallarControl(const char *motivo) {
  if (estado == Estado::Pid) terminar(Estado::Fallo, motivo);
}

void cancelar() {
  // Disponible tambien desde reposo o un estado terminal y en modo manual.
  terminar(Estado::Cancelado, "ENSAYO_CANCELADO");
}

uint32_t leerTiempoEnsayoMs() {
  return (estado == Estado::Fijo || estado == Estado::Pid) ? millis() - inicioEnsayoMs : tiempoEnsayoFinalMs;
}

void actualizar() {
  const uint32_t ahora = millis();
  if (estaActivo()) {
    const Medicion::Lectura l = Medicion::leerLectura();
    const bool gracia = estado == Estado::Preparacion &&
                        ahora - inicioPreparacionMs < graciaMedicionPreparacionMs;
    if (l.valida || gracia) esperandoRecuperacion = false;
    else if (!esperandoRecuperacion) {
      esperandoRecuperacion = true;
      inicioInvalidaMs = ahora;
    } else if (ahora - inicioInvalidaMs >= falloMedicionPersistenteMs) {
      terminar(Estado::Fallo, "FALLO_MEDICION");
      return;
    }
  }
  if (estado == Estado::Preparacion &&
      ahora - inicioPreparacionMs >= tiempoMaximoPreparacionMs) {
    terminar(Estado::Fallo, "FALLO_TIEMPO_PREPARACION");
  } else if (estado == Estado::Fijo && ahora - inicioEnsayoMs >= duracionMs) {
    // Es un final por tiempo. No certifica que el disco este detenido.
    terminar(Estado::Finalizado, "ENSAYO_FIN_DURACION");
  } else if (estado == Estado::Pid && ahora - inicioEnsayoMs >= duracionMs) {
    const Medicion::Lectura l = Medicion::leerLectura();
    if (l.valida && l.rpm <= rpmFinPid) {
      if (!confirmandoFin) { confirmandoFin = true; inicioConfirmacionMs = ahora; }
      else if (ahora - inicioConfirmacionMs >= confirmacionFinPidMs) {
        terminar(Estado::Finalizado, "ENSAYO_PID_FIN_BAJA_RPM");
        return;
      }
    } else confirmandoFin = false;
    if (ahora - inicioEnsayoMs - duracionMs >= tiempoExtraFinPidMs)
      terminar(Estado::Fallo, "PID_FIN_NO_CONFIRMADO");
  }
}
}
