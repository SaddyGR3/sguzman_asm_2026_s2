#include "protocolo.h"
#include <cstring>

static_assert(CABLE_INPUT == 2094 && CABLE_DIAG == 102,
              "tamaños en el cable distintos de la especificación");
static_assert(CABLE_CONTROL == 70, "tamaño CONTROL en el cable distinto de la especificación");
static_assert(sizeof(float) == 4, "el protocolo requiere float32");

static uint32_t tabla_crc[256];

// Lectura little-endian sin depender de alineación ni relleno de estructuras.
uint16_t get_u16(const uint8_t* p)
{
    return static_cast<uint16_t>(p[0] | (static_cast<uint16_t>(p[1]) << 8));
}

uint32_t get_u32(const uint8_t* p)
{
    uint32_t v = 0;
    for (int i = 0; i < 4; ++i) v |= static_cast<uint32_t>(p[i]) << (8 * i);
    return v;
}

uint64_t get_u64(const uint8_t* p)
{
    uint64_t v = 0;
    for (int i = 0; i < 8; ++i) v |= static_cast<uint64_t>(p[i]) << (8 * i);
    return v;
}

float get_f32(const uint8_t* p)
{
    const uint32_t bits = get_u32(p);
    float v;
    memcpy(&v, &bits, sizeof(v));
    return v;
}

// Origen: nodo1/src/protocolo.cpp; tabla y CRC-32/ISO-HDLC sin cambios.
void crc32_iniciar()
{
    for (uint32_t i = 0; i < 256; ++i) {
        uint32_t c = i;
        for (int b = 0; b < 8; ++b) c = (c & 1) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
        tabla_crc[i] = c;
    }
}

uint32_t crc32(const uint8_t* datos, size_t n)
{
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t k = 0; k < n; ++k) {
        crc = tabla_crc[(crc ^ datos[k]) & 0xFF] ^ (crc >> 8);
    }
    return crc ^ 0xFFFFFFFFu;
}

size_t cobs_decodificar(const uint8_t* entrada, size_t n, uint8_t* salida, size_t capacidad)
{
    size_t i = 0, j = 0;
    while (i < n) {
        const uint8_t codigo = entrada[i++];
        if (codigo == 0) return 0;
        const size_t cantidad = codigo - 1;
        if (cantidad > n - i || cantidad > capacidad - j) return 0;
        for (size_t k = 0; k < cantidad; ++k) {
            if (entrada[i] == 0) return 0;
            salida[j++] = entrada[i++];
        }
        if (codigo != 0xFF && i < n) {
            if (j == capacidad) return 0;
            salida[j++] = 0;
        }
    }
    return j;
}

Cabecera leer_cabecera(const uint8_t* datos)
{
    return {get_u16(datos), datos[2], datos[3], datos[4], datos[5],
            get_u32(datos + 8), get_u32(datos + 12), get_u64(datos + 16), get_u16(datos + 24),
            datos[26], datos[27], get_u32(datos + 28)};
}
