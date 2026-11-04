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

constexpr int N_FFT = 1024;      // dos bloques de 512
static float banda_lo = 100.0f, banda_hi = 1200.0f;
enum class Vista { DIAG, TODO };
static Vista vista = Vista::DIAG;

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

static void imprimir_diagnostico(const ResultadoDiagnostico& r)
{
    printf("banda protegida %.1f %.1f Hz | parcial %u calentamiento %u | tipo %u "
           "pico_Hz %.4f | candidato M %.6g piso local %.6g contraste contra piso %.2f dB | "
           "piso_resumen %.6g | análisis %lu us\n",
           banda_lo, banda_hi, r.parcial ? 1u : 0u, static_cast<unsigned>(r.calentamiento),
           static_cast<unsigned>(r.tipo_ruido), r.pico_hz, r.magnitud_candidato,
           r.piso_local, r.contraste_db, r.piso_resumen, (unsigned long)r.tiempo_us);
}

static void imprimir_linea_diag(const ResultadoDiagnostico& r, const ResumenAdc* adc,
                                uint32_t desbordes, uint32_t overruns, uint32_t saturaciones)
{
    printf("DIAG | banda %g-%g Hz | tipo %u %s", banda_lo, banda_hi,
           static_cast<unsigned>(r.tipo_ruido), r.tipo_ruido == 1 ? "tonal" : "ninguno");
    if (r.tipo_ruido == 1) {
        printf(" | pico %.1f Hz", r.pico_hz);
        if (r.contraste_db >= 0.0f) printf(" | contraste %.1f dB", r.contraste_db);
        else printf(" | contraste --");
    } else {
        printf(" | pico -- | contraste --");
    }
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
    printf(">> comando no reconocido. Comandos: banda <lo> <hi>, estado, vista diag|todo\n");
}

static void comando_consola(const char* linea)
{
    char comando[16], modo[16], extra;
    float lo, hi;
    if (sscanf(linea, " %15s", comando) != 1) return;
    if (strcmp(comando, "banda") == 0 &&
        sscanf(linea, " %15s %f %f %c", comando, &lo, &hi, &extra) == 3) {
        if (std::isfinite(lo) && std::isfinite(hi) && lo >= 0.0f && lo < hi && hi <= 4000.0f) {
            banda_lo = lo;
            banda_hi = hi;
            diagnostico_banda(lo, hi);
            printf(">> banda protegida: %g-%g Hz\n", lo, hi);
        } else {
            ayuda_consola();
        }
    } else if (strcmp(comando, "vista") == 0 &&
               sscanf(linea, " %15s %15s %c", comando, modo, &extra) == 2 &&
               (strcmp(modo, "diag") == 0 || strcmp(modo, "todo") == 0)) {
        vista = strcmp(modo, "diag") == 0 ? Vista::DIAG : Vista::TODO;
        printf(">> vista: %s\n", vista == Vista::DIAG ? "diag" : "todo");
    } else if (strcmp(comando, "estado") == 0 &&
               sscanf(linea, " %15s %c", comando, &extra) == 1) {
        printf(">> banda protegida: %g-%g Hz\n>> vista: %s\n>> ",
               banda_lo, banda_hi, vista == Vista::DIAG ? "diag" : "todo");
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
static void enviar_bloque(Enlace& e, const uint8_t* datos, size_t l1,
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
    } else {
        // Sin reintento: el audio vencido se descarta. Los sequence ya asignados dejan un
        // salto que el receptor cuenta como pérdida.
        ++e.desbordes_tx;
        const uint32_t escritura = static_cast<uint32_t>(esp_timer_get_time() - t0);
        if (escritura > e.esc_max_us) e.esc_max_us = escritura;
    }
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
    diagnostico_iniciar();
    diagnostico_banda(banda_lo, banda_hi);
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0, 1024, 4096, 0, nullptr, 0));
    // Los resúmenes se copian a TX; su transmisión a 115200 no frena el bloque.
    uart_vfs_dev_use_driver(UART_NUM_0);
    printf("Consola: banda <lo> <hi>, estado, vista diag|todo | banda protegida inicial 100 1200 Hz\n");

    // Un único 0x00 en UART1. Si el emisor se reinicia a mitad de un paquete, ese paquete
    // queda cortado sin su 0x00; el receptor juntaría esos restos con el primer paquete de la
    // sesión nueva (sequence 0, bandera 0x0004) y fallaría el CRC. El 0x00 cierra los restos
    // como una trama aparte y el receptor descarta las tramas vacías (resincronización COBS).
    static const uint8_t cero = 0;
    uart_write_bytes(enlace_n2.puerto, &cero, 1);

    if (FUENTE_ENTRADA == Fuente::GENERADOR) {
        printf("Fuente GENERADOR: salida solo INPUT + DIAG por UART1 (GPIO18).\n");

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
               "salida solo INPUT + DIAG por UART1 (GPIO18).\n");
        entrada_adc_iniciar();
    }

    uint64_t first_sample = 0;   // índice de la primera muestra del siguiente bloque
    uint32_t atrasos_temporizador = 0;   // solo GENERADOR, acumulado
    uint32_t bloques = 0;        // bloques procesados (acumulado)

    // Secuencia de UART1; el primer INPUT lleva reinicio.
    uint32_t seq_n2 = 0;
    bool primer_n2 = true;

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
        const auto& diagnostico = diagnostico_procesar(x, muestra_inicial);
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
        d.H = HOP;
        d.pico_Hz = diagnostico.pico_hz;
        d.banda_lo = d.banda_hi = -1.0f;
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
        enviar_bloque(enlace_n2, sal_input, cable_input, sal_diag2, cable_diag);

        // El resumen va al final: el printf cae en el tiempo libre del periodo.
        if (v_bloques == BLOQUES_VENTANA) {
            const uint32_t overruns = atrasos_temporizador + enlace_n2.desbordes_tx;
            ContadoresAdc contadores_resumen;
            if (vista == Vista::DIAG) {
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
