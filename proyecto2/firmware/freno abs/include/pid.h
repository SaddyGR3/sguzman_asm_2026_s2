#pragma once
#include <stdint.h>

namespace PID {
struct Parametros {
  float kp;
  float ki;
  float kd;
  float tauDerivadaS;
  uint32_t periodoUs;
  uint32_t intervaloMaximoUs;
};
struct Muestra {
  float rpm;
  uint32_t instanteUs;
  bool valida;
};
enum class Estado {
  Inactivo, SinConfigurar, Valido, MedicionInvalida,
  EntradaInvalida, TiempoExcedido, ErrorNumerico
};
struct Resultado {
  float error, p, i, d, solicitada, limitada;
  uint32_t dtUs, omitidos;
  bool disponible, liberacion;
  Estado estado;
};

// No conoce el servo, el sensor, Serial ni el reloj del microcontrolador.
class Controlador {
 public:
  Controlador();
  bool configurar(const Parametros &parametros);
  void reiniciar();
  bool actualizar(float referenciaRpm, const Muestra &muestra, uint32_t ahoraUs);
  const Resultado &leer() const;
 private:
  void invalidar(Estado estado);
  Parametros parametros_{};
  Resultado resultado_{};
  bool configurado_ = false, temporizado_ = false, hayMuestra_ = false;
  uint32_t ultimoCalculoUs_ = 0, ultimaMuestraUs_ = 0, omitidos_ = 0;
  float ultimaRpm_ = 0, derivadaFiltrada_ = 0, integral_ = 0;
};
}
