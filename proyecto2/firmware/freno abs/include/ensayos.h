#pragma once
#include <Arduino.h>

namespace Ensayos {
enum class Estado {
  Reposo,
  Preparacion,
  Fijo,
  Pid,
  Finalizado,
  Cancelado,
  Fallo
};

void iniciar();
void preparar();
void iniciarFijo(int angulo);
void iniciarPID();
void fallarControl(const char *motivo);
void configurarDuracion(int duracionMs);
void cancelar();
void actualizar();
void informarEstado();
Estado leerEstado();
const char *nombreEstado();
uint32_t leerTiempoEnsayoMs();
bool estaActivo();
}
