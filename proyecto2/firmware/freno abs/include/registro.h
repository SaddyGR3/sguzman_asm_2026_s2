#pragma once
#include <Arduino.h>

namespace Registro {
void anunciarInicio();
void reiniciar();
void imprimirAyuda();
void emitirEvento(const char *tipo, int valor, uint32_t instanteUs);
void registrarMedicion();
}
