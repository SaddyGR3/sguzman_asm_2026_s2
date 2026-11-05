#pragma once
#include "esp_err.h"

constexpr int ESPECTRAL_N = 1024;
constexpr int ESPECTRAL_H = ESPECTRAL_N / 2;

// Búferes estáticos compartidos: usar desde una sola tarea, después de iniciar.
esp_err_t espectral_iniciar();
// Limpia el historial y el solape al empezar cada reproducción.
void espectral_reiniciar();
// Recibe y entrega H muestras. Ganancia 1 y retardo de H muestras (64 ms).
// Al terminar, procesar un bloque de ceros para recuperar la última salida.
void espectral_procesar(const float* entrada, float* salida);
