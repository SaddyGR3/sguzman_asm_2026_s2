#include <cstdio>
#include <cmath>
#include <cstring>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_err.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "driver/gpio.h"
#include "driver/uart.h"
#include "driver/uart_vfs.h"
#include "espectro.h"
#include "diagnostico.h"
#include "generador.h"
#include "protocolo.h"
#include "entrada_adc.h"

enum class Fuente { GENERADOR, ADC };
// Generador: respaldo si falla el micrófono y prueba de la placa N2+N3 sin señal acústica.
constexpr Fuente FUENTE_ENTRADA = Fuente::ADC;

static unsigned N_FFT = 1024;    // transporte fijo en 512; salto de análisis N/2
static float banda_lo = 100.0f, banda_hi = 1200.0f;
static uint32_t config_id = 1;
static bool config_pendiente = true;
constexpr int64_t REPETICION_CONFIG_US = 1000000;
enum class Vista { DIAG, TODO, DEBUG };
static Vista vista = Vista::DIAG;

static const char* nombre_vista()
{
    return vista == Vista::DEBUG ? "debug" : (vista == Vista::TODO ? "todo" : "diag");
}

// 512 muestras a 8 kHz = 64 ms: solo el generador usa el temporizador.
constexpr uint64_t PERIODO_US = 64000;
constexpr uint32_t BLOQUES_VENTANA = 16;   // un resumen cada ~1.024 s

constexpr int BAUDIOS = 921600;
constexpr size_t MARGEN_TX = 64;

static TaskHandle_t tarea_principal = nullptr;   // la lee el callback del temporizador

// El callback corre en la tarea del temporizador (ESP_TIMER_TASK) y no en una
// interrupción, por eso se usa xTaskNotifyGive() y no la versión FromISR.
static void aviso_bloque(void*)
{
    xTaskNotifyGive(tarea_principal);
}

static float x[HOP];                    // micrófono o mezcla del generador
static float s_util[HOP];               // solo generador: señal útil
static float i_interf[HOP];             // solo generador: interferencia

static const char* nombre_ruido(uint8_t tipo)
{
    switch (tipo) {
    case 0: return "ninguno confirmado";
    case 1: return "tonal";
    case 2: return "familia 50/60 Hz";
    case 3: return "banda ancha";
    case 4: return "banda limitada";
    case 5: return "impulsivo";
    default: return "desconocido";
    }
}

static void imprimir_diagnostico(const ResultadoDiagnostico& r)
{
    printf("banda protegida %.1f %.1f Hz | parcial %u calentamiento %u | tipo %u %s "
           "filtro %u método %u | pico_Hz %.4f contraste publicado %.2f dB | "
           "región %.1f %.1f Hz | cresta %.3f | "
           "candidato tonal M %.6g piso local %.6g contraste contra piso %.2f dB | "
           "piso_resumen %.6g | análisis %lu us\n",
           banda_lo, banda_hi, r.parcial ? 1u : 0u, static_cast<unsigned>(r.calentamiento),
           static_cast<unsigned>(r.tipo_ruido), nombre_ruido(r.tipo_ruido),
           static_cast<unsigned>(r.filtro_n2), static_cast<unsigned>(r.metodo),
           r.pico_hz, r.contraste_publicado_db, r.banda_detectada_lo, r.banda_detectada_hi,
           r.factor_cresta, r.magnitud_candidato,
           r.piso_local, r.contraste_db, r.piso_resumen, (unsigned long)r.tiempo_us);
}

static void imprimir_linea_diag(const ResultadoDiagnostico& r, const ResumenAdc* adc,
                                uint32_t desbordes, uint32_t overruns, uint32_t saturaciones)
{
    printf("DIAG | N %u H %u | banda %g-%g Hz | tipo %u %s", N_FFT, N_FFT / 2, banda_lo, banda_hi,
           static_cast<unsigned>(r.tipo_ruido), nombre_ruido(r.tipo_ruido));
    if (r.tipo_ruido == 1 || r.tipo_ruido == 2) {
        printf(" | pico %.1f Hz", r.pico_hz);
        if (r.contraste_publicado_db >= 0.0f) printf(" | contraste %.1f dB", r.contraste_publicado_db);
        else printf(" | contraste --");
    } else {
        printf(" | pico -- | contraste --");
    }
    if (r.tipo_ruido == 3 || r.tipo_ruido == 4)
        printf(" | región %.1f-%.1f Hz", r.banda_detectada_lo, r.banda_detectada_hi);
    else printf(" | región --");
    printf(" | cresta %.2f", r.factor_cresta);
    if (r.parcial || r.calentamiento) printf(" | calentando");
    if (adc != nullptr) printf(" | ADC x %d-%d mV", adc->x.mv_min, adc->x.mv_max);
    if (desbordes || overruns || saturaciones) {
        printf(" | ALERTA desbordes %lu overruns %lu saturaciones %lu",
               (unsigned long)desbordes, (unsigned long)overruns, (unsigned long)saturaciones);
    }
    printf("\n");
}

static void ayuda_consola()
{
    printf(">> comando no reconocido. Comandos: n <256|512|1024>, banda <lo> <hi>, estado, vista diag|todo|debug, "
           "fondo_diag calibrar, umbral_diag <nombre> <valor>\n"
           ">> umbrales: tonal red impulsivo banda fondo tonal_pct red_rel red_pct region_pct rafaga pico_fondo\n");
}

