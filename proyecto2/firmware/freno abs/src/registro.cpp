#include "registro.h"
#include "configuracion.h"
#include "medicion.h"
#include "freno.h"
#include "motor.h"
#include "ensayos.h"
#include "referencia.h"
#include "control_pid.h"
#include <math.h>

namespace Registro {
using namespace Configuracion;
namespace {
bool inicioAnunciado = false;
uint32_t tiempoAnteriorRegistroMs = 0;
bool diagnosticoEmitido = false;
Medicion::Estado estadoAnterior = Medicion::Estado::SinPulsos;
uint32_t tiempoRelativoMs(uint32_t ahoraUs, uint32_t inicioUs) {
  return (ahoraUs - inicioUs) / 1000U;
}
}

void imprimirAyuda() {
  Serial.println("#HELP,auto_fijoN/auto_pid: armar ciclo desde reposo; auto_preparar: acelerar; corte 1400 RPM y ensayo al bajar a 1300 RPM");
  Serial.println("#HELP,Sensor CHANGE con marcas completas; un conteo por ciclo; minimos 100 us provisionales");
  Serial.println("#HELP,sensor_on/sensor_off: observar cambios GPIO34 y conteos de marcas completas");
  Serial.println("#HELP,+/-: paso; pN: paso 1..10; gN: angulo directo 0..90; c/f: contacto; m: marca manual de fuente apagada; v: pulsos y rechazados; r: reiniciar reloj; 0: rampa; s: detener; 90: volver; motor_on/motor_off: motor si esta habilitado");
  Serial.println("#HELP,preparar: liberar y encender; fijoN: apagar motor y frenar a N grados; tiempoN: duracion en ms; estado: consultar; cancelar: apagar y liberar; pid: iniciar ensayo con controlador");
}

void anunciarInicio() {
  Serial.println("#READY: tiempo desde primera RPM valida; movimientos 0..90 grados");
  imprimirAyuda();
  Serial.println("tiempo_ms,rpm,servo_cmd_grados");
}

void reiniciar() {
  inicioAnunciado = false;
  diagnosticoEmitido = false;
  tiempoAnteriorRegistroMs = millis() - intervaloRegistroMs;
  Serial.println("#EVENT,-1,REINICIO,1");
}

void emitirEvento(const char *tipo, int valor, uint32_t instanteUs) {
  uint32_t inicio;
  Serial.print("#EVENT,");
  if (Medicion::leerInicio(inicio)) {
    Serial.print(tiempoRelativoMs(instanteUs, inicio));
  } else {
    Serial.print(-1);  // Todavia no existe un origen de RPM.
  }
  Serial.print(',');
  Serial.print(tipo);
  Serial.print(',');
  Serial.println(valor);
}

void registrarMedicion() {
  const uint32_t ahoraMs = millis();
  if (diagnosticoEmitido && ahoraMs - tiempoAnteriorRegistroMs < intervaloRegistroMs) return;
  diagnosticoEmitido = true;
  tiempoAnteriorRegistroMs = ahoraMs;
  const Medicion::Lectura l = Medicion::leerLectura();
  if (l.estado != estadoAnterior) {
    emitirEvento("ESTADO_MEDICION", static_cast<int>(l.estado), micros());
    estadoAnterior = l.estado;
  }
  uint32_t inicio;
  const bool tieneInicio = Medicion::leerInicio(inicio);
  const uint32_t ahoraUs = micros();
  if (tieneInicio) {
    if (!inicioAnunciado) {
      inicioAnunciado = true;
      Serial.println("#EVENT,0,RPM_INICIO,1");
    }
    Serial.print(tiempoRelativoMs(ahoraUs, inicio)); Serial.print(',');
    Serial.print(Medicion::calcularRPM(ahoraUs), 2); Serial.print(',');
    Serial.println(Freno::leerAngulo());
  }
  Serial.print("#DIAG,");
  if (tieneInicio) Serial.print(tiempoRelativoMs(ahoraUs, inicio));
  else Serial.print(-1);
  Serial.print(','); Serial.print(l.rpmCruda, 2);
  Serial.print(','); Serial.print(l.rpm, 2);
  Serial.print(','); Serial.print(Medicion::nombreEstado(l.estado));
  Serial.print(','); Serial.print(l.antiguedadUs);
  Serial.print(','); Serial.print(l.periodoUs);
  Serial.print(','); Serial.print(l.pulsosAceptados);
  Serial.print(','); Serial.print(l.pulsosRechazados);
  Serial.print(','); Serial.print(l.saltosRechazados);
  Serial.print(','); Serial.print(l.perdidosCola);
  Serial.print(','); Serial.print(l.ultimoPeriodoRechazadoUs);
  Serial.print(','); Serial.print(Ensayos::nombreEstado());
  Serial.print(','); Serial.print(Motor::estaEncendido() ? 1 : 0);
  Serial.print(','); Serial.print(Ensayos::leerTiempoEnsayoMs());
  const float referencia = Referencia::evaluar(ahoraMs);
  const float error = l.valida && isfinite(referencia) ? l.rpm - referencia : NAN;
  Serial.print(','); Serial.print(referencia, 2);
  Serial.print(','); Serial.print(error, 2);
  const PID::Resultado &pid = ControlPID::leer();
  Serial.print(','); Serial.print(pid.solicitada, 4);
  Serial.print(','); Serial.print(Freno::leerAccionAplicada(), 4);
  Serial.print(','); Serial.print(pid.limitada, 4);
  Serial.print(','); Serial.print(pid.p, 4);
  Serial.print(','); Serial.print(pid.i, 4);
  Serial.print(','); Serial.print(pid.d, 4);
  Serial.print(','); Serial.print(ControlPID::nombreEstado());
  Serial.print(','); Serial.print(pid.dtUs);
  Serial.print(','); Serial.print(pid.omitidos);
  Serial.print(','); Serial.println(ControlPID::leerTiempoCalculoUs());
}
}
