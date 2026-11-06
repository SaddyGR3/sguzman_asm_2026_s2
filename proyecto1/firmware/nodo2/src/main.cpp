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
#include "metricas.h"

enum class ModoFiltro { SIN_FILTRO, FIR, NOTCH, ESPECTRAL };
constexpr ModoFiltro MODO_INICIAL = ModoFiltro::SIN_FILTRO;
constexpr gpio_num_t PIN_BOTON = GPIO_NUM_32;
constexpr gpio_num_t PIN_REPRODUCIR = GPIO_NUM_33;
constexpr int64_t BOTON_ESTABLE_US = 30000;
constexpr int64_t BOTON_BLOQUEO_US = 200000;
static_assert(ESPECTRAL_H == MUESTRAS_BLOQUE, "El avance espectral debe coincidir con el bloque reproducido");
static_assert(COEFICIENTES_FIR % 2 == 1 && (COEFICIENTES_FIR - 1) / 2 < MUESTRAS_BLOQUE,
              "El alineamiento FIR requiere retardo entero menor que un bloque");

struct TiempoProceso {
    uint64_t suma_us = 0;
    uint64_t max_us = 0;
};

// Solo la tarea principal lee/cambia el modo y procesa los filtros.
// La tarea DAC recibe códigos ya convertidos y no accede a esta variable.
static ModoFiltro modo = MODO_INICIAL;
// Cambiar la escucha a ESPECTRAL conserva la última selección temporal.
static ModoFiltro modo_temporal = MODO_INICIAL;
static bool automatico = false;
static float banda_nodo1_lo = 100.0f, banda_nodo1_hi = 1200.0f;
static uint32_t config_nodo1 = 0;
static bool banda_pendiente = false;
static float banda_pendiente_lo = 0.0f, banda_pendiente_hi = 0.0f;
static uint32_t config_pendiente = 0;
static bool banda_es_nodo1 = false;
static int boton_leido = 1, boton_estable = 1;
static int64_t boton_cambio_us = 0, boton_bloqueado_hasta_us = 0;
static int reproducir_anterior = 1;
static float salida[MUESTRAS_BLOQUE];
static float entrada_reproduccion[MUESTRAS_BLOQUE];
static float salida_espectral[MUESTRAS_BLOQUE];
static float salida_fir[MUESTRAS_BLOQUE], salida_notch[MUESTRAS_BLOQUE];
static bool cola_espectral_pendiente = false;
static char linea_comando[96];
static size_t longitud_comando = 0;
static bool descartando_comando = false;
static bool vista_breve = true;
static TiempoProceso proc_total, proc_temporal, proc_espectral;
static uint32_t bloques_proc = 0;

static void registrar_duracion(TiempoProceso& tiempo, uint64_t duracion_us)
{
    tiempo.suma_us += duracion_us;
    if (duracion_us > tiempo.max_us) tiempo.max_us = duracion_us;
}

static void reiniciar_tiempos()
{
    proc_total = proc_temporal = proc_espectral = {};
    bloques_proc = 0;
}

static const char* nombre_modo(ModoFiltro seleccionado)
{
    static const char* const nombres[] = {"SIN FILTRO", "FIR", "NOTCH", "ESPECTRAL"};
    return nombres[static_cast<int>(seleccionado)];
}

static const char* nombre_modo() { return nombre_modo(modo); }

static void aplicar_banda_nodo1(float inferior, float superior, uint32_t config_id)
{
    filtros_cambiar_banda(inferior, superior);
    banda_nodo1_lo = inferior;
    banda_nodo1_hi = superior;
    config_nodo1 = config_id;
    banda_es_nodo1 = true;
    printf("Banda del nodo 1: %.6g-%.6g Hz (config %lu)\n",
           inferior, superior, (unsigned long)config_id);
}

