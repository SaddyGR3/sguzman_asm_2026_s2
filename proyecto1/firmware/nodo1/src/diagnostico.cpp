#include "diagnostico.h"
#include "espectro.h"
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include "esp_timer.h"

namespace {
constexpr int N = 1024, H = 512;
constexpr float FS = 8000.0f, ANALISIS_LO = 100.0f, ANALISIS_HI = 3000.0f;
constexpr float EPSILON = 1e-12f;
constexpr int CONFIRMACIONES = 3, RETIRADA = 3, TOLERANCIA_BINS = 1;
constexpr int ARMONICOS_MINIMOS = 3, HUECO_MAXIMO = 2, ANCHURA_MINIMA = 8;
constexpr int HISTORIA_IMPULSIVA = 3, IMPULSOS_MINIMOS = 2;

struct Pico {
    int bin = -1;
    float magnitud = -1.0f;
    float piso = -1.0f;
};

struct Familia {
    int armonicos = 0;
    double suma = 0.0;
    Pico fuerte;
};

struct Region {
    int inicio = -1, fin = -1;
    double energia = 0.0;
};

struct EstadoTonal {
    int anterior = -1, entradas = 0, ausencias = 0;
    Pico publicado;
};

struct EstadoRed {
    int entradas = 0, ausencias = 0;
    Familia publicada;
};

struct EstadoAncha {
    int entradas = 0, ausencias = 0;
    bool publicada = false;
};

struct EstadoLimitada {
    int entradas = 0, ausencias = 0;
    Region anterior, publicada;
};

static float historial[N];
static float magnitudes[N / 2 + 1], piso[N / 2 + 1];
static float trabajo_mediana[N / 2 + 1];
static bool picos_50[N / 2 + 1], picos_60[N / 2 + 1];
static bool mitades_validas[2];
static bool impulsos[HISTORIA_IMPULSIVA];
static int mitad = 0, posicion_impulso = 0, completos = 0;
static bool primera = true;
static float banda_lo = 100.0f, banda_hi = 1200.0f;
static UmbralesDiagnostico umbrales;
static EstadoTonal tonal;
static EstadoRed red_50, red_60;
static EstadoAncha ancha;
static EstadoLimitada limitada;
static ResultadoDiagnostico resultado;

static void reiniciar_clasificacion()
{
    tonal = EstadoTonal{};
    red_50 = red_60 = EstadoRed{};
    ancha = EstadoAncha{};
    limitada = EstadoLimitada{};
    memset(impulsos, 0, sizeof(impulsos));
    posicion_impulso = completos = 0;
    resultado.tipo_ruido = resultado.filtro_n2 = resultado.metodo = 0;
    resultado.pico_hz = resultado.banda_detectada_lo = resultado.banda_detectada_hi = -1.0f;
    resultado.magnitud_candidato = resultado.piso_local = resultado.contraste_db = -1.0f;
    resultado.contraste_publicado_db = -1.0f;
    resultado.calentamiento = 1;
}

static bool protegido(int bin)
{
    const float hz = espectro_bin_a_hz(bin, FS);
    return hz >= banda_lo && hz <= banda_hi;
}

static bool maximo(int bin, float umbral)
{
    return !protegido(bin) && magnitudes[bin] >= magnitudes[bin - 1] &&
        magnitudes[bin] >= magnitudes[bin + 1] &&
        magnitudes[bin] > umbral * fmaxf(piso[bin], EPSILON);
}

static Pico obtener_pico(int bin)
{
    Pico pico;
    pico.bin = bin;
    pico.magnitud = magnitudes[bin];
    pico.piso = piso[bin];
    return pico;
}

static float contraste(const Pico& pico)
{
    // La razón se forma en double para evitar desbordes con magnitudes extremas.
    const double razon = static_cast<double>(fmaxf(pico.magnitud, EPSILON)) / fmaxf(pico.piso, EPSILON);
    return static_cast<float>(20.0 * log10(razon));
}

// El RMS y la cresta pertenecen al bloque actual de 512 muestras. Una mitad
// inválida se sustituye completa por ceros solo en la copia de análisis.
static bool incorporar_bloque(const float* x)
{
    double cuadrados = 0.0;
    float absoluto = 0.0f;
    bool valido = true;
    for (int j = 0; j < H; ++j) {
        if (!std::isfinite(x[j])) {
            valido = false;
            continue;
        }
        cuadrados += static_cast<double>(x[j]) * x[j];
        absoluto = fmaxf(absoluto, fabsf(x[j]));
    }
    float* destino = historial + mitad * H;
    if (valido) memcpy(destino, x, H * sizeof(float));
    else memset(destino, 0, H * sizeof(float));
    mitades_validas[mitad] = valido;
    const float rms = valido ? static_cast<float>(sqrt(cuadrados / H)) : 0.0f;
    resultado.factor_cresta = rms > DIAG_RMS_MINIMO ? absoluto / rms : 0.0f;
    return valido && rms > DIAG_RMS_MINIMO;
}

static float referencia_global(int desde, int hasta)
{
    const int cantidad = hasta - desde + 1;
    for (int j = 0; j < cantidad; ++j) trabajo_mediana[j] = piso[desde + j];
    // std::sort trabaja sobre el arreglo estático, sin reservar memoria dinámica.
    std::sort(trabajo_mediana, trabajo_mediana + cantidad);
    const int centro = cantidad / 2;
    return cantidad % 2 ? trabajo_mediana[centro] :
        0.5f * trabajo_mediana[centro - 1] + 0.5f * trabajo_mediana[centro];
}

static Familia buscar_familia(int base, int desde, int hasta, bool* usados)
{
    Familia familia;
    memset(usados, 0, (N / 2 + 1) * sizeof(bool));
    for (int multiplo = static_cast<int>(ceilf(ANALISIS_LO / base));
         multiplo * base <= ANALISIS_HI; ++multiplo) {
        const float centro = espectro_hz_a_bin(static_cast<float>(multiplo * base), FS);
        const int cercano = static_cast<int>(lroundf(centro));
        int elegido = -1;
        for (int k = cercano - TOLERANCIA_BINS; k <= cercano + TOLERANCIA_BINS; ++k) {
            if (k < desde || k > hasta || usados[k] ||
                fabsf(k - centro) > TOLERANCIA_BINS || !maximo(k, umbrales.red)) continue;
            if (elegido < 0 || magnitudes[k] > magnitudes[elegido]) elegido = k;
        }
        // Un máximo por armónico y cada máximo una sola vez por familia.
        if (elegido < 0) continue;
        usados[elegido] = true;
        ++familia.armonicos;
        familia.suma += magnitudes[elegido];
        if (familia.fuerte.bin < 0 || magnitudes[elegido] > familia.fuerte.magnitud)
            familia.fuerte = obtener_pico(elegido);
    }
    return familia;
}

static Pico buscar_tonal(int desde, int hasta, const Familia& f50, const Familia& f60)
{
    Pico candidato;
    for (int k = desde; k <= hasta; ++k) {
        if ((f50.armonicos >= ARMONICOS_MINIMOS && picos_50[k]) ||
            (f60.armonicos >= ARMONICOS_MINIMOS && picos_60[k])) continue;
        if (maximo(k, umbrales.tonal) && magnitudes[k] > candidato.magnitud)
            candidato = obtener_pico(k);
    }
    return candidato;
}

static void persistir_tonal(const Pico& candidato)
{
    if (candidato.bin >= 0) {
        tonal.entradas = tonal.anterior >= 0 && abs(candidato.bin - tonal.anterior) <= TOLERANCIA_BINS
            ? std::min(tonal.entradas + 1, CONFIRMACIONES) : 1;
    } else tonal.entradas = 0;
    tonal.anterior = candidato.bin;
    if (tonal.publicado.bin >= 0) {
        if (candidato.bin >= 0 && abs(candidato.bin - tonal.publicado.bin) <= TOLERANCIA_BINS) {
            tonal.publicado = candidato;
            tonal.ausencias = 0;
        } else if (++tonal.ausencias >= RETIRADA) {
            tonal.publicado = Pico{};
            tonal.ausencias = 0;
        }
    }
    if (tonal.publicado.bin < 0 && tonal.entradas >= CONFIRMACIONES) {
        tonal.publicado = candidato;
        tonal.ausencias = 0;
    }
}

static void persistir_red(EstadoRed& estado, const Familia& candidata)
{
    if (candidata.armonicos >= ARMONICOS_MINIMOS) {
        estado.entradas = std::min(estado.entradas + 1, CONFIRMACIONES);
        estado.ausencias = 0;
        if (estado.entradas >= CONFIRMACIONES || estado.publicada.armonicos >= ARMONICOS_MINIMOS)
            estado.publicada = candidata;
    } else {
        estado.entradas = 0;
        if (estado.publicada.armonicos >= ARMONICOS_MINIMOS && ++estado.ausencias >= RETIRADA) {
            estado.publicada = Familia{};
            estado.ausencias = 0;
        }
    }
}

static bool detectar_ancha(int desde, int hasta, float referencia)
{
    int ocupados = 0;
    double suma = 0.0, logaritmos = 0.0;
    for (int k = desde; k <= hasta; ++k) {
        if (piso[k] > DIAG_FRACCION_PISO * referencia) ++ocupados;
        suma += piso[k];
        logaritmos += log(fmaxf(piso[k], EPSILON));
    }
    const int cantidad = hasta - desde + 1;
    const double media = suma / cantidad;
    const double planitud = exp(logaritmos / cantidad) / std::max(media, static_cast<double>(EPSILON));
    return ocupados >= DIAG_OCUPACION_MINIMA * cantidad && planitud >= DIAG_PLANITUD_MINIMA;
}

static void elegir_region(const Region& candidata, Region& mejor)
{
    // El recorrido ascendente conserva la menor frecuencia inicial en un empate.
    if (candidata.inicio >= 0 && candidata.fin - candidata.inicio + 1 >= ANCHURA_MINIMA &&
        (mejor.inicio < 0 || candidata.energia > mejor.energia)) mejor = candidata;
}

static Region buscar_limitada(int desde, int hasta, float referencia)
{
    Region actual, mejor;
    int huecos = 0;
    double energia_hueco = 0.0;
    const float umbral = umbrales.banda * fmaxf(referencia, EPSILON);
    for (int k = desde; k <= hasta; ++k) {
        if (protegido(k)) {
            elegir_region(actual, mejor);
            actual = Region{};
            huecos = 0;
            energia_hueco = 0.0;
        } else if (piso[k] > umbral) {
            if (actual.inicio < 0) actual.inicio = k;
            actual.fin = k;
            actual.energia += energia_hueco + static_cast<double>(magnitudes[k]) * magnitudes[k];
            huecos = 0;
            energia_hueco = 0.0;
        } else if (actual.inicio >= 0) {
            if (++huecos > HUECO_MAXIMO) {
                elegir_region(actual, mejor);
                actual = Region{};
                huecos = 0;
                energia_hueco = 0.0;
            } else energia_hueco += static_cast<double>(magnitudes[k]) * magnitudes[k];
        }
    }
    elegir_region(actual, mejor);
    return mejor;
}

static bool coinciden(const Region& a, const Region& b)
{
    if (a.inicio < 0 || b.inicio < 0) return false;
    const int interseccion = std::min(a.fin, b.fin) - std::max(a.inicio, b.inicio) + 1;
    return 2 * interseccion >= std::min(a.fin - a.inicio + 1, b.fin - b.inicio + 1);
}

static void persistir_ancha(bool candidata)
{
    if (candidata) {
        ancha.entradas = std::min(ancha.entradas + 1, CONFIRMACIONES);
        ancha.ausencias = 0;
        if (ancha.entradas >= CONFIRMACIONES) ancha.publicada = true;
    } else {
        ancha.entradas = 0;
        if (ancha.publicada && ++ancha.ausencias >= RETIRADA) {
            ancha.publicada = false;
            ancha.ausencias = 0;
        }
    }
}

static void persistir_limitada(const Region& candidata)
{
    limitada.entradas = candidata.inicio < 0 ? 0 : coinciden(candidata, limitada.anterior)
        ? std::min(limitada.entradas + 1, CONFIRMACIONES) : 1;
    limitada.anterior = candidata;
    if (limitada.publicada.inicio >= 0) {
        if (coinciden(candidata, limitada.publicada)) {
            limitada.ausencias = 0;
            if (limitada.entradas >= CONFIRMACIONES) limitada.publicada = candidata;
        } else if (++limitada.ausencias >= RETIRADA) {
            limitada.publicada = Region{};
            limitada.ausencias = 0;
        }
    }
    if (limitada.publicada.inicio < 0 && limitada.entradas >= CONFIRMACIONES) {
        limitada.publicada = candidata;
        limitada.ausencias = 0;
    }
}

static bool actualizar_impulsivo(bool activo)
{
    impulsos[posicion_impulso] = activo && resultado.factor_cresta > umbrales.impulsivo;
    posicion_impulso = (posicion_impulso + 1) % HISTORIA_IMPULSIVA;
    int positivos = 0;
    for (bool impulso : impulsos) if (impulso) ++positivos;
    return positivos >= IMPULSOS_MINIMOS;
}

static const Familia& elegir_red()
{
    const Familia& a = red_50.publicada;
    const Familia& b = red_60.publicada;
    if (b.armonicos > a.armonicos || (b.armonicos == a.armonicos && b.suma > a.suma)) return b;
    return a;
}

static void publicar(bool impulsivo)
{
    const Familia& red = elegir_red();
    if (tonal.publicado.bin >= 0 || red.armonicos >= ARMONICOS_MINIMOS) {
        const bool es_tonal = tonal.publicado.bin >= 0;
        const Pico& pico = es_tonal ? tonal.publicado : red.fuerte;
        resultado.tipo_ruido = es_tonal ? 1 : 2;
        resultado.filtro_n2 = es_tonal ? 2 : 3;
        resultado.metodo = 1;
        resultado.pico_hz = espectro_bin_a_hz(pico.bin, FS);
        resultado.contraste_publicado_db = contraste(pico);
    } else if (impulsivo) {
        resultado.tipo_ruido = 5;
        resultado.filtro_n2 = 1;
        resultado.metodo = 2;
    } else if (ancha.publicada || limitada.publicada.inicio >= 0) {
        resultado.tipo_ruido = ancha.publicada ? 3 : 4;
        resultado.filtro_n2 = 1;
        resultado.metodo = 2;
        resultado.banda_detectada_lo = ancha.publicada ? ANALISIS_LO :
            espectro_bin_a_hz(limitada.publicada.inicio, FS);
        resultado.banda_detectada_hi = ancha.publicada ? ANALISIS_HI :
            espectro_bin_a_hz(limitada.publicada.fin, FS);
    }
}
} // espacio de nombres

