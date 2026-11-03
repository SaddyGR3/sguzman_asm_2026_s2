#include "filtros.h"
#include <cmath>

constexpr double PI = 3.14159265358979323846;
constexpr double FRECUENCIA_MUESTREO = 8000.0;
constexpr int TAM_HISTORIAL = COEFICIENTES_FIR - 1;
constexpr double TRANSICION_HZ = 600.0;

static CoeficientesFiltros coeficientes;
static ConfiguracionFiltros configuracion;
static float historial[TAM_HISTORIAL];
static int siguiente = 0;  // posición de la muestra más antigua, que se reemplaza
static float z1 = 0.0f;
static float z2 = 0.0f;

// Origen: sim/nodo2.py. I0(x) por serie con parada relativa de 1e-16.
static double bessel_i0(double x)
{
    const double cuadrado = (x / 2.0) * (x / 2.0);
    double termino = 1.0;
    double suma = 1.0;
    for (int k = 1; termino >= 1e-16 * suma; ++k) {
        termino *= cuadrado / (static_cast<double>(k) * k);
        suma += termino;
    }
    return suma;
}

static double pasa_bajas_ideal(double corte_hz, int m)
{
    return m == 0 ? 2.0 * corte_hz / FRECUENCIA_MUESTREO
        : std::sin(2.0 * PI * corte_hz * m / FRECUENCIA_MUESTREO) / (PI * m);
}

void filtros_cambiar_banda(double inferior_hz, double superior_hz)
{
    // sim/nodo2.py: para inferior < 600 Hz se usa solo el pasa bajas;
    // en el otro caso se resta un pasa bajas para formar el pasa banda.
    const bool pasa_banda = inferior_hz >= TRANSICION_HZ;
    const double corte_superior = superior_hz + TRANSICION_HZ / 2.0;
    const double corte_inferior = inferior_hz - TRANSICION_HZ / 2.0;
    const double centro_hz = pasa_banda ? (corte_inferior + corte_superior) / 2.0 : 0.0;
    const double beta = 0.5842 * std::pow(45.0 - 21.0, 0.4) + 0.07886 * (45.0 - 21.0);
    const double denominador = bessel_i0(beta);
    double fir[COEFICIENTES_FIR];
    double suma = 0.0;
    for (int n = 0; n < COEFICIENTES_FIR; ++n) {
        const int m = n - TAM_HISTORIAL / 2;
        const double ideal = pasa_bajas_ideal(corte_superior, m)
            - (pasa_banda ? pasa_bajas_ideal(corte_inferior, m) : 0.0);
        const double posicion = 2.0 * n / TAM_HISTORIAL - 1.0;
        const double ventana = bessel_i0(beta * std::sqrt(1.0 - posicion * posicion)) / denominador;
        fir[n] = ideal * ventana;
        suma += fir[n] * std::cos(2.0 * PI * centro_hz * m / FRECUENCIA_MUESTREO);
    }
    for (int n = 0; n < COEFICIENTES_FIR; ++n) {
        coeficientes.fir[n] = static_cast<float>(fir[n] / suma);
    }
    configuracion.banda_inferior_hz = inferior_hz;
    configuracion.banda_superior_hz = superior_hz;
    for (float& muestra : historial) muestra = 0.0f;
    siguiente = 0;
}

void filtros_cambiar_notch(double frecuencia_hz, double q)
{
    // Notch de segundo orden, con las mismas fórmulas de sim/nodo2.py.
    const double omega = 2.0 * PI * frecuencia_hz / FRECUENCIA_MUESTREO;
    const double g = 1.0 / (1.0 + std::tan(omega / (2.0 * q)));
    coeficientes.b[0] = static_cast<float>(g);
    coeficientes.b[1] = static_cast<float>(-2.0 * g * std::cos(omega));
    coeficientes.b[2] = coeficientes.b[0];
    coeficientes.a[0] = 1.0f;
    coeficientes.a[1] = coeficientes.b[1];
    coeficientes.a[2] = static_cast<float>(2.0 * g - 1.0);
    configuracion.notch_hz = frecuencia_hz;
    configuracion.q_notch = q;
    z1 = z2 = 0.0f;
}

void filtros_iniciar()
{
    filtros_cambiar_banda(100.0, 1200.0);
    filtros_cambiar_notch(2150.0, 8.5);
}

const CoeficientesFiltros& filtros_coeficientes()
{
    return coeficientes;
}

const ConfiguracionFiltros& filtros_configuracion()
{
    return configuracion;
}

void filtros_procesar(float entrada, float& salida_fir, float& salida_notch)
{
    const float x = std::isfinite(entrada) ? entrada : 0.0f;

    // El historial contiene las 36 muestras anteriores, de reciente a antigua
    // al recorrerlo hacia atrás desde la siguiente posición de escritura.
    salida_fir = coeficientes.fir[0] * x;
    int indice = siguiente;
    for (int k = 1; k < COEFICIENTES_FIR; ++k) {
        if (--indice < 0) indice = TAM_HISTORIAL - 1;
        salida_fir += coeficientes.fir[k] * historial[indice];
    }
    historial[siguiente] = x;
    if (++siguiente == TAM_HISTORIAL) siguiente = 0;

    // Forma directa II transpuesta: dos estados que continúan entre bloques.
    salida_notch = coeficientes.b[0] * x + z1;
    z1 = coeficientes.b[1] * x - coeficientes.a[1] * salida_notch + z2;
    z2 = coeficientes.b[2] * x - coeficientes.a[2] * salida_notch;
}