static void procesar_control(const uint8_t* datos)
{
    const uint32_t config_id = get_u32(datos + 12);
    const float inferior = get_f32(datos + 24);
    const float superior = get_f32(datos + 28);
    if (config_id == config_nodo1 || config_id == config_pendiente) return;
    if (grabacion_estado() == EstadoGrabacion::REPRODUCIENDO) {
        banda_pendiente = true;
        banda_pendiente_lo = inferior;
        banda_pendiente_hi = superior;
        config_pendiente = config_id;
        return;
    }
    aplicar_banda_nodo1(inferior, superior, config_id);
}

static void aplicar_banda_pendiente()
{
    if (!banda_pendiente || grabacion_estado() == EstadoGrabacion::REPRODUCIENDO) return;
    aplicar_banda_nodo1(banda_pendiente_lo, banda_pendiente_hi, config_pendiente);
    banda_pendiente = false;
}

static void reproducir()
{
    if (grabacion_estado() != EstadoGrabacion::LISTA) {
        printf("Grabación: reproducir requiere estado LISTA\n");
        return;
    }
    if (automatico) {
        const DiagnosticoGrabacion& diagnostico = grabacion_diagnostico();
        const ModoFiltro modo_anterior = modo;
        ModoFiltro modo_auto = ModoFiltro::SIN_FILTRO;
        bool diagnostico_valido = true;
        if (diagnostico.filtro_n2 == 1) {
            modo_auto = ModoFiltro::FIR;
        } else if (diagnostico.filtro_n2 == 2 || diagnostico.filtro_n2 == 3) {
            if (std::isfinite(diagnostico.pico_hz) && diagnostico.pico_hz >= 100.0f &&
                diagnostico.pico_hz <= 3000.0f) {
                filtros_cambiar_notch(diagnostico.pico_hz, 8.5);
                modo_auto = ModoFiltro::NOTCH;
            } else {
                diagnostico_valido = false;
            }
        }
        if (!diagnostico_valido || diagnostico.filtro_n2 == 0) {
            modo_auto = ModoFiltro::SIN_FILTRO;
        }
        modo_temporal = modo_auto;
        if (modo_anterior != ModoFiltro::ESPECTRAL) modo = modo_auto;
        printf("Auto: grabación tipo %u, filtro %u, pico %.6g -> %s\n",
               diagnostico.tipo_ruido, diagnostico.filtro_n2, diagnostico.pico_hz,
               nombre_modo());
    }
    if (grabacion_reproducir(nombre_modo())) {
        filtros_reiniciar_estados();
        espectral_reiniciar();
        cola_espectral_pendiente = false;
        reiniciar_tiempos();
        const auto& filtros = filtros_configuracion();
        const auto& espectral = espectral_configuracion();
        ConfiguracionMetricas configuracion;
        configuracion.banda_lo = filtros.banda_inferior_hz;
        configuracion.banda_hi = filtros.banda_superior_hz;
        configuracion.pico_hz = grabacion_diagnostico().pico_hz;
        configuracion.notch_hz = filtros.notch_hz;
        configuracion.notch_q = filtros.q_notch;
        configuracion.alfa = espectral.alfa;
        configuracion.ganancia_minima = espectral.ganancia_minima;
        metricas_iniciar(configuracion);
    }
}

