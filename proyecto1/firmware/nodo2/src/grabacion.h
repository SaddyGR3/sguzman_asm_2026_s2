#pragma once
#include <cstdint>

enum class EstadoGrabacion { ESPERANDO, GRABANDO, LISTA, REPRODUCIENDO };

struct DiagnosticoGrabacion {
	uint8_t tipo_ruido = 0;
	uint8_t filtro_n2 = 0;
	float pico_hz = -1.0f;
};

void grabacion_iniciar();
void grabacion_calibrar();
void grabacion_nueva_sesion();
void grabacion_input(const uint8_t* datos);
void grabacion_diag(const uint8_t* datos);
bool grabacion_reproducir(const char* modo);
bool grabacion_leer_bloque(float* muestras, bool& ultimo);
void grabacion_finalizar_reproduccion();
void grabacion_cambiar_umbral(float factor);
void grabacion_imprimir();
const DiagnosticoGrabacion& grabacion_diagnostico();
EstadoGrabacion grabacion_estado();
const char* grabacion_nombre_estado();
float grabacion_rms();
float grabacion_fondo();
double grabacion_duracion_s();
double grabacion_posicion_s();
