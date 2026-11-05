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
#include "espectral.h"
#include "protocolo.h"
#include "recepcion.h"
#include "salida_dac.h"
#include "grabacion.h"

enum class ModoFiltro { SIN_FILTRO, FIR, NOTCH, ESPECTRAL };
constexpr ModoFiltro MODO_INICIAL = ModoFiltro::SIN_FILTRO;
constexpr gpio_num_t PIN_BOTON = GPIO_NUM_32;
constexpr gpio_num_t PIN_REPRODUCIR = GPIO_NUM_33;
static_assert(ESPECTRAL_H == MUESTRAS_BLOQUE, "El avance espectral debe coincidir con el bloque reproducido");

struct TiempoProceso {
    uint64_t suma_us = 0;
    uint64_t max_us = 0;
};

static ModoFiltro modo = MODO_INICIAL;
static int boton_anterior = 1;
static int reproducir_anterior = 1;
static float salida[MUESTRAS_BLOQUE];
static float salida_espectral[MUESTRAS_BLOQUE];
static bool cola_espectral_pendiente = false;
static char linea_comando[96];
static size_t longitud_comando = 0;
static bool descartando_comando = false;
static TiempoProceso proc_total, proc_temporal, proc_espectral;
static uint32_t bloques_proc = 0;

static void registrar_tiempo(TiempoProceso& tiempo, int64_t inicio_us)
{
    const uint64_t duracion_us = static_cast<uint64_t>(esp_timer_get_time() - inicio_us);
    tiempo.suma_us += duracion_us;
    if (duracion_us > tiempo.max_us) tiempo.max_us = duracion_us;
}

static void reiniciar_tiempos()
{
    proc_total = proc_temporal = proc_espectral = {};
    bloques_proc = 0;
}

static const char* nombre_modo()
{
    static const char* const nombres[] = {"SIN FILTRO", "FIR", "NOTCH", "ESPECTRAL"};
    return nombres[static_cast<int>(modo)];
}