static void imprimir_grupo_debug(const char* nombre, const GrupoPicosDebug& grupo)
{
    printf("DEBUG %s: %u picos", nombre, grupo.cantidad);
    const unsigned mostrados = grupo.cantidad < DIAG_DEBUG_MAX_PICOS ? grupo.cantidad : DIAG_DEBUG_MAX_PICOS;
    if (grupo.cantidad > mostrados) printf(" (solo %u más fuertes)", mostrados);
    for (unsigned j = 0; j < mostrados; ++j) {
        const auto& p = grupo.picos[j];
        const double magnitud = std::fmax(p.magnitud, 1e-12f);
        const double contraste = 20.0 * std::log10(magnitud / std::fmax(p.piso, 1e-12f));
        const double relativo = 20.0 * std::log10(magnitud / std::fmax(grupo.picos[0].magnitud, 1e-12f));
        printf(" | %.1fHz C%.1f R%.1f", p.hz, contraste, relativo);
    }
    putchar('\n');
}

static void imprimir_energia_debug(const char* nombre, const EnergiaPicoDebug& pico, double total)
{
    if (pico.hz < 0.0f) {
        printf("DEBUG energía %s: --\n", nombre);
        return;
    }
    const double resto = total - pico.energia;
    printf("DEBUG energía %s %.1fHz | bin ±2 %.6g | fracción %.2f %% | resto %.6g",
           nombre, pico.hz, pico.energia, pico.porcentaje, resto);
    if (pico.energia > 0.0 && resto > 0.0)
        printf(" | pico/resto %.2f dB\n", 10.0 * std::log10(pico.energia / resto));
    else printf(" | pico/resto --\n");
}

static void imprimir_debug()
{
    const auto& d = diagnostico_debug();
    const auto& u = diagnostico_umbrales();
    const auto& f = diagnostico_fondo();
    printf("DEBUG fondo PL02 %s | espera %u bloques | captura %u/%u | RMS %.6g | corto P95 %.6g pico P95 %.6g | nivel sobre fondo %u\n",
           f.listo ? "listo" : "calibrando", f.espera, f.bloques, DIAG_FONDO_BLOQUES, f.rms,
           f.corto_p95, f.pico_p95,
           d.nivel_suficiente ? 1u : 0u);
    printf("DEBUG selección | exceso fuera %.6g | pico evaluado %.1f Hz %.2f %% (mín %g) | red 50 %.2f %% 60 %.2f %% (mín %g) | región %.2f %% (mín %g)\n",
           d.exceso_fuera, d.pico_evaluado_hz, d.tonal_porcentaje, u.tonal_pct, d.red_porcentaje_50, d.red_porcentaje_60,
           u.red_pct, d.region_porcentaje, u.region_pct);
    printf("DEBUG armónicos antes de nivel relativo | 50 %u 60 %u | magnitud mínima %g %% del más fuerte\n",
           d.armonicos_brutos_50, d.armonicos_brutos_60, u.red_rel);
    printf("DEBUG impulso PL02 | contraste corto %.3f | subbloques fuertes %u/16 | candidato %u | candidatos intervalo %lu\n",
           d.razon_rafaga, d.subbloques_fuertes, d.impulso_candidato ? 1u : 0u,
           (unsigned long)d.candidatas_impulsivo);
    printf("DEBUG umbrales impulso | corto máximo %.6g mínimo fondo %.6g | pico mínimo fondo %.6g | supera ambos %u | rechazados fondo intervalo %lu\n",
           d.corto_max, d.corto_min_fondo, d.pico_min_fondo, d.impulso_sobre_fondo ? 1u : 0u,
           (unsigned long)d.impulsos_rechazados_fondo);
    printf("DEBUG activo %u ventana_valida %u | umbrales tonal %g red %g cresta %g | candidato independiente %.1f Hz\n",
           d.activo ? 1u : 0u, d.ventana_valida ? 1u : 0u, u.tonal, u.red, u.impulsivo, d.candidato_tonal_hz);
    printf("DEBUG nivel actual [min,max intervalo] | RMS %.6g [%.6g,%.6g] | pico abs %.6g [%.6g,%.6g] | cresta %.3f [%.3f,%.3f]\n",
           d.rms.actual, d.rms.minimo, d.rms.maximo, d.pico_temporal.actual, d.pico_temporal.minimo,
           d.pico_temporal.maximo, d.cresta.actual, d.cresta.minimo, d.cresta.maximo);
    printf("DEBUG ancha PL01 evaluada %u | ocupación %.2f %% [%.2f,%.2f] mínimo %.0f %% | planitud piso %.4f [%.4f,%.4f] mínimo %.2f | "
           "candidata %u confirmada %u confirma %u/3 ausencias %u/3\n",
           d.ancha_evaluada ? 1u : 0u, d.ocupacion.actual, d.ocupacion.minimo, d.ocupacion.maximo,
           100.0f * DIAG_OCUPACION_MINIMA, d.planitud.actual, d.planitud.minimo, d.planitud.maximo,
           DIAG_PLANITUD_MINIMA, d.ancha_candidata ? 1u : 0u, d.ancha_confirmada ? 1u : 0u,
           d.confirmaciones_ancha, d.ausencias_ancha);
    printf("DEBUG limitada candidata %.1f-%.1f Hz | confirmada %.1f-%.1f Hz | confirma %u/3 ausencias %u/3 | "
           "piso global %.6g umbral %.6g | energía región candidata %.6g\n",
           d.limitada_candidata_lo, d.limitada_candidata_hi, d.limitada_publicada_lo, d.limitada_publicada_hi,
           d.confirmaciones_limitada, d.ausencias_limitada, d.referencia_global, d.umbral_limitada, d.energia_region);
    printf("DEBUG energía FFT 100-3000 Hz: %.6g (suma de magnitudes al cuadrado)\n", d.energia_analisis);
    imprimir_energia_debug("publicado", d.energia_publicado, d.energia_analisis);
    imprimir_energia_debug("candidato tonal", d.energia_candidato, d.energia_analisis);
    printf("DEBUG red elegida %u Hz | 50: actuales %u publicados %u confirma %u/3 ausencias %u/3 | "
           "60: actuales %u publicados %u confirma %u/3 ausencias %u/3\n",
           d.familia_elegida, d.red_50.cantidad, d.armonicos_publicados_50, d.confirmaciones_50, d.ausencias_50,
           d.red_60.cantidad, d.armonicos_publicados_60, d.confirmaciones_60, d.ausencias_60);
    imprimir_grupo_debug("50 actual", d.red_50);
    imprimir_grupo_debug("60 actual", d.red_60);
    if (d.familia_elegida) {
        const auto& publicada = d.familia_elegida == 50 ? d.publicada_50 : d.publicada_60;
        imprimir_grupo_debug("familia publicada", publicada);
        if (!publicada.cantidad) printf("DEBUG lista publicada no capturada aún; activar debug antes de la señal\n");
    }
    imprimir_grupo_debug("máximos fuera de protección (antes de excluir red)", d.maximos);
    printf("DEBUG intervalo %lu análisis | supera cresta %lu | confirma impulsivo 2/3 %lu | "
           "tipos 0:%lu 1:%lu 2:%lu 3:%lu 4:%lu 5:%lu\n",
           (unsigned long)d.bloques, (unsigned long)d.supera_cresta, (unsigned long)d.confirma_impulsivo,
           (unsigned long)d.tipos[0], (unsigned long)d.tipos[1], (unsigned long)d.tipos[2],
           (unsigned long)d.tipos[3], (unsigned long)d.tipos[4], (unsigned long)d.tipos[5]);
    printf("DEBUG bandas intervalo | ancha candidata %lu confirmada %lu | limitada candidata %lu confirmada %lu\n",
           (unsigned long)d.candidatas_ancha, (unsigned long)d.confirmadas_ancha,
           (unsigned long)d.candidatas_limitada, (unsigned long)d.confirmadas_limitada);
    diagnostico_debug_reiniciar_contadores();
}

