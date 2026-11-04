#include <cstdio>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_err.h"
#include "esp_timer.h"
#include "filtros.h"
#include "protocolo.h"
#include "recepcion.h"
#include "salida_dac.h"
#include "transmision.h"

enum class ModoFiltro { SIN_FILTRO, FIR, NOTCH };
constexpr ModoFiltro MODO_INICIAL = ModoFiltro::SIN_FILTRO;
constexpr gpio_num_t PIN_BOTON = GPIO_NUM_32;

static ModoFiltro modo = MODO_INICIAL;
static int boton_anterior = 1;
static float salida[MUESTRAS_BLOQUE];
static char linea_comando[96];
static size_t longitud_comando = 0;
static bool descartando_comando = false;
static uint64_t suma_proc_us = 0;
static uint64_t max_proc_us = 0;
static uint32_t bloques_proc = 0;

static const char* nombre_modo()
{
    static const char* const nombres[] = {"SIN FILTRO", "FIR", "NOTCH"};
    return nombres[static_cast<int>(modo)];
}

static void seleccionar_modo(ModoFiltro nuevo)
{
    modo = nuevo;
    printf("Filtro: %s\n", nombre_modo());
}

static void imprimir_fir()
{
    const auto& c = filtros_coeficientes();
    printf("FIR coeficientes [");
    for (int n = 0; n < COEFICIENTES_FIR; ++n) {
        printf(n == 0 ? "%.9g" : ", %.9g", c.fir[n]);
    }
    printf("]\n");
}

static void imprimir_notch()
{
    const auto& c = filtros_coeficientes();
    printf("Notch b [%.9g, %.9g, %.9g] a [%.9g, %.9g, %.9g]\n",
           c.b[0], c.b[1], c.b[2], c.a[0], c.a[1], c.a[2]);
}

static void imprimir_estado()
{
    const auto& cfg = filtros_configuracion();
    printf("Estado: %s | banda %.6g-%.6g Hz | notch %.6g Hz Q %.6g\n",
           nombre_modo(), cfg.banda_inferior_hz, cfg.banda_superior_hz,
           cfg.notch_hz, cfg.q_notch);
    imprimir_fir();
    imprimir_notch();
}

static bool leer_numero(const char* texto, double& valor)
{
    if (texto == nullptr) return false;
    char* fin = nullptr;
    valor = std::strtod(texto, &fin);
    return fin != texto && *fin == '\0' && std::isfinite(valor);
}

static void ejecutar_comando(char* linea)
{
    char* resto = nullptr;
    const char* comando = strtok_r(linea, " \t", &resto);
    const char* primero = strtok_r(nullptr, " \t", &resto);
    const char* segundo = strtok_r(nullptr, " \t", &resto);
    const char* extra = strtok_r(nullptr, " \t", &resto);

    if (comando && std::strcmp(comando, "estado") == 0 && !primero) {
        imprimir_estado();
        return;
    }
    if (comando && std::strcmp(comando, "modo") == 0 && primero && !segundo) {
        if (std::strcmp(primero, "sin") == 0) seleccionar_modo(ModoFiltro::SIN_FILTRO);
        else if (std::strcmp(primero, "fir") == 0) seleccionar_modo(ModoFiltro::FIR);
        else if (std::strcmp(primero, "notch") == 0) seleccionar_modo(ModoFiltro::NOTCH);
        else printf("Error: comando o valores invalidos\n");
        return;
    }
    double uno, dos;
    if (comando && primero && segundo && !extra &&
        leer_numero(primero, uno) && leer_numero(segundo, dos)) {
        if (std::strcmp(comando, "banda") == 0 &&
            uno >= 100.0 && dos <= 3000.0 && uno < dos) {
            filtros_cambiar_banda(uno, dos);
            printf("Banda: %.6g-%.6g Hz\n", uno, dos);
            imprimir_fir();
            return;
        }
        if (std::strcmp(comando, "notch") == 0 &&
            uno >= 100.0 && uno <= 3000.0 && dos >= 0.5 && dos <= 20.0) {
            filtros_cambiar_notch(uno, dos);
            printf("Notch: %.6g Hz Q %.6g\n", uno, dos);
            imprimir_notch();
            return;
        }
    }
    printf("Error: comando o valores invalidos\n");
}

