#include "grabacion.h"
#include "protocolo.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include "esp_heap_caps.h"

constexpr size_t TAM_PRE_DISPARO = 8 * MUESTRAS_BLOQUE;
constexpr size_t MAX_GRABACION = 188 * MUESTRAS_BLOQUE;
constexpr size_t MARGEN_RAM = 48 * 1024;
constexpr uint32_t MEMORIA = MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT;
constexpr unsigned BLOQUES_IGNORADOS = 16;
constexpr unsigned BLOQUES_MEDIANA = 16;
constexpr unsigned BLOQUES_CALIBRACION = BLOQUES_IGNORADOS + BLOQUES_MEDIANA;
constexpr float FONDO_MINIMO = 0.00001f;
constexpr size_t MAX_PICOS_DIAGNOSTICO = 256;

static uint8_t pre_disparo[TAM_PRE_DISPARO];
static uint8_t* audio = nullptr;
static size_t capacidad = 0, grabados = 0, posicion = 0;
static size_t siguiente_pre = 0, cantidad_pre = 0;
static EstadoGrabacion estado = EstadoGrabacion::ESPERANDO;
static float ultima_rms = 0.0f, fondo = 0.0f, umbral = 3.0f;
static float rms_calibracion[BLOQUES_MEDIANA];
static unsigned bloques_calibracion = 0, activos = 0, silenciosos = 0;
static bool calibracion_pendiente = false;
static DiagnosticoGrabacion diagnostico;
static unsigned sugerencias[6][4] = {};
static float picos[4][MAX_PICOS_DIAGNOSTICO];
static size_t cantidad_picos[4] = {};

static void limpiar_diagnostico()
{
    diagnostico = {};
    for (auto& tipos : sugerencias) {
        for (unsigned& cantidad : tipos) cantidad = 0;
    }
    for (size_t& cantidad : cantidad_picos) cantidad = 0;
}

static void finalizar_diagnostico()
{
    unsigned mejor = 0;
    uint8_t mejor_tipo = 0;
    uint8_t mejor_filtro = 0;
    // Votar por filtro sumando todos los tipos. En empate gana el menor ID.
    for (uint8_t filtro = 1; filtro <= 3; ++filtro) {
        unsigned total = 0;
        for (uint8_t tipo = 0; tipo < 6; ++tipo) total += sugerencias[tipo][filtro];
        if (total > mejor) {
            mejor = total;
            mejor_filtro = filtro;
        }
    }
    if (mejor == 0) return;
    unsigned mejor_cantidad_tipo = 0;
    for (uint8_t tipo = 0; tipo < 6; ++tipo) {
        if (sugerencias[tipo][mejor_filtro] > mejor_cantidad_tipo) {
            mejor_cantidad_tipo = sugerencias[tipo][mejor_filtro];
            mejor_tipo = tipo;
        }
    }
    diagnostico.tipo_ruido = mejor_tipo;
    diagnostico.filtro_n2 = mejor_filtro;
    if (mejor_filtro == 2 || mejor_filtro == 3) {
        const size_t cantidad = cantidad_picos[mejor_filtro];
        if (cantidad == 0) return;
        std::sort(picos[mejor_filtro], picos[mejor_filtro] + cantidad);
        diagnostico.pico_hz = picos[mejor_filtro][cantidad / 2];
        if (cantidad % 2 == 0) {
            diagnostico.pico_hz = (picos[mejor_filtro][cantidad / 2 - 1] +
                                   picos[mejor_filtro][cantidad / 2]) / 2.0f;
        }
    }
}

// G.711 mu-law: PCM con signo de 16 bits, sesgo 132 y ocho segmentos.
static uint8_t codificar(float muestra)
{
    if (!std::isfinite(muestra)) muestra = 0.0f;
    if (muestra < -1.0f) muestra = -1.0f;
    if (muestra > 1.0f) muestra = 1.0f;
    int pcm = static_cast<int>(roundf(muestra * 32767.0f));
    const unsigned signo = pcm < 0 ? 0x80u : 0u;
    if (pcm < 0) pcm = -pcm;
    if (pcm > 32635) pcm = 32635;
    pcm += 132;
    unsigned segmento = 0;
    for (int limite = 0x100; segmento < 7 && pcm >= limite; limite <<= 1) ++segmento;
    const unsigned mantisa = (static_cast<unsigned>(pcm) >> (segmento + 3)) & 15u;
    return static_cast<uint8_t>(~(signo | (segmento << 4) | mantisa));
}