static void reproducir()
{
    if (grabacion_reproducir(nombre_modo())) {
        filtros_reiniciar_estados();
        espectral_reiniciar();
        cola_espectral_pendiente = false;
        reiniciar_tiempos();
    } else printf("Grabación: reproducir requiere estado LISTA\n");
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
    const auto& espectral = espectral_configuracion();
    printf("Espectral: resta | alfa %.6g | ganancia minima %.6g | N %d H %d | retardo 64 ms\n",
           espectral.alfa, espectral.ganancia_minima, ESPECTRAL_N, ESPECTRAL_H);
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

    if (comando && std::strcmp(comando, "calibrar") == 0 && !primero) {
        grabacion_calibrar();
        return;
    }
    if (comando && std::strcmp(comando, "reproducir") == 0 && !primero) {
        reproducir();
        return;
    }
    if (comando && std::strcmp(comando, "grabacion") == 0 && !primero) {
        grabacion_imprimir();
        return;
    }
    double factor;
    if (comando && std::strcmp(comando, "umbral") == 0 && primero && !segundo &&
        leer_numero(primero, factor) && factor >= 1.5 && factor <= 20.0) {
        grabacion_cambiar_umbral(static_cast<float>(factor));
        grabacion_imprimir();
        return;
    }
    if (comando && std::strcmp(comando, "estado") == 0 && !primero) {
        imprimir_estado();
        return;
    }
    if (comando && std::strcmp(comando, "modo") == 0 && primero && !segundo) {
        if (std::strcmp(primero, "sin") == 0) seleccionar_modo(ModoFiltro::SIN_FILTRO);
        else if (std::strcmp(primero, "fir") == 0) seleccionar_modo(ModoFiltro::FIR);
        else if (std::strcmp(primero, "notch") == 0) seleccionar_modo(ModoFiltro::NOTCH);
        else if (std::strcmp(primero, "espectral") == 0) seleccionar_modo(ModoFiltro::ESPECTRAL);
        else printf("Error: comando o valores invalidos\n");
        return;
    }
    double uno, dos;
    if (comando && primero && segundo && !extra &&
        leer_numero(primero, uno) && leer_numero(segundo, dos)) {
        if (std::strcmp(comando, "espectral") == 0 && espectral_configurar(uno, dos)) {
            const auto& cfg = espectral_configuracion();
            printf("Espectral: alfa %.6g | ganancia minima %.6g\n", cfg.alfa, cfg.ganancia_minima);
            return;
        }
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

static void procesar_input(const uint8_t* datos, uint64_t)
{
    // Una lectura del botón por INPUT, incluso si RX trae varios paquetes juntos.
    const int boton_actual = gpio_get_level(PIN_BOTON);
    if (boton_anterior == 1 && boton_actual == 0) {
        switch (modo) {
            case ModoFiltro::SIN_FILTRO: seleccionar_modo(ModoFiltro::FIR); break;
            case ModoFiltro::FIR: seleccionar_modo(ModoFiltro::NOTCH); break;
            case ModoFiltro::NOTCH: seleccionar_modo(ModoFiltro::ESPECTRAL); break;
            case ModoFiltro::ESPECTRAL: seleccionar_modo(ModoFiltro::SIN_FILTRO); break;
        }
    }
    boton_anterior = boton_actual;

    grabacion_input(datos);
}

static void atender_reproduccion()
{
    if (salida_dac_terminada()) grabacion_finalizar_reproduccion();
    if (grabacion_estado() != EstadoGrabacion::REPRODUCIENDO || !salida_dac_disponible()) return;
    const int64_t inicio_proc_us = esp_timer_get_time();
    bool ultimo = false;
    if (cola_espectral_pendiente) {
        // Un bloque de ceros completa el solape de las últimas 512 muestras.
        // Se vacían ambas rutas, incluso si se escucha otra salida.
        std::memset(salida, 0, sizeof(salida));
        cola_espectral_pendiente = false;
        ultimo = true;
    } else {
        if (!grabacion_leer_bloque(salida, ultimo)) return;
        cola_espectral_pendiente = ultimo;
        ultimo = false;  // El DAC termina después del bloque de vaciado.
    }
    // La ruta espectral recibe la misma entrada decodificada que FIR y notch.
    // Se calcula antes de que la selección temporal sobrescriba 'salida'.
    const int64_t inicio_espectral_us = esp_timer_get_time();
    espectral_procesar(salida, salida_espectral);
    registrar_tiempo(proc_espectral, inicio_espectral_us);
    const int64_t inicio_temporal_us = esp_timer_get_time();
    for (size_t k = 0; k < MUESTRAS_BLOQUE; ++k) {
        const float x = salida[k];
        float fir, notch;
        filtros_procesar(x, fir, notch);
        switch (modo) {
            case ModoFiltro::SIN_FILTRO:
            case ModoFiltro::ESPECTRAL: salida[k] = x; break;
            case ModoFiltro::FIR: salida[k] = fir; break;
            case ModoFiltro::NOTCH: salida[k] = notch; break;
        }
    }
    registrar_tiempo(proc_temporal, inicio_temporal_us);
    salida_dac_input(modo == ModoFiltro::ESPECTRAL ? salida_espectral : salida, ultimo);
    registrar_tiempo(proc_total, inicio_proc_us);
    ++bloques_proc;
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
    boton.pin_bit_mask = (1ULL << PIN_BOTON) | (1ULL << PIN_REPRODUCIR);
    boton.mode = GPIO_MODE_INPUT;
    boton.pull_up_en = GPIO_PULLUP_ENABLE;
    boton.pull_down_en = GPIO_PULLDOWN_DISABLE;
    boton.intr_type = GPIO_INTR_DISABLE;
    ESP_ERROR_CHECK(gpio_config(&boton));
    boton_anterior = gpio_get_level(PIN_BOTON);
    reproducir_anterior = gpio_get_level(PIN_REPRODUCIR);

    filtros_iniciar();
    // Inicializar ESP-DSP antes de reservar la grabación: también usa RAM interna.
    ESP_ERROR_CHECK(espectral_iniciar());
    salida_dac_iniciar();
    recepcion_iniciar(procesar_input, grabacion_nueva_sesion);
    grabacion_iniciar();
    const int banderas_consola = fcntl(STDIN_FILENO, F_GETFL, 0);
    ESP_ERROR_CHECK(banderas_consola >= 0 &&
                    fcntl(STDIN_FILENO, F_SETFL, banderas_consola | O_NONBLOCK) == 0
                    ? ESP_OK : ESP_FAIL);
    const auto& c = filtros_coeficientes();
    const auto& cfg_espectral = espectral_configuracion();
    printf("Nodos 2+3: UART1 RX GPIO19 TX GPIO18 sin uso, 921600 8N1, RX 16384 B | "
           "DAC GPIO25 8000 Hz APLL DMA 6x512 B, tarea dedicada | LED GPIO4 | "
           "watchdog INPUT 200 ms | monitor UART0 115200 | Filtro: %s | botones GPIO32 filtro, GPIO33 reproducir | "
           "espectral resta N 1024 H 512, alfa %.6g, ganancia minima %.6g, retardo 64 ms | FIR primeros 3 [%.12f, %.12f, %.12f] | "
           "notch b [%.12f, %.12f, %.12f] a [%.12f, %.12f, %.12f]\n",
           nombre_modo(), cfg_espectral.alfa, cfg_espectral.ganancia_minima,
           c.fir[0], c.fir[1], c.fir[2],
           c.b[0], c.b[1], c.b[2], c.a[0], c.a[1], c.a[2]);

    uint32_t numero_resumen = 0;
    int64_t ultimo_resumen_us = esp_timer_get_time();
    int64_t ultimo_error_dac_us = -1;
    uint32_t desbordes_anteriores = 0;
    for (;;) {
        const bool hubo_bytes = recepcion_leer();
        // Los comandos se aplican después de terminar todos los INPUT de la lectura.
        leer_consola();
        const int reproducir_actual = gpio_get_level(PIN_REPRODUCIR);
        if (reproducir_anterior == 1 && reproducir_actual == 0 &&
            grabacion_estado() == EstadoGrabacion::LISTA) reproducir();
        reproducir_anterior = reproducir_actual;
        atender_reproduccion();
        const int64_t ahora_us = esp_timer_get_time();
        const bool error_rx = recepcion_actualizar(ahora_us);
        const auto d = salida_dac_contadores();
        if (d.desbordes != desbordes_anteriores) {
            ultimo_error_dac_us = ahora_us;
            desbordes_anteriores = d.desbordes;
        }
        const bool error_dac = ultimo_error_dac_us >= 0 && ahora_us - ultimo_error_dac_us < 500000;
        ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_4, error_rx || error_dac ? 1 : 0));

        if (longitud_comando > 0 || descartando_comando) {
            // Mientras se escribe, no intercalar resúmenes con el eco del comando.
            ultimo_resumen_us = ahora_us;
            reiniciar_tiempos();
        } else if (ahora_us - ultimo_resumen_us >= 1000000) {
            const auto& r = recepcion_contadores();
            const uint32_t divisor = bloques_proc ? bloques_proc : 1;
            printf("#%04lu | Filtro: %s | INPUT %llu | DIAG %llu | err_trama %llu | err_cobs %llu | "
                   "err_crc %llu | err_cabecera %llu | perdidos %llu | sesiones %llu | "
                   "DAC %llu B | desbordes_dac %lu | proc total prom %llu us max %llu us | "
                   "proc temporal prom %llu us max %llu us | proc espectral prom %llu us max %llu us | "
                   "grabación %s | RMS %.6g | fondo %.6g\n",
                   (unsigned long)++numero_resumen, nombre_modo(),
                   (unsigned long long)r.input, (unsigned long long)r.diag,
                   (unsigned long long)r.err_trama, (unsigned long long)r.err_cobs,
                   (unsigned long long)r.err_crc, (unsigned long long)r.err_cabecera,
                   (unsigned long long)r.perdidos, (unsigned long long)r.sesiones,
                   (unsigned long long)d.bytes, (unsigned long)d.desbordes,
                   (unsigned long long)(proc_total.suma_us / divisor), (unsigned long long)proc_total.max_us,
                   (unsigned long long)(proc_temporal.suma_us / divisor), (unsigned long long)proc_temporal.max_us,
                   (unsigned long long)(proc_espectral.suma_us / divisor), (unsigned long long)proc_espectral.max_us,
                   grabacion_nombre_estado(), grabacion_rms(), grabacion_fondo());
            reiniciar_tiempos();
            ultimo_resumen_us = ahora_us;
        }
        // Un tick son 10 ms con la configuración actual; RX se drena antes de dormir.
        if (!hubo_bytes) vTaskDelay(1);
    }
}
