#pragma once
#include <cstdint>

struct ContadoresRecepcion {
    uint64_t input = 0;
    uint64_t diag = 0;
    uint64_t err_trama = 0;
    uint64_t err_cobs = 0;
    uint64_t err_crc = 0;
    uint64_t err_cabecera = 0;
    uint64_t perdidos = 0;
    uint64_t sesiones = 0;
};

// La función se llama por cada INPUT válido, antes de reutilizar sus bytes.
void recepcion_iniciar(void (*procesar_input)(const uint8_t*, uint64_t first_sample));
// Drena RX por bloques sin esperar; devuelve si hubo bytes.
bool recepcion_leer();
// Atiende el watchdog y devuelve el estado del LED de error.
bool recepcion_actualizar(int64_t ahora_us);
const ContadoresRecepcion& recepcion_contadores();