static float decodificar(uint8_t codigo)
{
    const unsigned valor = static_cast<uint8_t>(~codigo);
    const int magnitud = static_cast<int>(((valor & 15u) * 8u + 132u)
                                          << ((valor >> 4) & 7u)) - 132;
    return ((valor & 0x80u) ? -magnitud : magnitud) / 32768.0f;
}

static void limpiar_pre()
{
    siguiente_pre = cantidad_pre = 0;
    activos = silenciosos = 0;
}

static void iniciar_calibracion()
{
    estado = EstadoGrabacion::ESPERANDO;
    grabados = posicion = 0;
    fondo = 0.0f;
    bloques_calibracion = 0;
    calibracion_pendiente = false;
    limpiar_pre();
    limpiar_diagnostico();
    printf("Grabación: esperando, calibrando en silencio\n");
}

void grabacion_calibrar()
{
    if (estado == EstadoGrabacion::REPRODUCIENDO) {
        printf("Grabación: calibrar no disponible mientras reproduce\n");
        return;
    }
    iniciar_calibracion();
}

void grabacion_nueva_sesion()
{
    // No medir el sonido del parlante ni interrumpir el audio ya encolado.
    if (estado == EstadoGrabacion::REPRODUCIENDO) {
        calibracion_pendiente = true;
        return;
    }
    iniciar_calibracion();
}

void grabacion_iniciar()
{
    const size_t libre = heap_caps_get_free_size(MEMORIA);
    const size_t mayor = heap_caps_get_largest_free_block(MEMORIA);
    printf("RAM interna libre %lu B | bloque libre más grande %lu B\n",
           (unsigned long)libre, (unsigned long)mayor);
    size_t disponible = libre > MARGEN_RAM ? libre - MARGEN_RAM : 0;
    if (disponible > mayor) disponible = mayor;
    if (disponible > MAX_GRABACION) disponible = MAX_GRABACION;
    disponible -= disponible % MUESTRAS_BLOQUE;
    // El mayor bloque puede incluir el coste del asignador; reducir si no cabe.
    while (disponible >= TAM_PRE_DISPARO) {
        audio = static_cast<uint8_t*>(heap_caps_malloc(disponible, MEMORIA));
        if (audio && heap_caps_get_free_size(MEMORIA) >= MARGEN_RAM) {
            capacidad = disponible;
            break;
        }
        if (audio) heap_caps_free(audio);
        audio = nullptr;
        disponible -= MUESTRAS_BLOQUE;
    }
    printf("Grabación: capacidad %.3f s (%lu B), pre-disparo 0.512 s incluido\n",
           capacidad / 8000.0, (unsigned long)capacidad);
    if (!audio) printf("Grabación: deshabilitada por falta de RAM; DAC en silencio\n");
    printf("Grabación: esperando\n");
}

static void terminar_grabacion()
{
    finalizar_diagnostico();
    estado = EstadoGrabacion::LISTA;
    limpiar_pre();
    printf("Grabación: lista %.3f s | diagnóstico tipo %u filtro %u pico %.6g Hz\n",
           grabados / 8000.0, diagnostico.tipo_ruido, diagnostico.filtro_n2,
           diagnostico.pico_hz);
}