void diagnostico_iniciar()
{
    memset(historial, 0, sizeof(historial));
    memset(mitades_validas, 0, sizeof(mitades_validas));
    mitad = 0;
    primera = true;
    umbrales = UmbralesDiagnostico{};
    resultado = ResultadoDiagnostico{};
    reiniciar_clasificacion();
}

void diagnostico_banda(float lo, float hi)
{
    if (!std::isfinite(lo) || !std::isfinite(hi) || lo < ANALISIS_LO || lo >= hi || hi > ANALISIS_HI) return;
    if (lo == banda_lo && hi == banda_hi) return;
    banda_lo = lo;
    banda_hi = hi;
    reiniciar_clasificacion();
}

const UmbralesDiagnostico& diagnostico_umbrales()
{
    return umbrales;
}

bool diagnostico_ajustar_umbral(const char* nombre, float valor)
{
    if (nombre == nullptr || !std::isfinite(valor) || valor <= 1.0f || valor > 100.0f) return false;
    float* destino = nullptr;
    if (strcmp(nombre, "tonal") == 0) destino = &umbrales.tonal;
    else if (strcmp(nombre, "red") == 0) destino = &umbrales.red;
    else if (strcmp(nombre, "impulsivo") == 0) destino = &umbrales.impulsivo;
    else if (strcmp(nombre, "banda") == 0) destino = &umbrales.banda;
    if (destino == nullptr) return false;
    *destino = valor;
    reiniciar_clasificacion();
    return true;
}

