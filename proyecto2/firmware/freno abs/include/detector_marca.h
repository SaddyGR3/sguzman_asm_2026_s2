#pragma once
#include <stdint.h>

// Cada marca requiere una zona libre estable seguida de una marca estable.
// Los tiempos corresponden a niveles observados entre interrupciones.
// No puede distinguir ruido sostenido de una marca fisica sin mas informacion.
class DetectorMarca {
 public:
  DetectorMarca(uint32_t libreUs, uint32_t marcaUs)
      : minimoLibre(libreUs), minimoMarca(marcaUs) {}
  __attribute__((always_inline)) inline void reiniciar(bool marca, uint32_t ahora) {
    anteriorMarca = marca;
    desde = ahora;
    armado = false;
  }
  __attribute__((always_inline)) inline bool actualizar(bool marca, uint32_t ahora,
                                                       uint32_t &inicioMarca) {
    // Una notificacion repetida del mismo nivel no representa otra transicion.
    if (marca == anteriorMarca) return false;
    const uint32_t duracion = ahora - desde;
    bool completa = false;
    if (!anteriorMarca) {
      if (duracion >= minimoLibre) armado = true;
    } else if (armado && duracion >= minimoMarca) {
      inicioMarca = desde;
      completa = true;
      armado = false;
    }
    anteriorMarca = marca;
    desde = ahora;
    return completa;
  }
 private:
  const uint32_t minimoLibre, minimoMarca;
  bool anteriorMarca = false, armado = false;
  uint32_t desde = 0;
};
