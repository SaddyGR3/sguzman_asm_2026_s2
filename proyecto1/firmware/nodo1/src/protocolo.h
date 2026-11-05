#pragma once
#include <cstddef>
#include <cstdint>

// ---- Constantes del protocolo ----
constexpr uint16_t PROTO_MAGIC = 0x5341;     // en el cable: 41 53
constexpr uint8_t  PROTO_VERSION = 1;

// Tipos de paquete.
constexpr uint8_t TIPO_INPUT = 1;       // x, 512 float32
constexpr uint8_t TIPO_INPUT_REF = 2;   // x y s intercalados
constexpr uint8_t TIPO_FIR_OUT = 3;     // solo la constante
constexpr uint8_t TIPO_DIAG = 4;
constexpr uint8_t TIPO_CONTROL = 5;     // solo la constante

// Banderas.
constexpr uint16_t FLAG_REFERENCIA = 0x0001;
constexpr uint16_t FLAG_CALENTAMIENTO = 0x0002;
constexpr uint16_t FLAG_REINICIO = 0x0004;
constexpr uint16_t FLAG_SATURACION = 0x0008;
constexpr uint16_t FLAG_DISCONTINUIDAD = 0x0010;
constexpr uint16_t FLAG_VENTANA_PARCIAL = 0x0020;

// Nodos.
constexpr uint8_t NODO_1 = 1;
constexpr uint8_t NODO_2 = 2;
constexpr uint8_t NODO_3 = 3;

// Formato y canales.
constexpr uint8_t FORMATO_META = 0;
constexpr uint8_t FORMATO_FLOAT32 = 1;

// Tamaños en bytes.
constexpr size_t TAM_CABECERA = 32;
constexpr size_t TAM_CRC = 4;
constexpr size_t TAM_DIAG = 64;
constexpr size_t TAM_CONTROL = 32;
constexpr size_t MUESTRAS_BLOQUE = 512;
constexpr size_t TAM_DATOS_INPUT = MUESTRAS_BLOQUE * 4;       // 2048
constexpr size_t TAM_DATOS_INPUT_REF = MUESTRAS_BLOQUE * 8;   // 4096

// Máximo en el cable: R + floor(R/254) + 2 (incluye el 0x00 delimitador).
constexpr size_t cota_cable(size_t r) { return r + r / 254 + 2; }
constexpr size_t R_INPUT = TAM_CABECERA + TAM_DATOS_INPUT + TAM_CRC;           // 2084
constexpr size_t R_INPUT_REF = TAM_CABECERA + TAM_DATOS_INPUT_REF + TAM_CRC;   // 4132
constexpr size_t R_DIAG = TAM_CABECERA + TAM_DIAG + TAM_CRC;                   // 100
constexpr size_t CABLE_INPUT = cota_cable(R_INPUT);          // 2094
constexpr size_t CABLE_INPUT_REF = cota_cable(R_INPUT_REF);  // 4150
constexpr size_t CABLE_DIAG = cota_cable(R_DIAG);            // 102
constexpr size_t TAM_TRABAJO = R_INPUT_REF;   // el paquete más grande, antes de COBS

// ---- Serialización little-endian, byte a byte ----
// Se escribe byte a byte para no depender de relleno ni de alineación.
void put_u16(uint8_t* p, uint16_t v);
void put_u32(uint8_t* p, uint32_t v);
void put_u64(uint8_t* p, uint64_t v);
void put_f32(uint8_t* p, float v);

// ---- CRC-32/ISO-HDLC ----
void crc32_iniciar();                          // genera la tabla; llamar antes de crc32()
uint32_t crc32(const uint8_t* datos, size_t n);

// ---- COBS ----
// Devuelve la longitud codificada, sin el 0x00 delimitador.
size_t cobs_codificar(const uint8_t* entrada, size_t n, uint8_t* salida);

// ---- Paquetes ----
// Arma [cabecera | datos | CRC] en 'trabajo' (TAM_TRABAJO B), aplica COBS hacia
// 'salida' y agrega el 0x00. Devuelve la longitud en el cable (0 si no caben los datos).
size_t armar_paquete(uint8_t tipo, uint8_t src, uint8_t dst, uint16_t flags,
                     uint32_t session_id, uint32_t sequence, uint64_t first_sample,
                     uint16_t sample_count, uint8_t format, uint8_t channels,
                     const uint8_t* datos, uint32_t n_datos,
                     uint8_t* trabajo, uint8_t* salida);

// Campos del DIAG, en el orden de sus offsets.
struct Diag {
    uint32_t fs = 0;
    uint16_t N = 0;
    uint16_t H = 0;
    uint8_t metodo = 0;          // método sugerido para el nodo 3 (0 = pasa todo)
    uint8_t calentamiento = 0;   // estado del estimador
    uint8_t tipo_ruido = 0;      // 0 = ninguno
    uint8_t filtro_n2 = 0;       // filtro sugerido para el nodo 2 (0 = pasa todo)
    float pico_Hz = 0.0f;
    float banda_lo = 0.0f;
    float banda_hi = 0.0f;
    float piso_resumen = 0.0f;
    float DC = 0.0f;
    float energia = 0.0f;
    uint32_t tiempo_us = 0;
    uint32_t overruns = 0;
    uint32_t perdidas = 0;
    uint32_t saturaciones = 0;
    uint64_t inicio_ventana = 0;
    uint32_t config_id = 0;
};

// Escribe los 64 B del DIAG en 'salida'.
void armar_diag(const Diag& d, uint8_t* salida);
