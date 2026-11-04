#pragma once
#include "esp_err.h"

// Módulo independiente del protocolo y de la adquisición. No es reentrante:
// sus búferes estáticos son compartidos; usar desde una sola tarea.
// Admite N = 256, 512 o 1024. M y P requieren N/2+1 posiciones.
esp_err_t espectro_iniciar(int n);
// Devuelve la media retirada. 'inicio' permite recorrer una ventana circular
// de N muestras sin copiarla previamente a un arreglo ordenado.
float espectro_magnitudes(const float* x, float* M, int inicio = 0);
void espectro_piso(const float* M, float* P);
float espectro_bin_a_hz(int bin, float fs);
float espectro_hz_a_bin(float hz, float fs);
