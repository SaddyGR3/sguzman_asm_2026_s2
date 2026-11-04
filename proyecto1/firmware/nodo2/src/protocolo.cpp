#include "protocolo.h"
#include <cstring>

static_assert(CABLE_INPUT == 2094 && CABLE_DIAG == 102,
              "tamaños en el cable distintos de la especificación");
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

static void put_u16(uint8_t* p, uint16_t v)
{
    p[0] = static_cast<uint8_t>(v);
    p[1] = static_cast<uint8_t>(v >> 8);
}

static void put_u32(uint8_t* p, uint32_t v)
{
    for (int i = 0; i < 4; ++i) p[i] = static_cast<uint8_t>(v >> (8 * i));
}

static void put_u64(uint8_t* p, uint64_t v)
{
    for (int i = 0; i < 8; ++i) p[i] = static_cast<uint8_t>(v >> (8 * i));
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

// Adaptado de nodo1/src/protocolo.cpp: COBS del paquete completo.
static size_t cobs_codificar(const uint8_t* entrada, size_t n, uint8_t* salida)
{
    size_t idx_codigo = 0;
    size_t j = 1;
    uint8_t codigo = 1;
    for (size_t k = 0; k < n; ++k) {
        const uint8_t b = entrada[k];
        if (b == 0) {
            salida[idx_codigo] = codigo;
            idx_codigo = j++;
            codigo = 1;
        } else {
            salida[j++] = b;
            if (++codigo == 0xFF) {
                salida[idx_codigo] = codigo;
                idx_codigo = j++;
                codigo = 1;
            }
        }
    }
    salida[idx_codigo] = codigo;
    return j;
}

size_t armar_fir_out(const float* muestras, uint16_t flags, uint32_t session_id,
                    uint32_t sequence, uint64_t first_sample,
                    uint8_t* trabajo, uint8_t* salida)
{
    put_u16(trabajo + 0, PROTO_MAGIC);
    trabajo[2] = PROTO_VERSION;
    trabajo[3] = TIPO_FIR_OUT;
    trabajo[4] = NODO_2;
    trabajo[5] = NODO_3;
    put_u16(trabajo + 6, flags);
    put_u32(trabajo + 8, session_id);
    put_u32(trabajo + 12, sequence);
    put_u64(trabajo + 16, first_sample);
    put_u16(trabajo + 24, MUESTRAS_BLOQUE);
    trabajo[26] = FORMATO_FLOAT32;
    trabajo[27] = 1;
    put_u32(trabajo + 28, TAM_DATOS_INPUT);
    // Igual que el nodo 1: ESP32 usa float32 IEEE 754 y little-endian.
    memcpy(trabajo + TAM_CABECERA, muestras, TAM_DATOS_INPUT);
    put_u32(trabajo + TAM_CABECERA + TAM_DATOS_INPUT,
            crc32(trabajo, TAM_CABECERA + TAM_DATOS_INPUT));
    const size_t largo = cobs_codificar(trabajo, R_INPUT, salida);
    salida[largo] = 0;
    return largo + 1;
}