static void imprimir_umbrales()
{
    const auto& u = diagnostico_umbrales();
    printf(">> umbrales lineales: tonal %g red %g impulsivo %g banda %g | RMS mínimo %g\n"
           ">> banda ancha: ocupación mínima %.0f %% con piso > %g de mediana global | planitud mínima %g\n",
           u.tonal, u.red, u.impulsivo, u.banda, DIAG_RMS_MINIMO,
           100.0f * DIAG_OCUPACION_MINIMA, DIAG_FRACCION_PISO, DIAG_PLANITUD_MINIMA);
    printf(">> razones: fondo %g rafaga %g pico_fondo %g | porcentajes: tonal_pct %g red_rel %g red_pct %g region_pct %g\n",
           u.fondo, u.rafaga, u.pico_fondo, u.tonal_pct, u.red_rel, u.red_pct, u.region_pct);
    printf(">> banda ancha PL01 exige elevación sobre fondo; planitud del piso sin resta. Limitada: máximo %g Hz.\n",
           DIAG_ANCHURA_MAXIMA_HZ);
    const auto& f = diagnostico_fondo();
    printf(">> fondo PL02 %s | espera %u bloques | captura %u/%u | RMS %.6g | corto P95 %.6g pico P95 %.6g | margen %g\n",
           f.listo ? "listo" : "calibrando", f.espera, f.bloques, DIAG_FONDO_BLOQUES, f.rms,
           f.corto_p95, f.pico_p95, DIAG_MARGEN_TRANSITORIOS);
}

