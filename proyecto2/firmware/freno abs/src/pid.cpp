#include "pid.h"
#include <math.h>

namespace PID {
namespace {
float limitar(float valor) { return valor < 0 ? 0 : (valor > 1 ? 1 : valor); }
}
Controlador::Controlador() { reiniciar(); }

void Controlador::invalidar(Estado estado) {
  integral_ = derivadaFiltrada_ = ultimaRpm_ = 0;
  temporizado_ = hayMuestra_ = false;
  resultado_ = {NAN,NAN,NAN,NAN,NAN,NAN,0,omitidos_,false,false,estado};
}
void Controlador::reiniciar() {
  omitidos_ = 0;
  invalidar(configurado_ ? Estado::Inactivo : Estado::SinConfigurar);
}
bool Controlador::precargarIntegral(float accion) {
  // Solo antes del primer calculo. No reajustar la memoria durante el ensayo.
  if (!configurado_ || temporizado_ || !isfinite(accion) || accion < 0 || accion > 1) return false;
  integral_ = accion;
  return true;
}
const Resultado &Controlador::leer() const { return resultado_; }

bool Controlador::configurar(const Parametros &p) {
  configurado_ = isfinite(p.kp) && isfinite(p.ki) && isfinite(p.kd) &&
      p.kp >= 0 && p.ki >= 0 && p.kd >= 0 &&
      isfinite(p.tauDerivadaS) && p.tauDerivadaS > 0 &&
      p.periodoUs > 0 && p.intervaloMaximoUs >= p.periodoUs &&
      p.intervaloMaximoUs < 0x80000000UL;
  if (configurado_) parametros_ = p;
  reiniciar();
  return configurado_;
}

bool Controlador::actualizar(float referencia, const Muestra &m, uint32_t ahora) {
  if (!configurado_) { invalidar(Estado::SinConfigurar); return false; }
  if (!m.valida || !isfinite(m.rpm) || m.rpm < 0 ||
      static_cast<int32_t>(ahora - m.instanteUs) < 0 ||
      (hayMuestra_ && static_cast<int32_t>(m.instanteUs - ultimaMuestraUs_) < 0)) {
    invalidar(Estado::MedicionInvalida); return false;
  }
  if (!isfinite(referencia) || referencia < 0) {
    invalidar(Estado::EntradaInvalida); return false;
  }
  const uint32_t dtUs = temporizado_ ? ahora - ultimoCalculoUs_ : 0;
  if (temporizado_ && dtUs < parametros_.periodoUs) return false;
  if (temporizado_ && dtUs > parametros_.intervaloMaximoUs) {
    omitidos_ += dtUs / parametros_.periodoUs - 1;
    invalidar(Estado::TiempoExcedido);
    resultado_.dtUs = dtUs;
    return false;
  }
  if (temporizado_) omitidos_ += dtUs / parametros_.periodoUs - 1;

  const float error = m.rpm - referencia;
  const float terminoP = parametros_.kp * error;
  if (hayMuestra_ && m.instanteUs != ultimaMuestraUs_) {
    const float dtMuestraS = (m.instanteUs - ultimaMuestraUs_) * 1e-6f;
    const float pendiente = (m.rpm - ultimaRpm_) / dtMuestraS;
    const float alfa = dtMuestraS / (parametros_.tauDerivadaS + dtMuestraS);
    derivadaFiltrada_ += alfa * (pendiente - derivadaFiltrada_);
  }
  // La derivada usa la medicion. Un cambio de referencia no produce un golpe D.
  const float terminoD = parametros_.kd * derivadaFiltrada_;
  const float incremento = parametros_.ki * error * (dtUs * 1e-6f);
  const float candidata = integral_ + incremento;
  const float peticionCandidata = terminoP + candidata + terminoD;
  if (!isfinite(error) || !isfinite(terminoP) || !isfinite(terminoD) ||
      !isfinite(incremento) || !isfinite(candidata) || !isfinite(peticionCandidata)) {
    invalidar(Estado::ErrorNumerico); return false;
  }

  const bool liberar = error < 0;
  if (liberar) {
    // Liberar el freno no borra lo aprendido. El error negativo descarga I.
    // Se permite descargar aun si P + I + D queda bajo el limite inferior.
    integral_ = limitar(candidata);
  }
  else if (!((peticionCandidata > 1 && incremento > 0) ||
             (peticionCandidata < 0 && incremento < 0))) {
    // La integral se expresa en unidades de accion y queda acotada.
    integral_ = limitar(candidata);
  }
  const float solicitada = terminoP + integral_ + terminoD;
  if (!isfinite(solicitada)) { invalidar(Estado::ErrorNumerico); return false; }
  resultado_ = {error,terminoP,integral_,terminoD,solicitada,
                liberar ? 0.0f : limitar(solicitada),dtUs,omitidos_,
                true,liberar,Estado::Valido};
  ultimoCalculoUs_ = ahora;
  ultimaMuestraUs_ = m.instanteUs;
  ultimaRpm_ = m.rpm;
  hayMuestra_ = temporizado_ = true;
  return true;
}
}