static void seleccionar_modo(ModoFiltro nuevo, bool manual = true)
{
    if (nuevo != ModoFiltro::ESPECTRAL && nuevo != modo_temporal) {
        modo_temporal = nuevo;
    }
    if (manual && automatico) {
        automatico = false;
        printf("Auto: desactivado\n");
    }
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
    const DiagnosticoGrabacion& diagnostico = grabacion_diagnostico();
        printf("Estado: %s | auto %s | banda %.6g-%.6g Hz (%s, config %lu) | notch %.6g Hz Q %.6g\n",
            nombre_modo(), automatico ? "on" : "off", cfg.banda_inferior_hz,
            cfg.banda_superior_hz, banda_es_nodo1 ? "nodo1" : "local",
            (unsigned long)config_nodo1, cfg.notch_hz, cfg.q_notch);
    printf("Diagnóstico grabación: tipo %u | filtro %u | pico %.6g Hz\n",
        diagnostico.tipo_ruido, diagnostico.filtro_n2, diagnostico.pico_hz);
    printf("Ruta temporal independiente: %s\n", nombre_modo(modo_temporal));
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

    if (comando && std::strcmp(comando, "metricas") == 0 && !primero) {
        metricas_imprimir();
        return;
    }

    if (comando && std::strcmp(comando, "vista") == 0 && primero && !segundo) {
        if (std::strcmp(primero, "breve") == 0) vista_breve = true;
        else if (std::strcmp(primero, "todo") == 0) vista_breve = false;
        else {
            printf("Error: comando o valores invalidos\n");
            return;
        }
        printf("Vista: %s\n", vista_breve ? "breve" : "todo");
        return;
    }

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
        printf("Auto: %s\n", automatico ? "on" : "off");
        return;
    }
    if (comando && std::strcmp(comando, "auto") == 0 && primero && !segundo) {
        if (std::strcmp(primero, "on") == 0) {
            automatico = true;
            printf("Auto: activado\n");
        } else if (std::strcmp(primero, "off") == 0) {
            automatico = false;
            printf("Auto: desactivado\n");
        } else {
            printf("Error: comando o valores invalidos\n");
        }
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
        const auto espectral_anterior = espectral_configuracion();
        if (std::strcmp(comando, "espectral") == 0 && espectral_configurar(uno, dos)) {
            const auto& cfg = espectral_configuracion();
            if (cfg.alfa != espectral_anterior.alfa || cfg.ganancia_minima != espectral_anterior.ganancia_minima) {
                metricas_invalidar();
            }
            printf("Espectral: alfa %.6g | ganancia minima %.6g\n", cfg.alfa, cfg.ganancia_minima);
            return;
        }
        if (std::strcmp(comando, "banda") == 0 &&
            uno >= 100.0 && dos <= 3000.0 && uno < dos) {
            metricas_invalidar();
            filtros_cambiar_banda(uno, dos);
            banda_es_nodo1 = false;
            printf("Banda: %.6g-%.6g Hz\n", uno, dos);
            imprimir_fir();
            return;
        }
        if (std::strcmp(comando, "notch") == 0 &&
            uno >= 100.0 && uno <= 3000.0 && dos >= 0.5 && dos <= 20.0) {
            metricas_invalidar();
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

static void atender_boton_modo(int64_t ahora_us)
{
    const int boton_actual = gpio_get_level(PIN_BOTON);
    if (boton_actual != boton_leido) {
        boton_leido = boton_actual;
        boton_cambio_us = ahora_us;
    }
    if (boton_leido == boton_estable || ahora_us - boton_cambio_us < BOTON_ESTABLE_US) return;
    boton_estable = boton_leido;
    // Consumir también los flancos durante el bloqueo: mantener pulsado no repite.
    if (boton_estable == 0 && ahora_us >= boton_bloqueado_hasta_us) {
        switch (modo) {
            case ModoFiltro::SIN_FILTRO: seleccionar_modo(ModoFiltro::FIR); break;
            case ModoFiltro::FIR: seleccionar_modo(ModoFiltro::NOTCH); break;
            case ModoFiltro::NOTCH: seleccionar_modo(ModoFiltro::ESPECTRAL); break;
            case ModoFiltro::ESPECTRAL: seleccionar_modo(ModoFiltro::SIN_FILTRO); break;
        }
        boton_bloqueado_hasta_us = ahora_us + BOTON_BLOQUEO_US;
    }
}

static void procesar_input(const uint8_t* datos, uint64_t)
{
    grabacion_input(datos);
}

static void procesar_diag(const uint8_t* datos)
{
    grabacion_diag(datos);
}

static void atender_reproduccion()
{
    if (salida_dac_terminada()) {
        metricas_finalizar();
        metricas_imprimir();
        grabacion_finalizar_reproduccion();
        aplicar_banda_pendiente();
    }
    if (grabacion_estado() != EstadoGrabacion::REPRODUCIENDO || !salida_dac_disponible()) return;
    const ModoFiltro modo_bloque = modo;
    const ModoFiltro temporal_bloque = modo_temporal;
    const int64_t inicio_proc_us = esp_timer_get_time();
    bool ultimo = false;
    if (cola_espectral_pendiente) {
        // Un bloque de ceros completa el solape de las últimas 512 muestras.
        // Se vacían ambas rutas, incluso si se escucha otra salida.
        std::memset(entrada_reproduccion, 0, sizeof(entrada_reproduccion));
        cola_espectral_pendiente = false;
        ultimo = true;
    } else {
        if (!grabacion_leer_bloque(entrada_reproduccion, ultimo)) return;
        cola_espectral_pendiente = ultimo;
        ultimo = false;  // El DAC termina después del bloque de vaciado.
    }
    // La ruta espectral recibe la misma entrada decodificada que FIR y notch.
    // Se calcula antes de que la selección temporal sobrescriba 'salida'.
    const int64_t inicio_espectral_us = esp_timer_get_time();
    espectral_procesar(entrada_reproduccion, salida_espectral);
    const uint64_t espectral_us = static_cast<uint64_t>(esp_timer_get_time() - inicio_espectral_us);
    const int64_t inicio_temporal_us = esp_timer_get_time();
    for (size_t k = 0; k < MUESTRAS_BLOQUE; ++k) {
        const float x = entrada_reproduccion[k];
        float fir, notch;
        filtros_procesar(x, fir, notch);
        salida_fir[k] = fir;
        salida_notch[k] = notch;
        switch (temporal_bloque) {
            case ModoFiltro::SIN_FILTRO:
            case ModoFiltro::ESPECTRAL: salida[k] = x; break;
            case ModoFiltro::FIR: salida[k] = fir; break;
            case ModoFiltro::NOTCH: salida[k] = notch; break;
        }
    }
    const uint64_t temporal_us = static_cast<uint64_t>(esp_timer_get_time() - inicio_temporal_us);
    const int64_t inicio_metricas_us = esp_timer_get_time();
    const TiempoMetricas coste = metricas_procesar(entrada_reproduccion, salida_fir, salida_notch, salida_espectral, ultimo);
    const uint64_t metricas_us = static_cast<uint64_t>(esp_timer_get_time() - inicio_metricas_us);
    salida_dac_input(modo_bloque == ModoFiltro::ESPECTRAL ? salida_espectral : salida, ultimo);
    const uint64_t total_us = static_cast<uint64_t>(esp_timer_get_time() - inicio_proc_us);
    registrar_duracion(proc_temporal, temporal_us + coste.temporal_us);
    registrar_duracion(proc_espectral, espectral_us + coste.espectral_us);
    registrar_duracion(proc_total, total_us);
    metricas_registrar_tiempos(coste, temporal_us, espectral_us,
                               total_us, metricas_us);
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
    boton_leido = boton_estable = gpio_get_level(PIN_BOTON);
    boton_cambio_us = esp_timer_get_time();
    reproducir_anterior = gpio_get_level(PIN_REPRODUCIR);

    filtros_iniciar();
    // Inicializar ESP-DSP antes de reservar la grabación: también usa RAM interna.
    ESP_ERROR_CHECK(espectral_iniciar());
    salida_dac_iniciar();
    recepcion_iniciar(procesar_input, procesar_diag, procesar_control, grabacion_nueva_sesion);
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
    int64_t ultima_medicion_rx_us = ultimo_resumen_us;
    ContadoresRecepcion rx_anterior = recepcion_contadores();
    uint32_t desbordes_resumen_anterior = salida_dac_contadores().desbordes;
    int64_t ultimo_error_dac_us = -1;
    uint32_t desbordes_anteriores = 0;
    for (;;) {
        const bool hubo_bytes = recepcion_leer();
        // Los comandos se aplican después de terminar todos los INPUT de la lectura.
        leer_consola();
        atender_boton_modo(esp_timer_get_time());
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
            ++numero_resumen;
            if (vista_breve) {
                const double input_por_s = (r.input - rx_anterior.input) * 1000000.0 /
                                           (ahora_us - ultima_medicion_rx_us);
                printf("#%04lu | %s | %s ", (unsigned long)numero_resumen,
                       nombre_modo(), grabacion_nombre_estado());
                if (grabacion_estado() == EstadoGrabacion::REPRODUCIENDO) {
                    printf("%.3f/%.3f s", grabacion_posicion_s(), grabacion_duracion_s());
                } else {
                    printf("%.3f s", grabacion_duracion_s());
                }
                printf(" | RX %.1f/s | RMS %.3f fondo %.3f | proc T %.3f ms E %.3f ms",
                       input_por_s, grabacion_rms(), grabacion_fondo(),
                       proc_temporal.suma_us / (divisor * 1000.0),
                       proc_espectral.suma_us / (divisor * 1000.0));
                bool alerta = false;
                const auto imprimir_aumento = [&alerta](const char* nombre, uint64_t total,
                                                       uint64_t anterior) {
                    if (total <= anterior) return;
                    printf("%s%s +%llu (total %llu)", alerta ? ", " : " | ALERTA ", nombre,
                           (unsigned long long)(total - anterior), (unsigned long long)total);
                    alerta = true;
                };
                imprimir_aumento("err_trama", r.err_trama, rx_anterior.err_trama);
                imprimir_aumento("err_cobs", r.err_cobs, rx_anterior.err_cobs);
                imprimir_aumento("err_crc", r.err_crc, rx_anterior.err_crc);
                imprimir_aumento("err_cabecera", r.err_cabecera, rx_anterior.err_cabecera);
                imprimir_aumento("perdidos", r.perdidos, rx_anterior.perdidos);
                imprimir_aumento("desbordes_dac", d.desbordes, desbordes_resumen_anterior);
                putchar('\n');
            } else {
                printf("#%04lu | Filtro: %s | INPUT %llu | DIAG %llu | CONTROL %llu | err_trama %llu | err_cobs %llu | "
                       "err_crc %llu | err_cabecera %llu | perdidos %llu | sesiones %llu | "
                       "DAC %llu B | desbordes_dac %lu | proc total prom %llu us max %llu us | "
                       "proc temporal prom %llu us max %llu us | proc espectral prom %llu us max %llu us | "
                       "grabación %s | RMS %.6g | fondo %.6g\n",
                       (unsigned long)numero_resumen, nombre_modo(),
                       (unsigned long long)r.input, (unsigned long long)r.diag,
                       (unsigned long long)r.control,
                       (unsigned long long)r.err_trama, (unsigned long long)r.err_cobs,
                       (unsigned long long)r.err_crc, (unsigned long long)r.err_cabecera,
                       (unsigned long long)r.perdidos, (unsigned long long)r.sesiones,
                       (unsigned long long)d.bytes, (unsigned long)d.desbordes,
                       (unsigned long long)(proc_total.suma_us / divisor), (unsigned long long)proc_total.max_us,
                       (unsigned long long)(proc_temporal.suma_us / divisor), (unsigned long long)proc_temporal.max_us,
                       (unsigned long long)(proc_espectral.suma_us / divisor), (unsigned long long)proc_espectral.max_us,
                       grabacion_nombre_estado(), grabacion_rms(), grabacion_fondo());
            }
            // Ambas vistas avanzan la referencia; escribir en consola solo pospone la impresión.
            rx_anterior = r;
            desbordes_resumen_anterior = d.desbordes;
            ultima_medicion_rx_us = ahora_us;
            reiniciar_tiempos();
            ultimo_resumen_us = ahora_us;
        }
        // Un tick son 10 ms con la configuración actual; RX se drena antes de dormir.
        if (!hubo_bytes) vTaskDelay(1);
    }
}
