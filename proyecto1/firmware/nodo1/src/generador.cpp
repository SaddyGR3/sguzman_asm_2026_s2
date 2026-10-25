#include "generador.h"
#include <cmath>

float Generador::tabla_[TAM_TABLA];
bool Generador::tabla_lista_ = false;

namespace {
constexpr float DOS_PI = 6.283185307f;
constexpr double CICLO = 4294967296.0;                 // 2^32
constexpr int DESPLAZAMIENTO = 32 - 10;                // 10 bits altos = índice de la tabla
}

Generador::Generador()
{
    // La tabla (un ciclo de seno) se calcula una sola vez, aunque existan varios generadores.
    if (!tabla_lista_) {
        for (int i = 0; i < TAM_TABLA; ++i) {
            tabla_[i] = sinf(DOS_PI * i / TAM_TABLA);
        }
        tabla_lista_ = true;
    }
}

void Generador::configurar(int indice, float frecuencia_hz, float amplitud)
{
    if (indice < 0 || indice >= MAX_TONOS) return;
    tonos_[indice].amplitud = amplitud;
    // incremento = f / fs * 2^32; se calcula en double para no perder precisión.
    tonos_[indice].incremento =
        static_cast<uint32_t>(static_cast<double>(frecuencia_hz) / FS_HZ * CICLO);
}

void Generador::generar(float* bloque, size_t n)
{
    for (size_t k = 0; k < n; ++k) bloque[k] = 0.0f;

    for (auto& t : tonos_) {
        if (t.amplitud == 0.0f) continue;
        for (size_t k = 0; k < n; ++k) {
            // Los 10 bits altos de la fase indican la posición en la tabla (sin interpolar).
            bloque[k] += t.amplitud * tabla_[t.fase >> DESPLAZAMIENTO];
            t.fase += t.incremento;   // el desborde de uint32 da la vuelta al ciclo solo
        }
    }
}
