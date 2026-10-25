#pragma once
#include <cstddef>
#include <cstdint>

constexpr float FS_HZ = 8000.0f;    // frecuencia de muestreo
constexpr int HOP = 512;            // muestras por bloque
constexpr int MAX_TONOS = 4;        // tonos simultáneos
constexpr int TAM_TABLA = 1024;     // valores de la tabla de seno (2^10)

// Método con el que se calcula el seno.
enum class Metodo { TABLA, SINF };

struct Tono {
    float amplitud = 0.0f;
    uint32_t fase = 0;          // acumulador de fase: 2^32 equivale a un ciclo
    uint32_t incremento = 0;    // avance de fase por muestra
};

class Generador {
public:
    Generador();
    // Define frecuencia y amplitud de un tono. Amplitud 0 lo desactiva.
    void configurar(int indice, float frecuencia_hz, float amplitud);
    // Llena el bloque con la suma de los tonos y avanza sus fases.
    void generar(float* bloque, size_t n, Metodo metodo);
private:
    Tono tonos_[MAX_TONOS];
    static float tabla_[TAM_TABLA];
    static bool tabla_lista_;
};
