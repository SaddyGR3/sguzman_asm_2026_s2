#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <cstring>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_err.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "driver/gpio.h"
#include "driver/uart.h"
#include "dsps_fft2r.h"
#include "generador.h"
#include "protocolo.h"

// true: lazo de prueba con puentes GPIO18->GPIO19 y GPIO17->GPIO16 en la misma placa.
// false: para la PC, no se copia al anillo, no se lee RX y no se compara.
constexpr bool PRUEBA_LAZO = false;

constexpr int N_FFT = 1024;      // dos bloques de 512
constexpr int EXCLUSION = 12;    // bins que separan un pico de otro

// 512 muestras a 8 kHz = 64 ms: el temporizador marca el ritmo de un bloque.
constexpr uint64_t PERIODO_US = 64000;
constexpr uint32_t BLOQUES_VENTANA = 16;   // un resumen cada ~1.024 s

constexpr int BAUDIOS = 921600;
constexpr size_t TAM_ANILLO = 16384;       // potencia de 2: el índice se envuelve con una máscara
constexpr size_t MARGEN_TX = 64;

static TaskHandle_t tarea_principal = nullptr;   // la lee el callback del temporizador

// El callback corre en la tarea del temporizador (ESP_TIMER_TASK) y no en una
// interrupción, por eso se usa xTaskNotifyGive() y no la versión FromISR.
static void aviso_bloque(void*)
{
    xTaskNotifyGive(tarea_principal);
}

static float x[HOP];                    // señal contaminada: x = s + i
static float s_util[HOP];               // señal útil (referencia limpia)
static float i_interf[HOP];             // interferencia
static float xs[2 * HOP];               // x y s intercalados para INPUT_REF
static float muestras[N_FFT];
static float fft_buf[2 * N_FFT];        // real e imaginario intercalados
static float mag_db[N_FFT / 2 + 1];

// FFT de 1024 muestras de x = s + i, generadas directamente sobre los generadores
// (avanzan su fase).
static void analizar(Generador& gen_s, Generador& gen_i)
{
    for (int h = 0; h < 2; ++h) {
        gen_s.generar(s_util, HOP);
        gen_i.generar(i_interf, HOP);
        for (int k = 0; k < HOP; ++k) muestras[h * HOP + k] = s_util[k] + i_interf[k];
    }

    // Ventana de Hann periódica y parte imaginaria en cero.
    constexpr float DOS_PI = 6.283185307f;
    for (int n = 0; n < N_FFT; ++n) {
        const float w = 0.5f - 0.5f * cosf(DOS_PI * n / N_FFT);
        fft_buf[2 * n] = muestras[n] * w;
        fft_buf[2 * n + 1] = 0.0f;
    }

    dsps_fft2r_fc32(fft_buf, N_FFT);
    dsps_bit_rev_fc32(fft_buf, N_FFT);   // deja los bins en orden natural

    // Magnitud en dB y máximo global, de 0 a N/2.
    float max_db = -200.0f;
    for (int k = 0; k <= N_FFT / 2; ++k) {
        const float re = fft_buf[2 * k];
        const float im = fft_buf[2 * k + 1];
        mag_db[k] = 10.0f * log10f(re * re + im * im + 1e-20f);
        max_db = fmaxf(max_db, mag_db[k]);
    }

    // Los 4 máximos locales más altos, separados al menos EXCLUSION bins.
    int picos[4] = {-1, -1, -1, -1};
    for (int j = 0; j < 4; ++j) {
        int mejor = -1;
        for (int k = 1; k < N_FFT / 2; ++k) {
            const bool local = mag_db[k] >= mag_db[k - 1] && mag_db[k] >= mag_db[k + 1];
            bool usado = false;
            for (int i = 0; i < j; ++i) {
                if (abs(k - picos[i]) <= EXCLUSION) usado = true;
            }
            if (local && !usado && (mejor < 0 || mag_db[k] > mag_db[mejor])) mejor = k;
        }
        picos[j] = mejor;
    }

    printf("picos:");
    for (int j = 0; j < 4; ++j) {
        if (picos[j] < 0) continue;
        printf("  %.1f Hz (%.1f dB)", picos[j] * FS_HZ / N_FFT, mag_db[picos[j]] - max_db);
    }
    printf("\n");
}

