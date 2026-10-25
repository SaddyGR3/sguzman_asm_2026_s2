#include "generador.h"
#include <cmath>

float Generador::tabla_[TAM_TABLA];
bool Generador::tabla_lista_ = false;

namespace {
constexpr float DOS_PI = 6.283185307f;
constexpr double CICLO = 4294967296.0;                 // 2^32
constexpr float FASE_A_RAD = DOS_PI / 4294967296.0f;   // fase de 32 bits a radianes
constexpr int DESPLAZAMIENTO = 32 - 10;                // 10 bits altos = índice de la tabla
}

Generador::Generador()
{
    // La tabla se calcula una sola vez, aunque existan varios generadores.
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
    // Se calcula en double para no perder precisión en el incremento.
    tonos_[indice].incremento =
        static_cast<uint32_t>(static_cast<double>(frecuencia_hz) / FS_HZ * CICLO);
}

void Generador::generar(float* bloque, size_t n, Metodo metodo)
{
    for (size_t k = 0; k < n; ++k) bloque[k] = 0.0f;

    for (auto& t : tonos_) {
        if (t.amplitud == 0.0f) continue;
        for (size_t k = 0; k < n; ++k) {
            const float s = (metodo == Metodo::TABLA)
                                ? tabla_[t.fase >> DESPLAZAMIENTO]
                                : sinf(static_cast<float>(t.fase) * FASE_A_RAD);
            bloque[k] += t.amplitud * s;
            t.fase += t.incremento;   // el desborde de uint32 da la vuelta al ciclo solo
        }
    }
}