void grabacion_input(const uint8_t* datos)
{
    float energia = 0.0f;
    for (size_t k = 0; k < MUESTRAS_BLOQUE; ++k) {
        float x = get_f32(datos + 4 * k);
        if (!std::isfinite(x)) x = 0.0f;
        energia += x * x;
    }
    ultima_rms = std::sqrt(energia / MUESTRAS_BLOQUE);
    if (estado == EstadoGrabacion::REPRODUCIENDO) return;
    if (bloques_calibracion < BLOQUES_CALIBRACION) {
        if (bloques_calibracion >= BLOQUES_IGNORADOS) {
            rms_calibracion[bloques_calibracion - BLOQUES_IGNORADOS] = ultima_rms;
        }
        ++bloques_calibracion;
        if (bloques_calibracion == BLOQUES_CALIBRACION) {
            std::sort(rms_calibracion, rms_calibracion + BLOQUES_MEDIANA);
            fondo = (rms_calibracion[BLOQUES_MEDIANA / 2 - 1]
                     + rms_calibracion[BLOQUES_MEDIANA / 2]) / 2.0f;
            printf("Grabación: fondo calibrado %.6g\n", fondo);
        }
        return;
    }
    const bool actividad = ultima_rms > umbral * (fondo > FONDO_MINIMO ? fondo : FONDO_MINIMO);
    if (estado == EstadoGrabacion::ESPERANDO && ultima_rms < 1.5f * fondo) {
        fondo += 0.01f * (ultima_rms - fondo);
    }
    if (!audio) return;
    if (estado == EstadoGrabacion::GRABANDO) {
        for (size_t k = 0; k < MUESTRAS_BLOQUE; ++k) audio[grabados++] = codificar(get_f32(datos + 4 * k));
        silenciosos = actividad ? 0 : silenciosos + 1;
        if (silenciosos >= 16 || grabados == capacidad) terminar_grabacion();
        return;
    }
    // Incluir los dos bloques de confirmación una sola vez, dentro del circular.
    for (size_t k = 0; k < MUESTRAS_BLOQUE; ++k) {
        pre_disparo[siguiente_pre] = codificar(get_f32(datos + 4 * k));
        siguiente_pre = (siguiente_pre + 1) % TAM_PRE_DISPARO;
    }
    if (cantidad_pre < TAM_PRE_DISPARO) cantidad_pre += MUESTRAS_BLOQUE;
    activos = actividad ? activos + 1 : 0;
    if (activos < 2) return;
    grabados = cantidad_pre;
    const size_t principio = (siguiente_pre + TAM_PRE_DISPARO - cantidad_pre) % TAM_PRE_DISPARO;
    const size_t primera = cantidad_pre < TAM_PRE_DISPARO - principio ? cantidad_pre : TAM_PRE_DISPARO - principio;
    memcpy(audio, pre_disparo + principio, primera);
    memcpy(audio + primera, pre_disparo, cantidad_pre - primera);
    silenciosos = 0;
    limpiar_diagnostico();
    estado = EstadoGrabacion::GRABANDO;
    printf("Grabación: grabando\n");
    if (grabados == capacidad) terminar_grabacion();
}

void grabacion_diag(const uint8_t* datos)
{
    if (estado != EstadoGrabacion::GRABANDO) return;
    const uint8_t tipo = datos[10];
    const uint8_t filtro = datos[11];
    if (tipo > 5 || filtro < 1 || filtro > 3) return;
    ++sugerencias[tipo][filtro];
    const float pico = get_f32(datos + 12);
    if ((filtro == 2 || filtro == 3) && std::isfinite(pico) &&
        pico >= 100.0f && pico <= 3000.0f &&
        cantidad_picos[filtro] < MAX_PICOS_DIAGNOSTICO) {
        picos[filtro][cantidad_picos[filtro]++] = pico;
    }
}

bool grabacion_reproducir(const char* modo)
{
    if (estado != EstadoGrabacion::LISTA) return false;
    posicion = 0;
    estado = EstadoGrabacion::REPRODUCIENDO;
    printf("Grabación: reproduciendo %.3f s en modo %s\n", grabados / 8000.0, modo);
    return true;
}

bool grabacion_leer_bloque(float* muestras, bool& ultimo)
{
    if (estado != EstadoGrabacion::REPRODUCIENDO || posicion == grabados) return false;
    for (size_t k = 0; k < MUESTRAS_BLOQUE; ++k) muestras[k] = decodificar(audio[posicion++]);
    ultimo = posicion == grabados;
    return true;
}

void grabacion_finalizar_reproduccion()
{
    if (calibracion_pendiente) {
        iniciar_calibracion();
        return;
    }
    estado = EstadoGrabacion::LISTA;
    limpiar_pre();
    printf("Grabación: lista %.3f s\n", grabados / 8000.0);
}

void grabacion_cambiar_umbral(float factor) { umbral = factor; }
EstadoGrabacion grabacion_estado() { return estado; }
float grabacion_rms() { return ultima_rms; }
float grabacion_fondo() { return fondo; }
double grabacion_duracion_s() { return grabados / 8000.0; }
double grabacion_posicion_s() { return posicion / 8000.0; }

const char* grabacion_nombre_estado()
{
    static const char* const nombres[] = {"ESPERANDO", "GRABANDO", "LISTA", "REPRODUCIENDO"};
    return nombres[static_cast<unsigned>(estado)];
}

void grabacion_imprimir()
{
    printf("Grabación: %s | duración %.3f s | capacidad %.3f s | ruido de fondo %.6g | "
           "umbral %.3g | diagnóstico tipo %u filtro %u pico %.6g Hz\n",
           grabacion_nombre_estado(), grabados / 8000.0, capacidad / 8000.0, fondo, umbral,
           diagnostico.tipo_ruido, diagnostico.filtro_n2, diagnostico.pico_hz);
}

const DiagnosticoGrabacion& grabacion_diagnostico()
{
    return diagnostico;
}
