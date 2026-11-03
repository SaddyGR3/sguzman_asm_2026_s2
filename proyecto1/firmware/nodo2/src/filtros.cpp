#include "filtros.h"
#include <cmath>

constexpr double PI = 3.14159265358979323846;
constexpr double FRECUENCIA_MUESTREO = 8000.0;
constexpr double CORTE_FIR = 1500.0;
constexpr double FRECUENCIA_NOTCH = 2150.0;
constexpr double Q_NOTCH = 8.5;
constexpr int TAM_HISTORIAL = COEFICIENTES_FIR - 1;

static CoeficientesFiltros coeficientes;
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

void filtros_iniciar()
{
    // Sinc por Kaiser, normalizada a ganancia 1 en continua, todo en double.
    const double beta = 0.5842 * std::pow(45.0 - 21.0, 0.4) + 0.07886 * (45.0 - 21.0);
    const double denominador = bessel_i0(beta);
    double fir[COEFICIENTES_FIR];
    double suma = 0.0;
    for (int n = 0; n < COEFICIENTES_FIR; ++n) {
        const int m = n - TAM_HISTORIAL / 2;
        const double ideal = m == 0 ? 2.0 * CORTE_FIR / FRECUENCIA_MUESTREO
            : std::sin(2.0 * PI * CORTE_FIR * m / FRECUENCIA_MUESTREO) / (PI * m);
        const double posicion = 2.0 * n / TAM_HISTORIAL - 1.0;
        const double ventana = bessel_i0(beta * std::sqrt(1.0 - posicion * posicion)) / denominador;
        fir[n] = ideal * ventana;
        suma += fir[n];
    }
    for (int n = 0; n < COEFICIENTES_FIR; ++n) {
        coeficientes.fir[n] = static_cast<float>(fir[n] / suma);
    }

    // Notch de segundo orden, con las mismas fórmulas de sim/nodo2.py.
    const double omega = 2.0 * PI * FRECUENCIA_NOTCH / FRECUENCIA_MUESTREO;
    const double g = 1.0 / (1.0 + std::tan(omega / (2.0 * Q_NOTCH)));
    coeficientes.b[0] = static_cast<float>(g);
    coeficientes.b[1] = static_cast<float>(-2.0 * g * std::cos(omega));
    coeficientes.b[2] = coeficientes.b[0];
    coeficientes.a[0] = 1.0f;
    coeficientes.a[1] = coeficientes.b[1];
    coeficientes.a[2] = static_cast<float>(2.0 * g - 1.0);

    for (float& muestra : historial) muestra = 0.0f;
    siguiente = 0;
    z1 = z2 = 0.0f;
}

const CoeficientesFiltros& filtros_coeficientes()
{
    return coeficientes;
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
