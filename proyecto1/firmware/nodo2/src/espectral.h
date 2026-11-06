#pragma once
#include "esp_err.h"

constexpr int ESPECTRAL_N = 1024;
constexpr int ESPECTRAL_H = ESPECTRAL_N / 2;

struct ConfiguracionEspectral {
    float alfa = 3.0f;
    float ganancia_minima = 0.05f;
};

// Búferes estáticos compartidos: usar desde una sola tarea, después de iniciar.
esp_err_t espectral_iniciar();
// Configurar entre bloques: alfa en 0.5–10 y ganancia mínima en 0–0.5.
// Si algún valor es inválido, devuelve false sin cambiar la configuración.
bool espectral_configurar(double alfa, double ganancia_minima);
const ConfiguracionEspectral& espectral_configuracion();
// Limpia audio, estimador y solape al reproducir; conserva los parámetros.
void espectral_reiniciar();
// Recibe y entrega H muestras. Resta espectral con retardo de H muestras (64 ms).
// Durante el calentamiento del estimador se mantiene ganancia 1.
// Al terminar, procesar un bloque de ceros para recuperar la última salida.
void espectral_procesar(const float* entrada, float* salida);

struct EnergiaEspectral {
    double dentro = 0.0;
    double fuera = 0.0;
    double pico = 0.0;
};

// Analiza N muestras con la misma ventana y FFT, sin tocar estimador ni solape.
// Solo llamar después de espectral_procesar(), nunca desde otra tarea.
// Energía unilateral normalizada por N; el pico incluye el bin más cercano ±2.
EnergiaEspectral espectral_medir(const float* muestras, double banda_lo,
                                double banda_hi, double pico_hz);