const ResultadoDiagnostico& diagnostico_procesar(const float* x, uint64_t first_sample)
{
    const int64_t comienzo = esp_timer_get_time();
    resultado = ResultadoDiagnostico{};
    const bool activo = incorporar_bloque(x);
    resultado.parcial = primera;
    resultado.inicio_ventana = primera ? 0 : first_sample - H;
    // Primera: bloque + ceros a la derecha. Después: mitad anterior + actual.
    const int inicio = primera ? 0 : (1 - mitad) * H;
    bool ventana_valida = !primera && mitades_validas[0] && mitades_validas[1];
    mitad = 1 - mitad;
    primera = false;

    resultado.dc = espectro_magnitudes(historial, magnitudes, inicio);
    for (float magnitud : magnitudes) {
        if (!std::isfinite(magnitud)) {
            // Tampoco se admite evidencia si la FFT desborda por una entrada extrema.
            ventana_valida = false;
            memset(magnitudes, 0, sizeof(magnitudes));
            break;
        }
    }
    espectro_piso(magnitudes, piso);
    double cuadrados = 0.0;
    for (float valor : piso) cuadrados += static_cast<double>(valor) * valor;
    resultado.piso_resumen = static_cast<float>(sqrt(cuadrados / (N / 2 + 1)));
    const int desde = static_cast<int>(ceilf(espectro_hz_a_bin(ANALISIS_LO, FS)));
    const int hasta = static_cast<int>(floorf(espectro_hz_a_bin(ANALISIS_HI, FS)));
    const float referencia = referencia_global(desde, hasta);

    Pico candidato;
    Familia familia_50, familia_60;
    Region region;
    bool banda_ancha = false;
    if (ventana_valida) {
        completos = std::min(completos + 1, CONFIRMACIONES);
        if (activo) {
            familia_50 = buscar_familia(50, desde, hasta, picos_50);
            familia_60 = buscar_familia(60, desde, hasta, picos_60);
            candidato = buscar_tonal(desde, hasta, familia_50, familia_60);
            banda_ancha = detectar_ancha(desde, hasta, referencia);
            region = buscar_limitada(desde, hasta, referencia);
        }
    } else completos = 0;

    // Todos actualizan sus historias, incluso si luego gana una prioridad mayor.
    persistir_tonal(candidato);
    persistir_red(red_50, familia_50);
    persistir_red(red_60, familia_60);
    persistir_ancha(banda_ancha);
    persistir_limitada(region);
    const bool impulsivo = actualizar_impulsivo(activo);
    resultado.calentamiento = completos < CONFIRMACIONES ? 1 : 0;
    if (candidato.bin >= 0) {
        resultado.magnitud_candidato = candidato.magnitud;
        resultado.piso_local = candidato.piso;
        resultado.contraste_db = contraste(candidato);
    }
    publicar(impulsivo);
    resultado.tiempo_us = static_cast<uint32_t>(esp_timer_get_time() - comienzo);
    return resultado;
}

const ResultadoDiagnostico& diagnostico_resultado()
{
    return resultado;
}