// Búferes de paquetes (estáticos: la pila de app_main es pequeña).
static uint8_t trabajo[TAM_TRABAJO];          // cabecera + datos + CRC, antes de COBS
static uint8_t sal_input[CABLE_INPUT];
static uint8_t sal_ref[CABLE_INPUT_REF];
static uint8_t sal_diag2[CABLE_DIAG];         // DIAG hacia el nodo 2
static uint8_t sal_diag3[CABLE_DIAG];         // DIAG hacia el nodo 3
static uint8_t diag64[TAM_DIAG];
static uint32_t session_id = 0;

// Un enlace UART hacia otro nodo, con sus contadores y, para el lazo, el anillo
// con una copia de lo enviado.
struct Enlace {
    const char* nombre;
    uart_port_t puerto;
    uint64_t enviados = 0;        // bytes escritos en el búfer del driver (acumulado)
    uint32_t desbordes_tx = 0;    // bloques descartados por falta de espacio (acumulado)
    uint32_t esc_max_us = 0;      // máximo tiempo de escritura de la ventana
    // Lazo de prueba.
    uint8_t anillo[TAM_ANILLO];
    uint32_t pos_esc = 0;         // dónde se copia el siguiente byte enviado
    uint32_t pos_lect = 0;        // contra qué byte se compara el siguiente recibido
    uint64_t recibidos = 0;
    uint32_t diferencias = 0;
    bool desincronizado = false;

    Enlace(const char* n, uart_port_t p) : nombre(n), puerto(p) {}   // el anillo queda en .bss
};

static Enlace enlace_n2("N2", UART_NUM_1);
static Enlace enlace_n3("N3", UART_NUM_2);
static uint8_t buf_rx[1024];      // búfer de lectura compartido por los dos enlaces

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
    // Pull-up en RX, después de uart_set_pin: con PRUEBA_LAZO = false los RX quedan sin
    // conectar, y sin pull-up captan ruido que la UART interpreta como bytes y errores.
    ESP_ERROR_CHECK(gpio_set_pull_mode(static_cast<gpio_num_t>(rx), GPIO_PULLUP_ONLY));
    ESP_ERROR_CHECK(uart_driver_install(puerto, buf_rx_tam, buf_tx, 0, NULL, 0));
}

// Copia al anillo lo que se acaba de escribir, en el mismo orden.
static void copiar_al_anillo(Enlace& e, const uint8_t* datos, size_t n)
{
    for (size_t k = 0; k < n; ++k) {
        e.anillo[e.pos_esc] = datos[k];
        e.pos_esc = (e.pos_esc + 1) & (TAM_ANILLO - 1);
    }
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
        uart_write_bytes(e.puerto, datos, l1);
        uart_write_bytes(e.puerto, diag, l2);
        const int64_t t1 = esp_timer_get_time();
        const uint32_t escritura = static_cast<uint32_t>(t1 - t0);
        if (escritura > e.esc_max_us) e.esc_max_us = escritura;
        if (PRUEBA_LAZO) {
            copiar_al_anillo(e, datos, l1);
            copiar_al_anillo(e, diag, l2);
        }
        e.enviados += l1 + l2;
    } else {
        // Sin reintento: el audio vencido se descarta. Los sequence ya asignados dejan un
        // salto que el receptor cuenta como pérdida.
        ++e.desbordes_tx;
        const uint32_t escritura = static_cast<uint32_t>(esp_timer_get_time() - t0);
        if (escritura > e.esc_max_us) e.esc_max_us = escritura;
    }
}

