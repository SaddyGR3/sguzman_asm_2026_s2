#include "diagnostico.h"
#include "espectro.h"
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include "esp_timer.h"

namespace {
constexpr int N_MAX = 1024, BLOQUE = 512;
static int N = 1024, H = 512;
static const int TAMANOS[] = {256, 512, 1024};
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
    double porcentaje = 0.0;
    bool valida = false;
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

static float historial[N_MAX];
static float magnitudes[N_MAX / 2 + 1], piso[N_MAX / 2 + 1];
static float trabajo_mediana[N_MAX / 2 + 1];
static bool picos_50[N_MAX / 2 + 1], picos_60[N_MAX / 2 + 1];
static bool anterior_valido = false, actual_valido = false;
static bool impulsos[HISTORIA_IMPULSIVA];
static int posicion_impulso = 0, completos = 0;
static bool primera = true;
static float banda_lo = 100.0f, banda_hi = 1200.0f;
static UmbralesDiagnostico umbrales;
static EstadoTonal tonal;
static EstadoRed red_50, red_60;
static EstadoAncha ancha;
static EstadoLimitada limitada;
static ResultadoDiagnostico resultado;
static bool debug_activado = false;
static DiagnosticoDebug debug;
static FondoDiagnostico fondo;
static float perfiles_potencia[3][N_MAX / 2 + 1], perfiles_piso2[3][N_MAX / 2 + 1];
static float* fondo_potencia = perfiles_potencia[2];
static float* fondo_piso2 = perfiles_piso2[2];
static bool impulsivo_bloque = false;
static double fondo_temporal2 = 0.0, exceso_fuera = 0.0, exceso_piso_fuera = 0.0;
static float rms_bloque = 0.0f, pico_bloque = 0.0f;
static float rms_cortos[BLOQUE / DIAG_SUBBLOQUE];
static unsigned subbloques_fuertes = 0;
static float razon_rafaga = 0.0f;
static bool impulso_candidato = false;
// PL02: máximos temporales medidos durante la misma captura de fondo.
static float fondo_cortos[DIAG_FONDO_BLOQUES], fondo_picos[DIAG_FONDO_BLOQUES];
static float corto_max = 0.0f, corto_min_fondo = 0.0f, pico_min_fondo = 0.0f;
static bool impulso_sobre_fondo = false, impulso_rechazado_fondo = false;

static void reiniciar_clasificacion()
{
    debug = DiagnosticoDebug{};
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
        magnitudes[bin] > umbral * fmaxf(piso[bin], EPSILON) &&
        static_cast<double>(magnitudes[bin]) * magnitudes[bin] >
            umbrales.fondo * umbrales.fondo * fondo_potencia[bin];
}

static double exceso(int bin)
{
    return std::max(0.0, static_cast<double>(magnitudes[bin]) * magnitudes[bin] - fondo_potencia[bin]);
}

static double exceso_piso(int bin)
{
    return std::max(0.0, static_cast<double>(piso[bin]) * piso[bin] - fondo_piso2[bin]);
}

static double energia_pico(int bin, int desde, int hasta)
{
    double energia = 0.0;
    for (int k = std::max(desde, bin - 2); k <= std::min(hasta, bin + 2); ++k)
        if (!protegido(k)) energia += exceso(k);
    return energia;
}

static bool piso_sobre_fondo(int bin)
{
    return static_cast<double>(piso[bin]) * piso[bin] >
        umbrales.fondo * umbrales.fondo * fmaxf(fondo_piso2[bin], EPSILON);
}

static Pico obtener_pico(int bin)
{
    Pico pico;
    pico.bin = bin;
    pico.magnitud = magnitudes[bin];
    pico.piso = piso[bin];
    return pico;
}

static void guardar_pico_debug(GrupoPicosDebug& grupo, int bin)
{
    ++grupo.cantidad;
    int posicion = static_cast<int>(std::min(grupo.cantidad, static_cast<unsigned>(DIAG_DEBUG_MAX_PICOS))) - 1;
    if (grupo.cantidad > DIAG_DEBUG_MAX_PICOS && magnitudes[bin] <= grupo.picos[posicion].magnitud) return;
    while (posicion > 0 && magnitudes[bin] > grupo.picos[posicion - 1].magnitud) {
        grupo.picos[posicion] = grupo.picos[posicion - 1];
        --posicion;
    }
    grupo.picos[posicion] = {espectro_bin_a_hz(bin, FS), magnitudes[bin], piso[bin]};
}

static float contraste(const Pico& pico)
{
    // La razón se forma en double para evitar desbordes con magnitudes extremas.
    const double razon = static_cast<double>(fmaxf(pico.magnitud, EPSILON)) / fmaxf(pico.piso, EPSILON);
    return static_cast<float>(20.0 * log10(razon));
}

static void registrar_medida_debug(MedidaDebug& medida, float valor)
{
    medida.actual = std::isfinite(valor) ? valor : -1.0f;
    if (medida.actual < 0.0f) return;
    if (medida.minimo < 0.0f || valor < medida.minimo) medida.minimo = valor;
    if (medida.maximo < 0.0f || valor > medida.maximo) medida.maximo = valor;
}

// El RMS y la cresta pertenecen al bloque actual de 512 muestras. Una mitad
// inválida se sustituye completa por ceros solo en la copia de análisis.
static bool incorporar_bloque(const float* x)
{
    double cuadrados = 0.0, corto = 0.0;
    float absoluto = 0.0f;
    bool valido = true;
    for (int j = 0; j < BLOQUE; ++j) {
        if (!std::isfinite(x[j])) valido = false;
        else {
            cuadrados += static_cast<double>(x[j]) * x[j];
            corto += static_cast<double>(x[j]) * x[j];
            absoluto = fmaxf(absoluto, fabsf(x[j]));
            if (fabsf(x[j]) >= 0.999f) valido = false;
        }
        if ((j + 1) % DIAG_SUBBLOQUE == 0) {
            rms_cortos[j / DIAG_SUBBLOQUE] = static_cast<float>(sqrt(corto / DIAG_SUBBLOQUE));
            corto = 0.0;
        }
    }
    std::memmove(historial, historial + BLOQUE, BLOQUE * sizeof(float));
    if (valido) std::memcpy(historial + BLOQUE, x, BLOQUE * sizeof(float));
    else std::memset(historial + BLOQUE, 0, BLOQUE * sizeof(float));
    actual_valido = valido;
    rms_bloque = valido ? static_cast<float>(sqrt(cuadrados / BLOQUE)) : 0.0f;
    pico_bloque = valido ? absoluto : 0.0f;
    resultado.factor_cresta = rms_bloque > DIAG_RMS_MINIMO ? pico_bloque / rms_bloque : 0.0f;
    if (debug_activado) {
        registrar_medida_debug(debug.rms, valido ? rms_bloque : -1.0f);
        registrar_medida_debug(debug.pico_temporal, valido ? pico_bloque : -1.0f);
        registrar_medida_debug(debug.cresta, valido ? resultado.factor_cresta : -1.0f);
    }
    return valido && rms_bloque > DIAG_RMS_MINIMO;
}

static void actualizar_fondo(bool ventana_valida)
{
    if (fondo.listo) return;
    if (fondo.espera) { --fondo.espera; return; }
    if (!ventana_valida) { diagnostico_calibrar_fondo(); return; }
    fondo_temporal2 += static_cast<double>(rms_bloque) * rms_bloque;
    fondo_cortos[fondo.bloques] = *std::max_element(rms_cortos, rms_cortos + BLOQUE / DIAG_SUBBLOQUE);
    fondo_picos[fondo.bloques] = pico_bloque;
    // Capturar las tres rejillas con las mismas muestras en silencio. Se permite
    // cambiar N después sin aprender el audio de prueba como si fuera fondo.
    for (int perfil = 0; perfil < 3; ++perfil) {
        const int n = TAMANOS[perfil], h = n / 2;
        ESP_ERROR_CHECK(espectro_iniciar(n));
        const float divisor = static_cast<float>(DIAG_FONDO_BLOQUES * (BLOQUE / h));
        for (int offset = 0; offset < BLOQUE; offset += h) {
            espectro_magnitudes(historial + BLOQUE + offset + h - n, magnitudes);
            espectro_piso(magnitudes, piso);
            for (int k = 0; k <= n / 2; ++k) {
                perfiles_potencia[perfil][k] += magnitudes[k] * magnitudes[k] / divisor;
                perfiles_piso2[perfil][k] += piso[k] * piso[k] / divisor;
            }
        }
    }
    ESP_ERROR_CHECK(espectro_iniciar(N));
    if (++fondo.bloques == DIAG_FONDO_BLOQUES) {
        fondo.rms = static_cast<float>(sqrt(fondo_temporal2 / DIAG_FONDO_BLOQUES));
        std::sort(fondo_cortos, fondo_cortos + DIAG_FONDO_BLOQUES);
        std::sort(fondo_picos, fondo_picos + DIAG_FONDO_BLOQUES);
        constexpr unsigned INDICE = (DIAG_FONDO_PERCENTIL * DIAG_FONDO_BLOQUES + 99) / 100 - 1;
        fondo.corto_p95 = fondo_cortos[INDICE];
        fondo.pico_p95 = fondo_picos[INDICE];
        fondo.listo = true;
    }
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
        if (familia.fuerte.bin < 0 || magnitudes[elegido] > familia.fuerte.magnitud)
            familia.fuerte = obtener_pico(elegido);
    }
    unsigned brutos = 0;
    double energia = 0.0;
    for (int k = desde; k <= hasta; ++k) {
        if (!usados[k]) continue;
        ++brutos;
        if (magnitudes[k] < familia.fuerte.magnitud * umbrales.red_rel / 100.0f) {
            usados[k] = false;
            continue;
        }
        ++familia.armonicos;
        familia.suma += magnitudes[k];
        energia += energia_pico(k, desde, hasta);
        if (debug_activado) guardar_pico_debug(base == 50 ? debug.red_50 : debug.red_60, k);
    }
    familia.porcentaje = exceso_fuera > EPSILON ? 100.0 * energia / exceso_fuera : 0.0;
    familia.valida = familia.armonicos >= ARMONICOS_MINIMOS && familia.porcentaje >= umbrales.red_pct;
    if (debug_activado) {
        if (base == 50) debug.armonicos_brutos_50 = brutos;
        else debug.armonicos_brutos_60 = brutos;
    }
    return familia;
}

