#include "protocolo.h"
#include <cstring>

static_assert(CABLE_INPUT == 2094 && CABLE_INPUT_REF == 4150 && CABLE_DIAG == 102,
              "tamaños en el cable distintos de la especificación");

static uint32_t tabla_crc[256];

void put_u16(uint8_t* p, uint16_t v)
{
    p[0] = static_cast<uint8_t>(v);
    p[1] = static_cast<uint8_t>(v >> 8);
}

void put_u32(uint8_t* p, uint32_t v)
{
    for (int i = 0; i < 4; ++i) p[i] = static_cast<uint8_t>(v >> (8 * i));
}

void put_u64(uint8_t* p, uint64_t v)
{
    for (int i = 0; i < 8; ++i) p[i] = static_cast<uint8_t>(v >> (8 * i));
}

void put_f32(uint8_t* p, float v)
{
    // Se reinterpretan los bits del float (IEEE 754) como entero y se escriben en little-endian.
    uint32_t bits;
    memcpy(&bits, &v, sizeof(bits));
    put_u32(p, bits);
}

// La tabla evita hacer 8 pasos por byte: cada byte se resuelve con una consulta.
void crc32_iniciar()
{
    for (uint32_t i = 0; i < 256; ++i) {
        uint32_t c = i;
        for (int b = 0; b < 8; ++b) c = (c & 1) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
        tabla_crc[i] = c;
    }
}

// CRC-32/ISO-HDLC: igual que zlib.crc32, para que la PC lo verifique.
uint32_t crc32(const uint8_t* datos, size_t n)
{
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t k = 0; k < n; ++k) {
        crc = tabla_crc[(crc ^ datos[k]) & 0xFF] ^ (crc >> 8);
    }
    return crc ^ 0xFFFFFFFFu;
}

// COBS: quita los ceros internos para que 0x00 solo marque el fin del paquete.
// Cada grupo empieza con un código = (bytes del grupo + 1), o 0xFF si el grupo se llena.
size_t cobs_codificar(const uint8_t* entrada, size_t n, uint8_t* salida)
{
    size_t idx_codigo = 0;
    size_t j = 1;
    uint8_t codigo = 1;
    for (size_t k = 0; k < n; ++k) {
        const uint8_t b = entrada[k];
        if (b == 0) {
            salida[idx_codigo] = codigo;
            idx_codigo = j;
            j += 1;
            codigo = 1;
        } else {
            salida[j] = b;
            j += 1;
            codigo += 1;
            if (codigo == 0xFF) {
                salida[idx_codigo] = codigo;
                idx_codigo = j;
                j += 1;
                codigo = 1;
            }
        }
    }
    salida[idx_codigo] = codigo;
    return j;
}

// Un paquete = cabecera + datos + CRC, luego COBS y el delimitador 0x00.
size_t armar_paquete(uint8_t tipo, uint8_t src, uint8_t dst, uint16_t flags,
                     uint32_t session_id, uint32_t sequence, uint64_t first_sample,
                     uint16_t sample_count, uint8_t format, uint8_t channels,
                     const uint8_t* datos, uint32_t n_datos,
                     uint8_t* trabajo, uint8_t* salida)
{
    if (n_datos > TAM_TRABAJO - TAM_CABECERA - TAM_CRC) return 0;

    // Cabecera de 32 B, campo por campo.
    put_u16(trabajo + 0, PROTO_MAGIC);
    trabajo[2] = PROTO_VERSION;
    trabajo[3] = tipo;
    trabajo[4] = src;
    trabajo[5] = dst;
    put_u16(trabajo + 6, flags);
    put_u32(trabajo + 8, session_id);
    put_u32(trabajo + 12, sequence);
    put_u64(trabajo + 16, first_sample);
    put_u16(trabajo + 24, sample_count);
    trabajo[26] = format;
    trabajo[27] = channels;
    put_u32(trabajo + 28, n_datos);

    if (n_datos > 0) memcpy(trabajo + TAM_CABECERA, datos, n_datos);

    // El CRC cubre cabecera + datos, antes de COBS.
    const size_t sin_crc = TAM_CABECERA + n_datos;
    put_u32(trabajo + sin_crc, crc32(trabajo, sin_crc));

    const size_t largo = cobs_codificar(trabajo, sin_crc + TAM_CRC, salida);
    salida[largo] = 0x00;
    return largo + 1;
}

// DIAG: 64 B con los offsets de la especificación.
void armar_diag(const Diag& d, uint8_t* salida)
{
    put_u32(salida + 0, d.fs);
    put_u16(salida + 4, d.N);
    put_u16(salida + 6, d.H);
    salida[8] = d.metodo;
    salida[9] = d.calentamiento;
    salida[10] = d.tipo_ruido;
    salida[11] = d.filtro_n2;
    put_f32(salida + 12, d.pico_Hz);
    put_f32(salida + 16, d.banda_lo);
    put_f32(salida + 20, d.banda_hi);
    put_f32(salida + 24, d.piso_resumen);
    put_f32(salida + 28, d.DC);
    put_f32(salida + 32, d.energia);
    put_u32(salida + 36, d.tiempo_us);
    put_u32(salida + 40, d.overruns);
    put_u32(salida + 44, d.perdidas);
    put_u32(salida + 48, d.saturaciones);
    put_u64(salida + 52, d.inicio_ventana);   // offset 52: no alineado a 8, por eso byte a byte
    put_u32(salida + 60, d.config_id);
}
