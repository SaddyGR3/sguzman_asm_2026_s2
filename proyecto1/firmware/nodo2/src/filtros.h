#pragma once

constexpr int COEFICIENTES_FIR = 37;

struct CoeficientesFiltros {
    float fir[COEFICIENTES_FIR];
    float b[3];
    float a[3];
};

// Calcula los coeficientes una vez al arrancar y deja los estados en cero.
void filtros_iniciar();
const CoeficientesFiltros& filtros_coeficientes();
// Actualiza ambos filtros por muestra, sin recorte; entrada no finita se trata como 0.
void filtros_procesar(float entrada, float& salida_fir, float& salida_notch);