static void leer_consola()
{
    // UART0 del USB ya está registrado como stdin; read no espera con O_NONBLOCK.
    char recibidos[64];
    const ssize_t n = read(STDIN_FILENO, recibidos, sizeof(recibidos));
    for (ssize_t i = 0; i < n; ++i) {
        const char c = recibidos[i];
        if (c == '\r' || c == '\n') {
            if (descartando_comando || longitud_comando > 0) putchar('\n');
            if (descartando_comando) printf("Error: linea demasiado larga\n");
            else if (longitud_comando > 0) {
                linea_comando[longitud_comando] = '\0';
                ejecutar_comando(linea_comando);
            }
            longitud_comando = 0;
            descartando_comando = false;
        } else if (c == '\b' || c == '\x7f') {
            if (longitud_comando > 0) {
                --longitud_comando;
                printf("\b \b");
                fflush(stdout);
            }
        } else if (!descartando_comando && (c == '\t' || (c >= ' ' && c <= '~'))) {
            if (longitud_comando + 1 < sizeof(linea_comando)) {
                linea_comando[longitud_comando++] = c;
                putchar(c);
                fflush(stdout);
            } else {
                descartando_comando = true;
            }
        }
    }
}

static void procesar_input(const uint8_t* datos, uint64_t first_sample)
{
    // Una lectura del botón por INPUT, incluso si RX trae varios paquetes juntos.
    const int boton_actual = gpio_get_level(PIN_BOTON);
    if (boton_anterior == 1 && boton_actual == 0) {
        switch (modo) {
            case ModoFiltro::SIN_FILTRO: seleccionar_modo(ModoFiltro::FIR); break;
            case ModoFiltro::FIR: seleccionar_modo(ModoFiltro::NOTCH); break;
            case ModoFiltro::NOTCH: seleccionar_modo(ModoFiltro::SIN_FILTRO); break;
        }
    }
    boton_anterior = boton_actual;

    const int64_t inicio_proc_us = esp_timer_get_time();
    for (size_t k = 0; k < MUESTRAS_BLOQUE; ++k) {
        const float x = get_f32(datos + 4 * k);
        float fir, notch;
        filtros_procesar(x, fir, notch);
        switch (modo) {
            case ModoFiltro::SIN_FILTRO: salida[k] = x; break;
            case ModoFiltro::FIR: salida[k] = fir; break;
            case ModoFiltro::NOTCH: salida[k] = notch; break;
        }
    }
    salida_dac_input(salida);
    const uint64_t duracion_us = static_cast<uint64_t>(esp_timer_get_time() - inicio_proc_us);
    suma_proc_us += duracion_us;
    if (duracion_us > max_proc_us) max_proc_us = duracion_us;
    ++bloques_proc;
    transmision_enviar(salida, first_sample);
}

