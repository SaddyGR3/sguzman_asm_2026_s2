#pragma once

constexpr int COEFICIENTES_FIR = 37;

struct CoeficientesFiltros {
    float fir[COEFICIENTES_FIR];
    float b[3];
    float a[3];
};

struct ConfiguracionFiltros {
    double banda_inferior_hz;
    double banda_superior_hz;
    double notch_hz;
    double q_notch;
};

// Prepara los valores iniciales: banda 100-1200 Hz y notch 2150 Hz, Q 8.5.
void filtros_iniciar();
// Conserva los coeficientes y parámetros vigentes al iniciar otra escucha.
void filtros_reiniciar_estados();
const CoeficientesFiltros& filtros_coeficientes();
const ConfiguracionFiltros& filtros_configuracion();
// Recalcula solo el filtro indicado y reinicia únicamente su estado.
// El llamador valida los rangos antes de usar estas funciones.
void filtros_cambiar_banda(double inferior_hz, double superior_hz);
void filtros_cambiar_notch(double frecuencia_hz, double q);
// Actualiza ambos filtros por muestra, sin recorte; entrada no finita se trata como 0.
void filtros_procesar(float entrada, float& salida_fir, float& salida_notch);