static Pico buscar_tonal(int desde, int hasta, const Familia& f50, const Familia& f60)
{
    Pico candidato;
    for (int k = desde; k <= hasta; ++k) {
        if ((f50.valida && picos_50[k]) || (f60.valida && picos_60[k])) continue;
        if (maximo(k, umbrales.tonal) && exceso_fuera > EPSILON &&
            100.0 * energia_pico(k, desde, hasta) >= umbrales.tonal_pct * exceso_fuera &&
            magnitudes[k] > candidato.magnitud)
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
    if (candidata.valida) {
        estado.entradas = std::min(estado.entradas + 1, CONFIRMACIONES);
        estado.ausencias = 0;
        if (estado.entradas >= CONFIRMACIONES || estado.publicada.valida)
            estado.publicada = candidata;
    } else {
        estado.entradas = 0;
        if (estado.publicada.valida && ++estado.ausencias >= RETIRADA) {
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
        if (piso[k] > DIAG_FRACCION_PISO * referencia && piso_sobre_fondo(k)) ++ocupados;
        // PL01: el fondo decide actividad y cobertura, no la forma espectral.
        // Restarlo aquí crea ceros que hunden la media geométrica de la planitud.
        suma += piso[k];
        logaritmos += log(fmaxf(piso[k], EPSILON));
    }
    const int cantidad = hasta - desde + 1;
    const double media = suma / cantidad;
    const double planitud = exp(logaritmos / cantidad) / std::max(media, static_cast<double>(EPSILON));
    if (debug_activado) {
        debug.ancha_evaluada = true;
        registrar_medida_debug(debug.ocupacion, 100.0f * ocupados / cantidad);
        registrar_medida_debug(debug.planitud, static_cast<float>(planitud));
    }
    return ocupados >= DIAG_OCUPACION_MINIMA * cantidad && planitud >= DIAG_PLANITUD_MINIMA;
}

static void elegir_region(const Region& candidata, Region& mejor)
{
    // El recorrido ascendente conserva la menor frecuencia inicial en un empate.
    if (candidata.inicio >= 0 && candidata.fin - candidata.inicio + 1 >= ANCHURA_MINIMA &&
        (candidata.fin - candidata.inicio + 1) * FS / N <= DIAG_ANCHURA_MAXIMA_HZ &&
        exceso_piso_fuera > EPSILON &&
        100.0 * candidata.energia >= umbrales.region_pct * exceso_piso_fuera &&
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
        } else if (piso[k] > umbral && piso_sobre_fondo(k)) {
            if (actual.inicio < 0) actual.inicio = k;
            actual.fin = k;
            actual.energia += energia_hueco + exceso_piso(k);
            huecos = 0;
            energia_hueco = 0.0;
        } else if (actual.inicio >= 0) {
            if (++huecos > HUECO_MAXIMO) {
                elegir_region(actual, mejor);
                actual = Region{};
                huecos = 0;
                energia_hueco = 0.0;
            } else energia_hueco += exceso_piso(k);
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
    subbloques_fuertes = 0;
    razon_rafaga = 0.0f;
    impulso_candidato = false;
    corto_max = corto_min_fondo = pico_min_fondo = 0.0f;
    impulso_sobre_fondo = impulso_rechazado_fondo = false;
    if (activo && fondo.listo) {
        // Se puede ordenar: solo interesa duración total, no el orden de segmentos.
        constexpr int CANTIDAD = BLOQUE / DIAG_SUBBLOQUE;
        std::sort(rms_cortos, rms_cortos + CANTIDAD);
        const float mediana = 0.5f * (rms_cortos[CANTIDAD / 2 - 1] + rms_cortos[CANTIDAD / 2]);
        const float base = fmaxf(fmaxf(mediana, fondo.rms), DIAG_RMS_MINIMO);
        const float umbral = resultado.factor_cresta > umbrales.impulsivo
            ? fminf(umbrales.rafaga, 2.0f) : umbrales.rafaga;
        razon_rafaga = rms_cortos[CANTIDAD - 1] / base;
        for (float rms : rms_cortos) if (rms > umbral * base) ++subbloques_fuertes;
        const bool candidato_contraste = subbloques_fuertes >= 1 && subbloques_fuertes <= DIAG_SUBBLOQUES_MAX &&
            resultado.factor_cresta > 3.0f && pico_bloque > umbrales.pico_fondo * fmaxf(fondo.rms, DIAG_RMS_MINIMO);
        corto_max = rms_cortos[CANTIDAD - 1];
        corto_min_fondo = DIAG_MARGEN_TRANSITORIOS * fondo.corto_p95;
        pico_min_fondo = DIAG_MARGEN_TRANSITORIOS * fondo.pico_p95;
        impulso_sobre_fondo = corto_max > corto_min_fondo && pico_bloque > pico_min_fondo;
        impulso_candidato = candidato_contraste && impulso_sobre_fondo;
        impulso_rechazado_fondo = candidato_contraste && !impulso_sobre_fondo;
    }
    impulsos[posicion_impulso] = impulso_candidato;
    posicion_impulso = (posicion_impulso + 1) % HISTORIA_IMPULSIVA;
    int positivos = 0;
    for (bool impulso : impulsos) if (impulso) ++positivos;
    return positivos >= IMPULSOS_MINIMOS;
}

static const Familia& elegir_red()
{
    const Familia& a = red_50.publicada;
    const Familia& b = red_60.publicada;
    if (b.valida && (!a.valida || b.armonicos > a.armonicos ||
        (b.armonicos == a.armonicos && b.suma > a.suma))) return b;
    return a;
}

static void publicar(bool impulsivo)
{
    const Familia& red = elegir_red();
    if (tonal.publicado.bin >= 0 || red.valida) {
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
        const bool es_limitada = limitada.publicada.inicio >= 0;
        resultado.tipo_ruido = es_limitada ? 4 : 3;
        resultado.filtro_n2 = 1;
        resultado.metodo = 2;
        resultado.banda_detectada_lo = !es_limitada ? ANALISIS_LO :
            espectro_bin_a_hz(limitada.publicada.inicio, FS);
        resultado.banda_detectada_hi = !es_limitada ? ANALISIS_HI :
            espectro_bin_a_hz(limitada.publicada.fin, FS);
    }
}
} // espacio de nombres

void diagnostico_calibrar_fondo()
{
    fondo = FondoDiagnostico{};
    fondo_temporal2 = 0.0;
    memset(perfiles_potencia, 0, sizeof(perfiles_potencia));
    memset(perfiles_piso2, 0, sizeof(perfiles_piso2));
    memset(fondo_cortos, 0, sizeof(fondo_cortos));
    memset(fondo_picos, 0, sizeof(fondo_picos));
    reiniciar_clasificacion();
}

const FondoDiagnostico& diagnostico_fondo() { return fondo; }

void diagnostico_iniciar(bool calibrar_fondo)
{
    memset(historial, 0, sizeof(historial));
    anterior_valido = actual_valido = false;
    N = 1024; H = 512;
    fondo_potencia = perfiles_potencia[2];
    fondo_piso2 = perfiles_piso2[2];
    primera = true;
    umbrales = UmbralesDiagnostico{};
    resultado = ResultadoDiagnostico{};
    diagnostico_calibrar_fondo();
    if (!calibrar_fondo) {
        fondo.listo = true;
        fondo.espera = 0;
    }
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
    else if (strcmp(nombre, "fondo") == 0) destino = &umbrales.fondo;
    else if (strcmp(nombre, "tonal_pct") == 0) destino = &umbrales.tonal_pct;
    else if (strcmp(nombre, "red_rel") == 0) destino = &umbrales.red_rel;
    else if (strcmp(nombre, "red_pct") == 0) destino = &umbrales.red_pct;
    else if (strcmp(nombre, "region_pct") == 0) destino = &umbrales.region_pct;
    else if (strcmp(nombre, "rafaga") == 0) destino = &umbrales.rafaga;
    else if (strcmp(nombre, "pico_fondo") == 0) destino = &umbrales.pico_fondo;
    if (destino == nullptr) return false;
    *destino = valor;
    reiniciar_clasificacion();
    return true;
}

void diagnostico_debug_activar(bool activar)
{
    debug_activado = activar;
    debug = DiagnosticoDebug{};
}

const DiagnosticoDebug& diagnostico_debug() { return debug; }

static void reiniciar_rango_debug(MedidaDebug& medida)
{
    // El último valor pertenece al bloque mostrado; min/max son del intervalo.
    medida.minimo = medida.maximo = -1.0f;
}

void diagnostico_debug_reiniciar_contadores()
{
    debug.bloques = debug.supera_cresta = debug.confirma_impulsivo = 0;
    debug.candidatas_impulsivo = 0;
    debug.impulsos_rechazados_fondo = 0;
    for (auto& cantidad : debug.tipos) cantidad = 0;
    debug.candidatas_ancha = debug.confirmadas_ancha = 0;
    debug.candidatas_limitada = debug.confirmadas_limitada = 0;
    reiniciar_rango_debug(debug.rms);
    reiniciar_rango_debug(debug.pico_temporal);
    reiniciar_rango_debug(debug.cresta);
    reiniciar_rango_debug(debug.ocupacion);
    reiniciar_rango_debug(debug.planitud);
}

static EnergiaPicoDebug medir_energia_pico_debug(int bin, int desde, int hasta)
{
    EnergiaPicoDebug medida;
    if (bin < desde || bin > hasta) return medida;
    medida.hz = espectro_bin_a_hz(bin, FS);
    for (int k = std::max(desde, bin - 2); k <= std::min(hasta, bin + 2); ++k)
        medida.energia += static_cast<double>(magnitudes[k]) * magnitudes[k];
    if (debug.energia_analisis > 0.0)
        medida.porcentaje = 100.0 * medida.energia / debug.energia_analisis;
    return medida;
}

static void analizar_ventana(int offset, uint64_t first_sample, bool calibrando, bool activo)
{
    resultado = ResultadoDiagnostico{};
    resultado.factor_cresta = rms_bloque > DIAG_RMS_MINIMO ? pico_bloque / rms_bloque : 0.0f;
    if (debug_activado) {
        debug.red_50 = GrupoPicosDebug{};
        debug.red_60 = GrupoPicosDebug{};
        debug.maximos = GrupoPicosDebug{};
        debug.armonicos_brutos_50 = debug.armonicos_brutos_60 = 0;
        debug.activo = activo;
        debug.ancha_evaluada = false;
        debug.ocupacion.actual = debug.planitud.actual = -1.0f;
    }
    const int inicio = BLOQUE + offset + H - N;
    const uint64_t fin = first_sample + offset + H;
    resultado.parcial = primera && inicio < BLOQUE;
    resultado.inicio_ventana = fin >= static_cast<unsigned>(N) ? fin - N : 0;
    bool ventana_valida = actual_valido && (inicio >= BLOQUE || anterior_valido) && !resultado.parcial;
    resultado.dc = espectro_magnitudes(historial + inicio, magnitudes);
    for (int k = 0; k <= N / 2; ++k) {
        if (!std::isfinite(magnitudes[k])) {
            // Tampoco se admite evidencia si la FFT desborda por una entrada extrema.
            ventana_valida = false;
            memset(magnitudes, 0, sizeof(magnitudes));
            break;
        }
    }
    espectro_piso(magnitudes, piso);
    double cuadrados = 0.0;
    for (int k = 0; k <= N / 2; ++k) cuadrados += static_cast<double>(piso[k]) * piso[k];
    resultado.piso_resumen = static_cast<float>(sqrt(cuadrados / (N / 2 + 1)));
    const int desde = static_cast<int>(ceilf(espectro_hz_a_bin(ANALISIS_LO, FS)));
    const int hasta = static_cast<int>(floorf(espectro_hz_a_bin(ANALISIS_HI, FS)));
    const float referencia = referencia_global(desde, hasta);
    const bool nivel_suficiente = !calibrando && activo &&
        rms_bloque > umbrales.fondo * fmaxf(fondo.rms, DIAG_RMS_MINIMO);
    exceso_fuera = exceso_piso_fuera = 0.0;
    for (int k = desde; k <= hasta; ++k) {
        if (protegido(k)) continue;
        exceso_fuera += exceso(k);
        exceso_piso_fuera += exceso_piso(k);
    }

    Pico candidato;
    Familia familia_50, familia_60;
    Region region;
    bool banda_ancha = false;
    if (ventana_valida && !calibrando) {
        completos = std::min(completos + 1, CONFIRMACIONES);
        if (nivel_suficiente) {
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
    const bool impulsivo = impulsivo_bloque;
    resultado.calentamiento = completos < CONFIRMACIONES ? 1 : 0;
    if (candidato.bin >= 0) {
        resultado.magnitud_candidato = candidato.magnitud;
        resultado.piso_local = candidato.piso;
        resultado.contraste_db = contraste(candidato);
    }
    publicar(impulsivo);
    if (debug_activado) {
        debug.ventana_valida = ventana_valida;
        debug.nivel_suficiente = nivel_suficiente;
        debug.exceso_fuera = exceso_fuera;
        debug.tonal_porcentaje = 0.0;
        debug.pico_evaluado_hz = -1.0f;
        debug.red_porcentaje_50 = familia_50.porcentaje;
        debug.red_porcentaje_60 = familia_60.porcentaje;
        debug.region_porcentaje = region.inicio >= 0 && exceso_piso_fuera > EPSILON
            ? 100.0 * region.energia / exceso_piso_fuera : 0.0;
        debug.subbloques_fuertes = subbloques_fuertes;
        debug.razon_rafaga = razon_rafaga;
        debug.impulso_candidato = impulso_candidato;
        debug.corto_max = corto_max;
        debug.corto_min_fondo = corto_min_fondo;
        debug.pico_min_fondo = pico_min_fondo;
        debug.impulso_sobre_fondo = impulso_sobre_fondo;
        debug.referencia_global = referencia;
        debug.umbral_limitada = umbrales.banda * fmaxf(referencia, EPSILON);
        debug.ancha_candidata = banda_ancha;
        debug.ancha_confirmada = ancha.publicada;
        debug.confirmaciones_ancha = ancha.entradas;
        debug.ausencias_ancha = ancha.ausencias;
        debug.limitada_candidata_lo = region.inicio >= 0 ? espectro_bin_a_hz(region.inicio, FS) : -1.0f;
        debug.limitada_candidata_hi = region.fin >= 0 ? espectro_bin_a_hz(region.fin, FS) : -1.0f;
        debug.limitada_publicada_lo = limitada.publicada.inicio >= 0
            ? espectro_bin_a_hz(limitada.publicada.inicio, FS) : -1.0f;
        debug.limitada_publicada_hi = limitada.publicada.fin >= 0
            ? espectro_bin_a_hz(limitada.publicada.fin, FS) : -1.0f;
        debug.energia_region = region.energia;
        debug.confirmaciones_limitada = limitada.entradas;
        debug.ausencias_limitada = limitada.ausencias;
        debug.energia_analisis = 0.0;
        if (ventana_valida) {
            for (int k = desde; k <= hasta; ++k)
                debug.energia_analisis += static_cast<double>(magnitudes[k]) * magnitudes[k];
        }
        const int bin_publicado = resultado.tipo_ruido == 1 || resultado.tipo_ruido == 2
            ? static_cast<int>(lroundf(espectro_hz_a_bin(resultado.pico_hz, FS))) : -1;
        debug.energia_publicado = ventana_valida ? medir_energia_pico_debug(bin_publicado, desde, hasta)
                                                : EnergiaPicoDebug{};
        debug.energia_candidato = ventana_valida ? medir_energia_pico_debug(candidato.bin, desde, hasta)
                                                : EnergiaPicoDebug{};
        debug.candidato_tonal_hz = candidato.bin >= 0 ? espectro_bin_a_hz(candidato.bin, FS) : -1.0f;
        // Estos máximos no excluyen las familias de red: muestran también los
        // picos que el clasificador descartó como candidatos tonales independientes.
        if (ventana_valida && activo && !calibrando) {
            int mas_fuerte = -1;
            for (int k = desde; k <= hasta; ++k) {
                if (!maximo(k, umbrales.tonal)) continue;
                guardar_pico_debug(debug.maximos, k);
                if (mas_fuerte < 0 || magnitudes[k] > magnitudes[mas_fuerte]) mas_fuerte = k;
            }
            if (mas_fuerte >= 0) {
                debug.pico_evaluado_hz = espectro_bin_a_hz(mas_fuerte, FS);
                debug.tonal_porcentaje = exceso_fuera > EPSILON
                    ? 100.0 * energia_pico(mas_fuerte, desde, hasta) / exceso_fuera : 0.0;
            }
        }
        if (familia_50.valida && red_50.publicada.valida)
            debug.publicada_50 = debug.red_50;
        else if (!red_50.publicada.valida) debug.publicada_50 = GrupoPicosDebug{};
        if (familia_60.valida && red_60.publicada.valida)
            debug.publicada_60 = debug.red_60;
        else if (!red_60.publicada.valida) debug.publicada_60 = GrupoPicosDebug{};
        debug.confirmaciones_50 = red_50.entradas;
        debug.confirmaciones_60 = red_60.entradas;
        debug.ausencias_50 = red_50.ausencias;
        debug.ausencias_60 = red_60.ausencias;
        debug.armonicos_publicados_50 = red_50.publicada.armonicos;
        debug.armonicos_publicados_60 = red_60.publicada.armonicos;
        debug.familia_elegida = elegir_red().valida
            ? (&elegir_red() == &red_50.publicada ? 50 : 60) : 0;
        ++debug.bloques;
        if (banda_ancha) ++debug.candidatas_ancha;
        if (ancha.publicada) ++debug.confirmadas_ancha;
        if (region.inicio >= 0) ++debug.candidatas_limitada;
        if (limitada.publicada.inicio >= 0) ++debug.confirmadas_limitada;
        if (activo && resultado.factor_cresta > umbrales.impulsivo) ++debug.supera_cresta;
        if (impulsivo) ++debug.confirma_impulsivo;
        if (impulso_candidato) ++debug.candidatas_impulsivo;
        if (impulso_rechazado_fondo) ++debug.impulsos_rechazados_fondo;
        ++debug.tipos[resultado.tipo_ruido];
    }
}

bool diagnostico_cambiar_n(unsigned n)
{
    if (n != 256 && n != 512 && n != 1024) return false;
    if (n == static_cast<unsigned>(N)) return true;
    ESP_ERROR_CHECK(espectro_iniciar(static_cast<int>(n)));
    N = static_cast<int>(n); H = N / 2;
    const int perfil = n == 256 ? 0 : n == 512 ? 1 : 2;
    fondo_potencia = perfiles_potencia[perfil];
    fondo_piso2 = perfiles_piso2[perfil];
    memset(historial, 0, sizeof(historial));
    anterior_valido = actual_valido = false;
    primera = true;
    reiniciar_clasificacion();
    return true;
}

const ResultadoDiagnostico& diagnostico_procesar(const float* x, uint64_t first_sample)
{
    const int64_t comienzo = esp_timer_get_time();
    const bool activo = incorporar_bloque(x);
    const bool calibrando = !fondo.listo;
    actualizar_fondo(actual_valido && anterior_valido && !primera);
    impulsivo_bloque = actualizar_impulsivo(activo && !primera && !calibrando);
    for (int offset = 0; offset < BLOQUE; offset += H)
        analizar_ventana(offset, first_sample, calibrando, activo);
    anterior_valido = actual_valido;
    primera = false;
    resultado.tiempo_us = static_cast<uint32_t>(esp_timer_get_time() - comienzo);
    return resultado;  // DIAG único: último análisis, índice absoluto de su ventana.
}

const ResultadoDiagnostico& diagnostico_resultado()
{
    return resultado;
}