static void comando_consola(const char* linea)
{
    char comando[16], modo[16], extra;
    float lo, hi;
    if (sscanf(linea, " %15s", comando) != 1) return;
    if (strcmp(comando, "n") == 0) {
        if (sscanf(linea, " %15s %15s %c", comando, modo, &extra) != 2 ||
            (strcmp(modo, "256") != 0 && strcmp(modo, "512") != 0 && strcmp(modo, "1024") != 0)) {
            printf(">> error: n 256|512|1024; configuración conservada\n");
            return;
        }
        const unsigned solicitado = strcmp(modo, "256") == 0 ? 256u : strcmp(modo, "512") == 0 ? 512u : 1024u;
        if (!diagnostico_cambiar_n(solicitado)) return;
        if (solicitado != N_FFT) {
            N_FFT = solicitado;
            if (++config_id == 0) config_id = 1;
            config_pendiente = true;
        }
        printf(">> FFT N %u H %u | resolución %.4f Hz | config %lu\n",
               N_FFT, N_FFT / 2, 8000.0 / N_FFT, (unsigned long)config_id);
    } else if (strcmp(comando, "umbral_diag") == 0) {
        float valor;
        if (sscanf(linea, " %15s %15s %f %c", comando, modo, &valor, &extra) != 3 ||
            !diagnostico_ajustar_umbral(modo, valor)) {
            printf(">> error: umbral_diag <nombre> <valor>, finito en (1, 100]. "
                   "Se conservan los umbrales.\n");
            ayuda_consola();
        } else {
            printf(">> umbral_diag %s %g | clasificación reiniciada\n", modo, valor);
        }
    } else if (strcmp(comando, "fondo_diag") == 0 &&
               sscanf(linea, " %15s %15s %c", comando, modo, &extra) == 2 &&
               strcmp(modo, "calibrar") == 0) {
        if (FUENTE_ENTRADA == Fuente::ADC) {
            diagnostico_calibrar_fondo();
            printf(">> calibrando fondo: mantener silencio con micrófono conectado ~3 s; esperar fondo listo.\n");
        } else printf(">> el generador utiliza fondo cero; la calibración corresponde al micrófono.\n");
    } else if (strcmp(comando, "banda") == 0 &&
        sscanf(linea, " %15s %f %f %c", comando, &lo, &hi, &extra) == 3) {
        if (std::isfinite(lo) && std::isfinite(hi) && lo >= 100.0f && lo < hi && hi <= 3000.0f) {
            if (lo != banda_lo || hi != banda_hi) {
                if (++config_id == 0) config_id = 1;  // cero está reservado
                config_pendiente = true;
            }
            banda_lo = lo;
            banda_hi = hi;
            diagnostico_banda(lo, hi);
            printf(">> banda protegida: %g-%g Hz | config %lu\n", lo, hi, (unsigned long)config_id);
        } else {
            ayuda_consola();
        }
    } else if (strcmp(comando, "vista") == 0 &&
               sscanf(linea, " %15s %15s %c", comando, modo, &extra) == 2 &&
               (strcmp(modo, "diag") == 0 || strcmp(modo, "todo") == 0 || strcmp(modo, "debug") == 0)) {
        vista = strcmp(modo, "debug") == 0 ? Vista::DEBUG : (strcmp(modo, "diag") == 0 ? Vista::DIAG : Vista::TODO);
        diagnostico_debug_activar(vista == Vista::DEBUG);
        printf(">> vista: %s\n", nombre_vista());
    } else if (strcmp(comando, "estado") == 0 &&
               sscanf(linea, " %15s %c", comando, &extra) == 1) {
        printf(">> banda protegida: %g-%g Hz | config %lu\n>> vista: %s\n",
               banda_lo, banda_hi, (unsigned long)config_id, nombre_vista());
        printf(">> FFT N %u H %u | resolución %.4f Hz\n", N_FFT, N_FFT / 2, 8000.0 / N_FFT);
        imprimir_umbrales();
        printf(">> ");
        imprimir_linea_diag(diagnostico_resultado(), nullptr, 0, 0, 0);
    } else {
        ayuda_consola();
    }
}

static void leer_consola()
{
    static char linea[96];
    static size_t usados = 0;
    static bool descartar = false;
    static uint8_t datos[64];
    static int posicion = 0, recibidos = 0;
    // Lectura acotada y sin espera: no drena indefinidamente la consola.
    if (posicion == recibidos) {
        const int n = uart_read_bytes(UART_NUM_0, datos, sizeof(datos), 0);
        if (n <= 0) return;
        posicion = 0;
        recibidos = n;
    }
    while (posicion < recibidos) {
        const char c = static_cast<char>(datos[posicion++]);
        if (c == '\r' || c == '\n') {
            const bool hubo_comando = descartar || usados > 0;
            if (descartar) ayuda_consola();
            else if (usados > 0) {
                linea[usados] = '\0';
                comando_consola(linea);
            }
            usados = 0;
            descartar = false;
            // Una respuesta por bloque; conserva el resto para la próxima vuelta.
            if (hubo_comando) return;
        } else if (!descartar) {
            if (c == '\b' || c == 127) {
                if (usados > 0) --usados;
            } else if (c >= 32 && c < 127) {
                if (usados + 1 < sizeof(linea)) linea[usados++] = c;
                else descartar = true;
            }
        }
    }
}

// Búferes de paquetes (estáticos: la pila de app_main es pequeña).
static uint8_t trabajo[TAM_TRABAJO];          // cabecera + datos + CRC, antes de COBS
static uint8_t sal_input[CABLE_INPUT];
static uint8_t sal_diag2[CABLE_DIAG];         // DIAG hacia el nodo 2
static uint8_t diag64[TAM_DIAG];
static uint8_t control32[TAM_CONTROL];
static uint8_t sal_control[CABLE_CONTROL];
static uint32_t session_id = 0;

// Enlace UART hacia la placa N2+N3, con sus contadores de transmisión.
struct Enlace {
    uart_port_t puerto;
    uint64_t enviados = 0;        // bytes escritos en el búfer del driver (acumulado)
    uint32_t desbordes_tx = 0;    // bloques descartados por falta de espacio (acumulado)
    uint32_t esc_max_us = 0;      // máximo tiempo de escritura de la ventana
    Enlace(uart_port_t p) : puerto(p) {}
};

static Enlace enlace_n2(UART_NUM_1);

