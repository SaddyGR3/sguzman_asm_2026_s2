#pragma once
#include <cstddef>
#include <cstdint>

// Origen: nodo1/src/protocolo.h. Se conservan las definiciones usadas por el receptor.
constexpr uint16_t PROTO_MAGIC = 0x5341;
constexpr uint8_t PROTO_VERSION = 1;
constexpr uint8_t TIPO_INPUT = 1;
constexpr uint8_t TIPO_FIR_OUT = 3;
constexpr uint8_t TIPO_DIAG = 4;
constexpr uint8_t NODO_1 = 1;
constexpr uint8_t NODO_2 = 2;
constexpr uint8_t NODO_3 = 3;
constexpr uint16_t FLAG_REINICIO = 0x0004;
constexpr uint8_t FORMATO_META = 0;
constexpr uint8_t FORMATO_FLOAT32 = 1;
constexpr size_t TAM_CABECERA = 32;
constexpr size_t TAM_CRC = 4;
constexpr size_t TAM_DIAG = 64;
constexpr size_t MUESTRAS_BLOQUE = 512;
constexpr size_t TAM_DATOS_INPUT = MUESTRAS_BLOQUE * 4;
constexpr size_t cota_cable(size_t r) { return r + r / 254 + 2; }
constexpr size_t R_INPUT = TAM_CABECERA + TAM_DATOS_INPUT + TAM_CRC;
constexpr size_t R_DIAG = TAM_CABECERA + TAM_DIAG + TAM_CRC;
constexpr size_t CABLE_INPUT = cota_cable(R_INPUT);
constexpr size_t CABLE_DIAG = cota_cable(R_DIAG);

// first_sample permite al nodo 3 alinear FIR_OUT con el INPUT que lo originó.
struct Cabecera {
    uint16_t magic;
    uint8_t version;
    uint8_t tipo;
    uint8_t src;
    uint8_t dst;
    uint32_t session_id;
    uint32_t sequence;
    uint64_t first_sample;
    uint16_t sample_count;
    uint8_t format;
    uint8_t channels;
    uint32_t payload_bytes;
};

uint16_t get_u16(const uint8_t* p);
uint32_t get_u32(const uint8_t* p);
uint64_t get_u64(const uint8_t* p);
float get_f32(const uint8_t* p);
void crc32_iniciar();
uint32_t crc32(const uint8_t* datos, size_t n);
// Devuelve 0 ante COBS inválido o falta de espacio; no incluye el delimitador.
size_t cobs_decodificar(const uint8_t* entrada, size_t n, uint8_t* salida, size_t capacidad);
// Requiere al menos TAM_CABECERA bytes, comprobados por el receptor.
Cabecera leer_cabecera(const uint8_t* datos);
// Serializa la salida seleccionada en un FIR_OUT completo (COBS y 0x00 incluidos).
size_t armar_fir_out(const float* muestras, uint16_t flags, uint32_t session_id,
                    uint32_t sequence, uint64_t first_sample,
                    uint8_t* trabajo, uint8_t* salida);