// Lee lo que llegó por RX y lo compara con el anillo. No decodifica nada.
static void leer_lazo(Enlace& e)
{
    if (e.desincronizado) return;
    size_t disponible = 0;
    ESP_ERROR_CHECK(uart_get_buffered_data_len(e.puerto, &disponible));
    while (disponible > 0) {
        // Si lo pendiente supera el anillo, ya se sobrescribieron bytes sin comparar.
        if (static_cast<int64_t>(e.enviados - e.recibidos) > static_cast<int64_t>(TAM_ANILLO)) {
            e.desincronizado = true;
            printf("lazo %s desincronizado: pendientes %llu\n", e.nombre,
                   (unsigned long long)(e.enviados - e.recibidos));
            return;
        }
        const size_t pedir = disponible < sizeof(buf_rx) ? disponible : sizeof(buf_rx);
        const int n = uart_read_bytes(e.puerto, buf_rx, pedir, 0);
        if (n <= 0) break;
        for (int k = 0; k < n; ++k) {
            if (buf_rx[k] != e.anillo[e.pos_lect]) ++e.diferencias;
            e.pos_lect = (e.pos_lect + 1) & (TAM_ANILLO - 1);
        }
        e.recibidos += n;
        disponible -= n;
    }
    if (static_cast<int64_t>(e.enviados - e.recibidos) > static_cast<int64_t>(TAM_ANILLO)) {
        e.desincronizado = true;
        printf("lazo %s desincronizado: pendientes %llu\n", e.nombre,
               (unsigned long long)(e.enviados - e.recibidos));
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

// INPUT_REF hacia el nodo 3: xs ya tiene x[0], s[0], x[1], s[1], ...
static size_t paquete_ref(uint32_t seq, uint16_t flags, uint64_t muestra)
{
    return armar_paquete(TIPO_INPUT_REF, NODO_1, NODO_3, flags | FLAG_REFERENCIA, session_id,
                         seq, muestra, HOP, FORMATO_FLOAT32, 2,
                         reinterpret_cast<const uint8_t*>(xs), TAM_DATOS_INPUT_REF,
                         trabajo, sal_ref);
}

// DIAG ya armado en diag64, hacia el destino indicado.
static size_t paquete_diag(uint8_t dst, uint32_t seq, uint64_t muestra, uint8_t* salida)
{
    return armar_paquete(TIPO_DIAG, NODO_1, dst, 0, session_id, seq, muestra,
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

    // Cabeceras del primer INPUT y del primer INPUT_REF (la cabecera no depende de los datos).
    paquete_input(0, FLAG_REINICIO, 0);
    imprimir_cabecera("INPUT");
    paquete_ref(0, FLAG_REINICIO, 0);
    imprimir_cabecera("INPUT_REF");

    // UART1 -> nodo 2 y UART2 -> nodo 3. El anillo de TX del driver es NOSPLIT con ítem
    // máximo ALIGN4(tamaño/2) - 8: con 8 KB el tope es 4088 B y uart_get_tx_buffer_free_size
    // daría descartes falsos para el bloque de N3 (~4246 B); con 16 KB el tope es 8184 B.
    // En UART1 el INPUT (~2086 B) cabe con 8 KB.
    iniciar_uart(UART_NUM_1, 18, 19, 8192, 8192);
    iniciar_uart(UART_NUM_2, 17, 16, 16384, 8192);
    uint32_t baud1 = 0, baud2 = 0;
    ESP_ERROR_CHECK(uart_get_baudrate(UART_NUM_1, &baud1));
    ESP_ERROR_CHECK(uart_get_baudrate(UART_NUM_2, &baud2));
    printf("UART1 baud real %lu | UART2 baud real %lu\n", (unsigned long)baud1, (unsigned long)baud2);

    // Verificación espectral, una sola vez al arrancar.
    if (dsps_fft2r_init_fc32(NULL, N_FFT) != ESP_OK) {
        printf("Error al iniciar la FFT de ESP-DSP\n");
    } else {
        analizar(gen_s, gen_i);
    }

    // Vacía RX para que el ruido del arranque no cuente en el lazo.
    ESP_ERROR_CHECK(uart_flush_input(UART_NUM_1));
    ESP_ERROR_CHECK(uart_flush_input(UART_NUM_2));

    // Un único 0x00 en cada UART. Si el emisor se reinicia a mitad de un paquete, ese paquete
    // queda cortado sin su 0x00; el receptor juntaría esos restos con el primer paquete de la
    // sesión nueva (sequence 0, bandera 0x0004) y fallaría el CRC. El 0x00 cierra los restos
    // como una trama aparte y el receptor descarta las tramas vacías (resincronización COBS).
    static const uint8_t cero = 0;
    uart_write_bytes(enlace_n2.puerto, &cero, 1);
    uart_write_bytes(enlace_n3.puerto, &cero, 1);
    if (PRUEBA_LAZO) {
        // Para que el lazo siga dando 0 diferencias, el 0x00 también entra al anillo.
        copiar_al_anillo(enlace_n2, &cero, 1);
        copiar_al_anillo(enlace_n3, &cero, 1);
        enlace_n2.enviados += 1;
        enlace_n3.enviados += 1;
    }

    // Temporizador periódico: cada 64 ms avisa a esta tarea que toca un bloque.
    tarea_principal = xTaskGetCurrentTaskHandle();
    esp_timer_create_args_t args = {};
    args.callback = aviso_bloque;
    args.dispatch_method = ESP_TIMER_TASK;
    args.name = "bloque";
    esp_timer_handle_t temporizador = nullptr;
    ESP_ERROR_CHECK(esp_timer_create(&args, &temporizador));
    ESP_ERROR_CHECK(esp_timer_start_periodic(temporizador, PERIODO_US));

    uint64_t first_sample = 0;   // índice de la primera muestra del siguiente bloque
    uint32_t overruns = 0;       // bloques que se retrasaron (acumulado)
    uint32_t bloques = 0;        // bloques generados (acumulado)

    // Un contador de secuencia por enlace; el primer paquete de cada enlace lleva reinicio.
    uint32_t seq_n2 = 0;
    uint32_t seq_n3 = 0;
    bool primer_n2 = true;
    bool primer_n3 = true;

    // Valores de la ventana de resumen; se reinician al imprimir.
    uint32_t v_bloques = 0;
    uint32_t v_periodos = 0;
    uint32_t v_per_min = 0xFFFFFFFF;
    uint32_t v_per_max = 0;
    uint64_t v_per_suma = 0;
    uint32_t v_gen_max = 0;
    uint32_t v_emp_max = 0;
    size_t cable_input = 0, cable_ref = 0, cable_diag = 0, cable_diag3 = 0;

    int64_t inicio_anterior = -1;   // la primera iteración no tiene periodo

    for (;;) {
        // Espera el aviso. Si n > 1, llegaron avisos mientras el bloque anterior
        // seguía en proceso: cada uno de más es un overrun.
        const uint32_t n = ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        if (n > 1) overruns += n - 1;

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

        // Generadores continuos: la fase pasa de un bloque al siguiente.
        gen_s.generar(s_util, HOP);
        gen_i.generar(i_interf, HOP);
        for (int k = 0; k < HOP; ++k) x[k] = s_util[k] + i_interf[k];
        const int64_t fin_gen = esp_timer_get_time();
        const uint32_t duracion = static_cast<uint32_t>(fin_gen - inicio);
        if (duracion > v_gen_max) v_gen_max = duracion;

        first_sample += HOP;
        ++bloques;
        ++v_bloques;

        // Empaquetado: energía, intercalado de xs y los 4 paquetes.
        float energia = 0.0f;
        for (int k = 0; k < HOP; ++k) {
            energia += x[k] * x[k];
            xs[2 * k] = x[k];
            xs[2 * k + 1] = s_util[k];
        }

        Diag d;
        d.fs = static_cast<uint32_t>(FS_HZ);
        d.N = N_FFT;
        d.H = HOP;
        d.pico_Hz = d.banda_lo = d.banda_hi = d.piso_resumen = -1.0f;
        d.energia = energia;
        d.tiempo_us = duracion;
        d.overruns = overruns;
        d.inicio_ventana = muestra_inicial;
        armar_diag(d, diag64);

        // Enlace N1 -> N2: INPUT y DIAG.
        cable_input = paquete_input(seq_n2++, primer_n2 ? FLAG_REINICIO : 0, muestra_inicial);
        primer_n2 = false;
        cable_diag = paquete_diag(NODO_2, seq_n2++, muestra_inicial, sal_diag2);

        // Enlace N1 -> N3: INPUT_REF y DIAG.
        cable_ref = paquete_ref(seq_n3++, primer_n3 ? FLAG_REINICIO : 0, muestra_inicial);
        primer_n3 = false;
        cable_diag3 = paquete_diag(NODO_3, seq_n3++, muestra_inicial, sal_diag3);

        const uint32_t empaquetado = static_cast<uint32_t>(esp_timer_get_time() - fin_gen);
        if (empaquetado > v_emp_max) v_emp_max = empaquetado;

        // Envío por UART: datos y después DIAG, un bloque por enlace.
        enviar_bloque(enlace_n2, sal_input, cable_input, sal_diag2, cable_diag);
        enviar_bloque(enlace_n3, sal_ref, cable_ref, sal_diag3, cable_diag3);

        // Lazo de prueba: lee RX al final, así el envío (con plazo) va primero.
        if (PRUEBA_LAZO) {
            leer_lazo(enlace_n2);
            leer_lazo(enlace_n3);
        }

        // El resumen va al final: el printf cae en el tiempo libre del periodo.
        if (v_bloques == BLOQUES_VENTANA) {
            const uint32_t prom = v_periodos ? static_cast<uint32_t>(v_per_suma / v_periodos) : 0;
            printf("bloques %lu | first_sample %llu | periodo prom %lu us (min %lu, max %lu) | generar max %lu us | empaquetar max %lu us | cable INPUT %lu REF %lu DIAG %lu | pila libre %lu B | overruns %lu\n",
                   (unsigned long)bloques, (unsigned long long)first_sample,
                   (unsigned long)prom, (unsigned long)v_per_min, (unsigned long)v_per_max,
                   (unsigned long)v_gen_max, (unsigned long)v_emp_max,
                   (unsigned long)cable_input, (unsigned long)cable_ref, (unsigned long)cable_diag,
                   (unsigned long)uxTaskGetStackHighWaterMark(NULL),
                   (unsigned long)overruns);
            printf("tx N2 %llu B (esc max %lu us, desb %lu) | tx N3 %llu B (esc max %lu us, desb %lu)\n",
                   (unsigned long long)enlace_n2.enviados, (unsigned long)enlace_n2.esc_max_us,
                   (unsigned long)enlace_n2.desbordes_tx,
                   (unsigned long long)enlace_n3.enviados, (unsigned long)enlace_n3.esc_max_us,
                   (unsigned long)enlace_n3.desbordes_tx);
            if (PRUEBA_LAZO) {
                printf("lazo N2: rx %llu dif %lu pend %lld | N3: rx %llu dif %lu pend %lld\n",
                       (unsigned long long)enlace_n2.recibidos, (unsigned long)enlace_n2.diferencias,
                       (long long)(enlace_n2.enviados - enlace_n2.recibidos),
                       (unsigned long long)enlace_n3.recibidos, (unsigned long)enlace_n3.diferencias,
                       (long long)(enlace_n3.enviados - enlace_n3.recibidos));
            }
            enlace_n2.esc_max_us = 0;
            enlace_n3.esc_max_us = 0;
            v_bloques = 0;
            v_periodos = 0;
            v_per_min = 0xFFFFFFFF;
            v_per_max = 0;
            v_per_suma = 0;
            v_gen_max = 0;
            v_emp_max = 0;
        }
    }
}