extern "C" void app_main(void)
{
    gpio_config_t led = {};
    led.pin_bit_mask = 1ULL << GPIO_NUM_4;
    led.mode = GPIO_MODE_OUTPUT;
    led.intr_type = GPIO_INTR_DISABLE;
    ESP_ERROR_CHECK(gpio_config(&led));
    ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_4, 1));

    gpio_config_t boton = {};
    boton.pin_bit_mask = 1ULL << PIN_BOTON;
    boton.mode = GPIO_MODE_INPUT;
    boton.pull_up_en = GPIO_PULLUP_ENABLE;
    boton.pull_down_en = GPIO_PULLDOWN_DISABLE;
    boton.intr_type = GPIO_INTR_DISABLE;
    ESP_ERROR_CHECK(gpio_config(&boton));
    boton_anterior = gpio_get_level(PIN_BOTON);

    filtros_iniciar();
    salida_dac_iniciar();
    recepcion_iniciar(procesar_input);
    transmision_iniciar();
    const int banderas_consola = fcntl(STDIN_FILENO, F_GETFL, 0);
    ESP_ERROR_CHECK(banderas_consola >= 0 &&
                    fcntl(STDIN_FILENO, F_SETFL, banderas_consola | O_NONBLOCK) == 0
                    ? ESP_OK : ESP_FAIL);
    const auto& c = filtros_coeficientes();
    printf("Nodo 2: UART1 RX GPIO19 TX GPIO18 sin uso, 921600 8N1, RX 16384 B | "
           "DAC GPIO25 8000 Hz APLL DMA 6x512 B, timeout 0 ms | UART2 TX GPIO17 921600 | LED GPIO4 | "
           "watchdog INPUT 200 ms | monitor UART0 115200 | Filtro: %s | botón GPIO32 | "
           "FIR primeros 3 [%.12f, %.12f, %.12f] | "
           "notch b [%.12f, %.12f, %.12f] a [%.12f, %.12f, %.12f]\n",
           nombre_modo(), c.fir[0], c.fir[1], c.fir[2],
           c.b[0], c.b[1], c.b[2], c.a[0], c.a[1], c.a[2]);

    int64_t ultimo_resumen_us = esp_timer_get_time();
    int64_t ultimo_error_dac_us = -1;
    uint32_t desbordes_anteriores = 0;
    for (;;) {
        const bool hubo_bytes = recepcion_leer();
        // Los comandos se aplican después de terminar todos los INPUT de la lectura.
        leer_consola();
        const int64_t ahora_us = esp_timer_get_time();
        const bool error_rx = recepcion_actualizar(ahora_us);
        const auto& d = salida_dac_contadores();
        if (d.desbordes != desbordes_anteriores) {
            ultimo_error_dac_us = ahora_us;
            desbordes_anteriores = d.desbordes;
        }
        const bool error_dac = ultimo_error_dac_us >= 0 && ahora_us - ultimo_error_dac_us < 500000;
        ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_4, error_rx || error_dac ? 1 : 0));

        if (longitud_comando > 0 || descartando_comando) {
            // Mientras se escribe, no intercalar resúmenes con el eco del comando.
            ultimo_resumen_us = ahora_us;
            suma_proc_us = 0;
            max_proc_us = 0;
            bloques_proc = 0;
        } else if (ahora_us - ultimo_resumen_us >= 1000000) {
            const auto& r = recepcion_contadores();
            const uint64_t prom_proc_us = bloques_proc ? suma_proc_us / bloques_proc : 0;
            printf("Filtro: %s | INPUT %llu | DIAG %llu | err_trama %llu | err_cobs %llu | "
                   "err_crc %llu | err_cabecera %llu | perdidos %llu | sesiones %llu | "
                   "DAC %llu B | desbordes_dac %lu | proc prom %llu us max %llu us | "
                   "FIR_OUT %llu | descartes_tx %llu\n",
                   nombre_modo(),
                   (unsigned long long)r.input, (unsigned long long)r.diag,
                   (unsigned long long)r.err_trama, (unsigned long long)r.err_cobs,
                   (unsigned long long)r.err_crc, (unsigned long long)r.err_cabecera,
                   (unsigned long long)r.perdidos, (unsigned long long)r.sesiones,
                   (unsigned long long)d.bytes, (unsigned long)d.desbordes,
                   (unsigned long long)prom_proc_us, (unsigned long long)max_proc_us,
                   (unsigned long long)transmision_enviados(),
                   (unsigned long long)transmision_descartados());
            suma_proc_us = 0;
            max_proc_us = 0;
            bloques_proc = 0;
            ultimo_resumen_us = ahora_us;
        }
        // Un tick son 10 ms con la configuración actual; RX se drena antes de dormir.
        if (!hubo_bytes) vTaskDelay(1);
    }
}