// Configura una UART a 921600 8N1 sin control de flujo, sin cola de eventos.
static void iniciar_uart(uart_port_t puerto, int tx, int rx, int buf_tx, int buf_rx_tam)
{
    uart_config_t cfg = {};
    cfg.baud_rate = BAUDIOS;
    cfg.data_bits = UART_DATA_8_BITS;
    cfg.parity = UART_PARITY_DISABLE;
    cfg.stop_bits = UART_STOP_BITS_1;
    cfg.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    cfg.source_clk = UART_SCLK_DEFAULT;
    ESP_ERROR_CHECK(uart_param_config(puerto, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(puerto, tx, rx, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    // RX sin conectar: el pull-up evita bytes y errores causados por ruido.
    ESP_ERROR_CHECK(gpio_set_pull_mode(static_cast<gpio_num_t>(rx), GPIO_PULLUP_ONLY));
    ESP_ERROR_CHECK(uart_driver_install(puerto, buf_rx_tam, buf_tx, 0, NULL, 0));
}

// Envía un bloque (datos + DIAG) sin bloquear: si no hay espacio en el búfer de TX
// se descarta completo. uart_write_bytes copia al búfer del driver y vuelve, así que
// los búferes de salida se pueden reutilizar en el bloque siguiente.
static bool enviar_bloque(Enlace& e, const uint8_t* datos, size_t l1,
                          const uint8_t* diag, size_t l2)
{
    const int64_t t0 = esp_timer_get_time();
    size_t libre = 0;
    ESP_ERROR_CHECK(uart_get_tx_buffer_free_size(e.puerto, &libre));

    // El margen de 64 B cubre la descripción (20 B), los encabezados (8 B por trozo) y el
    // relleno a múltiplo de 4 de las dos escrituras, que la función no descuenta del todo.
    if (libre >= l1 + l2 + MARGEN_TX) {
        if (l1 > 0) uart_write_bytes(e.puerto, datos, l1);
        uart_write_bytes(e.puerto, diag, l2);
        const int64_t t1 = esp_timer_get_time();
        const uint32_t escritura = static_cast<uint32_t>(t1 - t0);
        if (escritura > e.esc_max_us) e.esc_max_us = escritura;
        e.enviados += l1 + l2;
        return true;
    } else {
        // Sin reintento: el audio vencido se descarta. Los sequence ya asignados dejan un
        // salto que el receptor cuenta como pérdida.
        ++e.desbordes_tx;
        const uint32_t escritura = static_cast<uint32_t>(esp_timer_get_time() - t0);
        if (escritura > e.esc_max_us) e.esc_max_us = escritura;
        return false;
    }
}

// Solo se intenta después de encolar INPUT + DIAG. Sin espacio, queda pendiente;
// no consume sequence ni cuenta como descarte de audio. Un único productor TX.
static bool enviar_config(uint32_t& secuencia, uint64_t indice_efectivo)
{
    size_t libre = 0;
    ESP_ERROR_CHECK(uart_get_tx_buffer_free_size(enlace_n2.puerto, &libre));
    // Una escritura adicional: reservar de nuevo el margen para su metadato y relleno.
    if (libre < CABLE_CONTROL + MARGEN_TX) return false;
    const int64_t inicio = esp_timer_get_time();
    armar_control_config(config_id, indice_efectivo, banda_lo, banda_hi, static_cast<uint16_t>(N_FFT), control32);
    const size_t largo = armar_paquete(TIPO_CONTROL, NODO_1, NODO_2, 0,
        session_id, secuencia++, indice_efectivo, 0, FORMATO_META, 0,
        control32, TAM_CONTROL, trabajo, sal_control);
    uart_write_bytes(enlace_n2.puerto, sal_control, largo);
    enlace_n2.enviados += largo;
    const uint32_t duracion = static_cast<uint32_t>(esp_timer_get_time() - inicio);
    if (duracion > enlace_n2.esc_max_us) enlace_n2.esc_max_us = duracion;
    return true;
}

// INPUT hacia el nodo 2. Un arreglo de float no tiene relleno y el ESP32 es
// little-endian con IEEE 754, así que los bytes de x ya son los del protocolo.
static size_t paquete_input(uint32_t seq, uint16_t flags, uint64_t muestra)
{
    return armar_paquete(TIPO_INPUT, NODO_1, NODO_2, flags, session_id, seq, muestra,
                         HOP, FORMATO_FLOAT32, 1,
                         reinterpret_cast<const uint8_t*>(x), TAM_DATOS_INPUT,
                         trabajo, sal_input);
}

// DIAG ya armado en diag64, hacia el destino indicado.
static size_t paquete_diag(uint8_t dst, uint32_t seq, uint64_t muestra, uint16_t flags, uint8_t* salida)
{
    return armar_paquete(TIPO_DIAG, NODO_1, dst, flags, session_id, seq, muestra,
                         0, FORMATO_META, 0, diag64, TAM_DIAG, trabajo, salida);
}

// Imprime los 32 B de la cabecera que quedaron en 'trabajo' (antes de COBS).
static void imprimir_cabecera(const char* nombre)
{
    printf("cabecera %s:", nombre);
    for (size_t k = 0; k < TAM_CABECERA; ++k) printf(" %02X", trabajo[k]);
    printf("\n");
}

// Pruebas del CRC y del COBS con vectores conocidos.
static void pruebas_protocolo()
{
    const uint8_t texto[] = {'1', '2', '3', '4', '5', '6', '7', '8', '9'};
    const uint32_t crc = crc32(texto, sizeof(texto));
    printf("CRC \"123456789\": %s (0x%08lX)\n", crc == 0xCBF43926u ? "PASS" : "FAIL",
           (unsigned long)crc);

    const uint8_t entrada[] = {0x11, 0x00, 0x22};
    const uint8_t esperado[] = {0x02, 0x11, 0x02, 0x22};
    uint8_t salida[8];
    const size_t n = cobs_codificar(entrada, sizeof(entrada), salida);
    bool ok = (n == sizeof(esperado));
    for (size_t k = 0; ok && k < n; ++k) ok = (salida[k] == esperado[k]);
    printf("COBS 11 00 22: %s (", ok ? "PASS" : "FAIL");
    for (size_t k = 0; k < n; ++k) printf(k ? " %02X" : "%02X", salida[k]);
    printf(")\n");
}

extern "C" void app_main(void)
{
    // Dos generadores: señal útil s e interferencia i. x = s + i.
    Generador gen_s;
    Generador gen_i;
    const float g = 0.26f;                       // escala común: pico < 0.8
    gen_s.configurar(0, 300.0f,  1.00f * g);
    gen_s.configurar(1, 700.0f,  0.55f * g);
    gen_s.configurar(2, 1100.0f, 0.30f * g);
    gen_i.configurar(0, 2150.0f, 1.18f * g);     // interferencia, SNR de 0 dB

    crc32_iniciar();                             // antes de cualquier CRC
    pruebas_protocolo();

    // Identificador del ensayo. Sin Wi-Fi esp_random() es pseudoaleatorio,
    // pero basta para distinguir una sesión de otra.
    session_id = esp_random();

    // Cabecera del primer INPUT (no depende de los datos).
    paquete_input(0, FLAG_REINICIO, 0);
    imprimir_cabecera("INPUT");

    // UART1 -> placa N2+N3. El INPUT cabe en el búfer TX de 8 KB.
    iniciar_uart(UART_NUM_1, 18, 19, 8192, 8192);
    uint32_t baud1 = 0;
    ESP_ERROR_CHECK(uart_get_baudrate(UART_NUM_1, &baud1));
    printf("UART1 baud real %lu\n", (unsigned long)baud1);

    // Análisis común sobre la x transmitida; no avanza los generadores.
    ESP_ERROR_CHECK(espectro_iniciar(N_FFT));
    diagnostico_iniciar(FUENTE_ENTRADA == Fuente::ADC);
    diagnostico_banda(banda_lo, banda_hi);
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0, 1024, 4096, 0, nullptr, 0));
    // Los resúmenes se copian a TX; su transmisión a 115200 no frena el bloque.
    uart_vfs_dev_use_driver(UART_NUM_0);
    printf("Consola: n <256|512|1024>, banda <lo> <hi>, estado, vista diag|todo|debug, "
           "fondo_diag calibrar, umbral_diag <nombre> <valor> | banda protegida inicial 100 1200 Hz\n");
    if (FUENTE_ENTRADA == Fuente::ADC)
        printf("Fondo: mantener silencio con micrófono conectado ~3 s; esperar fondo listo antes de reproducir.\n");

    // Un único 0x00 en UART1. Si el emisor se reinicia a mitad de un paquete, ese paquete
    // queda cortado sin su 0x00; el receptor juntaría esos restos con el primer paquete de la
    // sesión nueva (sequence 0, bandera 0x0004) y fallaría el CRC. El 0x00 cierra los restos
    // como una trama aparte y el receptor descarta las tramas vacías (resincronización COBS).
    static const uint8_t cero = 0;
    uart_write_bytes(enlace_n2.puerto, &cero, 1);

    if (FUENTE_ENTRADA == Fuente::GENERADOR) {
        printf("Fuente GENERADOR: salida INPUT + DIAG y CONTROL CONFIG por UART1 (GPIO18).\n");

        // Solo el generador usa el temporizador de 64 ms.
        tarea_principal = xTaskGetCurrentTaskHandle();
        esp_timer_create_args_t args = {};
        args.callback = aviso_bloque;
        args.dispatch_method = ESP_TIMER_TASK;
        args.name = "bloque";
        esp_timer_handle_t temporizador = nullptr;
        ESP_ERROR_CHECK(esp_timer_create(&args, &temporizador));
        ESP_ERROR_CHECK(esp_timer_start_periodic(temporizador, PERIODO_US));
    } else {
        printf("Fuente ADC: micrófono en GPIO36=x, 24000 Hz; "
               "salida INPUT + DIAG y CONTROL CONFIG por UART1 (GPIO18).\n");
        entrada_adc_iniciar();
    }

    uint64_t first_sample = 0;   // índice de la primera muestra del siguiente bloque
    uint32_t atrasos_temporizador = 0;   // solo GENERADOR, acumulado
    uint32_t bloques = 0;        // bloques procesados (acumulado)

    // Secuencia de UART1; el primer INPUT lleva reinicio.
    uint32_t seq_n2 = 0;
    bool primer_n2 = true;

    uint32_t numero_resumen = 0;

    // Valores de la ventana de resumen; se reinician al imprimir.
    uint32_t v_bloques = 0;
    uint32_t v_periodos = 0;
    uint32_t v_per_min = 0xFFFFFFFF;
    uint32_t v_per_max = 0;
    uint64_t v_per_suma = 0;
    uint32_t v_procesamiento_max = 0;
    uint32_t v_emp_max = 0;
    uint32_t v_analisis_max = 0;
    uint32_t desbordes_previos = 0, overruns_previos = 0, saturaciones_previas = 0;
    ContadoresAdc adc_bloque_anterior;
    size_t cable_input = 0, cable_diag = 0;

    int64_t inicio_anterior = -1;   // la primera iteración no tiene periodo
    int64_t ultimo_config_us = 0;

    for (;;) {
        // Espera el aviso. Si n > 1, llegaron avisos mientras el bloque anterior
        // seguía en proceso: cada uno de más es un overrun.
        if (FUENTE_ENTRADA == Fuente::GENERADOR) {
            const uint32_t n = ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
            if (n > 1) atrasos_temporizador += n - 1;
        }

        const int64_t inicio = esp_timer_get_time();
        if (inicio_anterior >= 0) {
            const uint32_t periodo = static_cast<uint32_t>(inicio - inicio_anterior);
            if (periodo < v_per_min) v_per_min = periodo;
            if (periodo > v_per_max) v_per_max = periodo;
            v_per_suma += periodo;
            ++v_periodos;
        }
        inicio_anterior = inicio;

        // Todos los paquetes del bloque llevan el índice de su primera muestra.
        const uint64_t muestra_inicial = first_sample;

        uint32_t procesamiento_adc_us = 0;
        ContadoresAdc adc_bloque;
        if (FUENTE_ENTRADA == Fuente::GENERADOR) {
            // Generadores continuos: la fase pasa de un bloque al siguiente.
            gen_s.generar(s_util, HOP);
            gen_i.generar(i_interf, HOP);
            for (int k = 0; k < HOP; ++k) x[k] = s_util[k] + i_interf[k];
        } else {
            // Completa 1536 muestras crudas y 512 salidas de x.
            procesamiento_adc_us = entrada_adc_leer_bloque(x);
            adc_bloque = entrada_adc_contadores();
        }
        const int64_t fin_procesamiento = esp_timer_get_time();
        const uint32_t duracion = FUENTE_ENTRADA == Fuente::GENERADOR
            ? static_cast<uint32_t>(fin_procesamiento - inicio) : procesamiento_adc_us;
        if (duracion > v_procesamiento_max) v_procesamiento_max = duracion;

        leer_consola();
        const bool capturando_fondo = !diagnostico_fondo().listo;
        const auto& diagnostico = diagnostico_procesar(x, muestra_inicial);
        if (capturando_fondo && diagnostico_fondo().listo)
            printf(">> fondo listo | RMS %.6g | puede reproducir\n", diagnostico_fondo().rms);
        if (diagnostico.tiempo_us > v_analisis_max) v_analisis_max = diagnostico.tiempo_us;
        uint16_t flags_analisis = 0;
        if (diagnostico.parcial) flags_analisis |= FLAG_VENTANA_PARCIAL;
        if (diagnostico.calentamiento) flags_analisis |= FLAG_CALENTAMIENTO;
        if (FUENTE_ENTRADA == Fuente::ADC) {
            if (adc_bloque.desbordes_pool != adc_bloque_anterior.desbordes_pool) {
                flags_analisis |= FLAG_DISCONTINUIDAD;
            }
            // Eventos posteriores a esta lectura se señalan en el siguiente bloque.
            adc_bloque_anterior = adc_bloque;
        }
        const int64_t inicio_empaquetado = esp_timer_get_time();

        first_sample += HOP;
        ++bloques;
        ++v_bloques;

        // Empaquetado: energía de x y los dos paquetes INPUT + DIAG.
        float energia = 0.0f;
        for (int k = 0; k < HOP; ++k) {
            energia += x[k] * x[k];
        }

        Diag d;
        d.fs = static_cast<uint32_t>(FS_HZ);
        d.N = N_FFT;
        d.H = N_FFT / 2;
        d.pico_Hz = diagnostico.pico_hz;
        // DIAG describe ruido; CONTROL CONFIG conserva la banda protegida.
        d.banda_lo = diagnostico.banda_detectada_lo;
        d.banda_hi = diagnostico.banda_detectada_hi;
        d.config_id = config_id;
        d.piso_resumen = diagnostico.piso_resumen;
        d.DC = diagnostico.dc;
        d.metodo = diagnostico.metodo;
        d.tipo_ruido = diagnostico.tipo_ruido;
        d.filtro_n2 = diagnostico.filtro_n2;
        d.calentamiento = diagnostico.calentamiento;
        d.energia = energia;
        d.tiempo_us = diagnostico.tiempo_us;
        // Overruns = atrasos del temporizador (GENERADOR) + descartes TX de UART1.
        // Un descarte se informa en el siguiente DIAG que logre transmitirse.
        d.overruns = atrasos_temporizador + enlace_n2.desbordes_tx;
        if (FUENTE_ENTRADA == Fuente::ADC) {
            d.perdidas = adc_bloque.desbordes_pool;
            d.saturaciones = adc_bloque.saturaciones;
        }
        d.inicio_ventana = diagnostico.inicio_ventana;
        armar_diag(d, diag64);

        // Enlace N1 -> N2: INPUT y DIAG.
        cable_input = paquete_input(seq_n2++, flags_analisis | (primer_n2 ? FLAG_REINICIO : 0), muestra_inicial);
        primer_n2 = false;
        cable_diag = paquete_diag(NODO_2, seq_n2++, muestra_inicial, flags_analisis, sal_diag2);

        const uint32_t empaquetado = static_cast<uint32_t>(esp_timer_get_time() - inicio_empaquetado);
        if (empaquetado > v_emp_max) v_emp_max = empaquetado;

        // Envío por UART1: INPUT y después DIAG.
        const bool audio_enviado = enviar_bloque(enlace_n2, sal_input, cable_input, sal_diag2, cable_diag);
        const int64_t ahora_config_us = esp_timer_get_time();
        if (ahora_config_us - ultimo_config_us >= REPETICION_CONFIG_US) config_pendiente = true;
        if (audio_enviado && config_pendiente && enviar_config(seq_n2, first_sample)) {
            config_pendiente = false;
            ultimo_config_us = esp_timer_get_time();
        }

        // El resumen va al final: el printf cae en el tiempo libre del periodo.
        if (v_bloques == BLOQUES_VENTANA) {
            const uint32_t overruns = atrasos_temporizador + enlace_n2.desbordes_tx;
            ContadoresAdc contadores_resumen;
            printf("#%04lu t=%.1fs | ", (unsigned long)++numero_resumen,
                   esp_timer_get_time() / 1000000.0);
            if (vista == Vista::DIAG || vista == Vista::DEBUG) {
                ResumenAdc adc;
                if (FUENTE_ENTRADA == Fuente::ADC) {
                    adc = entrada_adc_resumen();
                    contadores_resumen = adc.acumulados;
                }
                imprimir_linea_diag(diagnostico_resultado(),
                    FUENTE_ENTRADA == Fuente::ADC ? &adc : nullptr,
                    contadores_resumen.desbordes_pool - desbordes_previos,
                    overruns - overruns_previos,
                    contadores_resumen.saturaciones - saturaciones_previas);
                if (vista == Vista::DEBUG) {
                    imprimir_debug();
                    if (FUENTE_ENTRADA == Fuente::ADC) {
                        printf("DEBUG ADC intervalo | crudo %u-%u | mV %d-%d | saturaciones nuevas %lu\n",
                               static_cast<unsigned>(adc.x.crudo_min), static_cast<unsigned>(adc.x.crudo_max),
                               adc.x.mv_min, adc.x.mv_max,
                               (unsigned long)(contadores_resumen.saturaciones - saturaciones_previas));
                    }
                }
            } else {
                imprimir_diagnostico(diagnostico_resultado());
                printf("análisis max %lu us\n", (unsigned long)v_analisis_max);
                const uint32_t prom = v_periodos ? static_cast<uint32_t>(v_per_suma / v_periodos) : 0;
                printf("bloques %lu | first_sample %llu | periodo prom %lu us (min %lu, max %lu) | procesamiento max %lu us | empaquetar max %lu us | cable INPUT %lu DIAG %lu | pila libre %lu B | overruns %lu\n",
                       (unsigned long)bloques, (unsigned long long)first_sample,
                       (unsigned long)prom, (unsigned long)v_per_min, (unsigned long)v_per_max,
                       (unsigned long)v_procesamiento_max, (unsigned long)v_emp_max,
                       (unsigned long)cable_input, (unsigned long)cable_diag,
                       (unsigned long)uxTaskGetStackHighWaterMark(NULL),
                       (unsigned long)overruns);
                printf("tx UART1 %llu B (esc max %lu us, descartes TX %lu)\n",
                       (unsigned long long)enlace_n2.enviados, (unsigned long)enlace_n2.esc_max_us,
                       (unsigned long)enlace_n2.desbordes_tx);
                if (FUENTE_ENTRADA == Fuente::ADC) {
                    const ResumenAdc adc = entrada_adc_resumen();
                    contadores_resumen = adc.acumulados;
                    printf("ADC x crudo %u-%u mV %d-%d | "
                           "frecuencia ADC x %.1f Hz | salida x %.1f Hz | "
                           "desbordes_pool %lu | saturaciones %lu | "
                           "procesamiento max %lu us (sin espera) | calibración max %lu us | "
                           "FIR+pasa altos+normalización max %lu us\n",
                           static_cast<unsigned>(adc.x.crudo_min), static_cast<unsigned>(adc.x.crudo_max),
                           adc.x.mv_min, adc.x.mv_max,
                           adc.x.frecuencia_adc, adc.x.frecuencia_salida,
                           (unsigned long)adc.acumulados.desbordes_pool,
                           (unsigned long)adc.acumulados.saturaciones,
                           (unsigned long)adc.procesamiento_max_us,
                           (unsigned long)adc.calibracion_max_us,
                           (unsigned long)adc.filtrado_max_us);
                }
            }
            // Referencia de alertas por periodo, también al mostrar vista todo.
            desbordes_previos = contadores_resumen.desbordes_pool;
            overruns_previos = overruns;
            saturaciones_previas = contadores_resumen.saturaciones;
            enlace_n2.esc_max_us = 0;
            v_bloques = 0;
            v_periodos = 0;
            v_per_min = 0xFFFFFFFF;
            v_per_max = 0;
            v_per_suma = 0;
            v_procesamiento_max = 0;
            v_emp_max = 0;
            v_analisis_max = 0;
        }
    }
}
