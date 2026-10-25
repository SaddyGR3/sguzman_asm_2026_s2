#include <cstdio>
#include <cstdlib>
#include <cmath>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_err.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "dsps_fft2r.h"
#include "generador.h"
#include "protocolo.h"

constexpr int N_FFT = 1024;      // dos bloques de 512
constexpr int EXCLUSION = 12;    // bins que separan un pico de otro

// 512 muestras a 8 kHz = 64 ms: el temporizador marca el ritmo de un bloque.
constexpr uint64_t PERIODO_US = 64000;
constexpr uint32_t BLOQUES_VENTANA = 16;   // un resumen cada ~1.024 s

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

    // Verificación espectral, una sola vez al arrancar.
    if (dsps_fft2r_init_fc32(NULL, N_FFT) != ESP_OK) {
        printf("Error al iniciar la FFT de ESP-DSP\n");
    } else {
        analizar(gen_s, gen_i);
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
    size_t cable_input = 0, cable_ref = 0, cable_diag = 0;

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
        paquete_diag(NODO_3, seq_n3++, muestra_inicial, sal_diag3);

        const uint32_t empaquetado = static_cast<uint32_t>(esp_timer_get_time() - fin_gen);
        if (empaquetado > v_emp_max) v_emp_max = empaquetado;

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
