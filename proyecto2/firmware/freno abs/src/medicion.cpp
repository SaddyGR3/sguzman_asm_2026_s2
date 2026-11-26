#include "medicion.h"
#include "configuracion.h"
#include "detector_marca.h"
#include <math.h>

namespace Medicion {
using namespace Configuracion;
namespace {
DetectorMarca detector(minimoZonaLibreUs, minimoMarcaUs);
struct Pulso { uint32_t instanteUs; uint32_t periodoUs; uint8_t tipo; };
// La ISR valida la secuencia de niveles, mide tiempos y deposita datos. No imprime ni calcula RPM.
volatile Pulso cola[capacidadColaPulsos];
volatile uint32_t escritura = 0, lecturaCola = 0;
volatile uint32_t ultimaMarcaUs = 0;
volatile uint32_t ultimaMarcaRecibidaUs = 0, ultimaMarcaRecibidaMs = 0;
volatile bool hayMarca = false;
volatile uint32_t conteoPulsos = 0, conteoRechazados = 0, perdidos = 0;

uint32_t periodoValidadoUs = 0, ultimaValidaUs = 0, ultimaValidaMs = 0;
uint32_t inicioRpmUs = 0;
bool inicioDisponible = false, hayValidacion = false, sospechosa = false;
bool desbordamiento = false;
uint32_t perdidosVistos = 0, saltos = 0, ultimoRechazadoUs = 0;
uint32_t periodoCrudoUs = 0, periodoPendienteUs = 0, confirmaciones = 0;

// Captura acotada de llamadas a la ISR CHANGE. No imprime desde la interrupcion.
constexpr uint32_t capacidadSensor = 128;
struct CambioSensor { uint32_t numero, instante, intervalo, nivel, aceptados, cortos; };
volatile CambioSensor cambiosSensor[capacidadSensor];
volatile uint32_t sensorEscritura = 0, sensorLectura = 0, sensorPerdidos = 0;
volatile uint32_t sensorNumero = 0, sensorAnterior = 0;
volatile bool sensorActivo = false;
uint32_t sensorPerdidosInformados = 0;

void IRAM_ATTR registrarInterrupcionSensor(uint32_t instante, uint32_t nivel) {
  const uint32_t intervalo = instante - sensorAnterior;
  sensorAnterior = instante;
  ++sensorNumero;
  const uint32_t siguiente = (sensorEscritura + 1) % capacidadSensor;
  if (siguiente == sensorLectura) { ++sensorPerdidos; return; }
  cambiosSensor[sensorEscritura].numero = sensorNumero;
  cambiosSensor[sensorEscritura].instante = instante;
  cambiosSensor[sensorEscritura].intervalo = intervalo;
  cambiosSensor[sensorEscritura].nivel = nivel;
  cambiosSensor[sensorEscritura].aceptados = conteoPulsos;
  cambiosSensor[sensorEscritura].cortos = conteoRechazados;
  sensorEscritura = siguiente;
}

void IRAM_ATTR detectarMarca() {
  const uint32_t ahora = micros();
  const uint32_t nivel = digitalRead(pinSensor);
  uint32_t inicioMarca = 0;
  const bool completa = detector.actualizar(nivel == nivelMarcaSensor, ahora, inicioMarca);
  if (completa) {
    // Medir entre entradas a marcas completas. No entre entrada y salida.
    const uint32_t periodo = hayMarca ? inicioMarca - ultimaMarcaUs : 0;
    const bool corto = hayMarca && periodo <= tiempoMinimoPulsoUs;
    const uint32_t ahoraMs = millis();
    const bool silencio = hayMarca &&
        ahoraMs - ultimaMarcaRecibidaMs > tiempoSinPulsoParaCeroUs / 1000U;
    const uint8_t tipo = corto ? 1 : ((!hayMarca || silencio) ? 0 : 2);
    if (corto) ++conteoRechazados;
    else {
      ultimaMarcaUs = inicioMarca;
      ultimaMarcaRecibidaUs = ahora;
      ultimaMarcaRecibidaMs = ahoraMs;
      hayMarca = true;
      ++conteoPulsos;
    }

    const uint32_t siguiente = (escritura + 1) % capacidadColaPulsos;
    if (siguiente == lecturaCola) ++perdidos;
    else {
      cola[escritura].instanteUs = inicioMarca;
      cola[escritura].periodoUs = periodo;
      cola[escritura].tipo = tipo;
      escritura = siguiente;
    }
  }
  if (sensorActivo) registrarInterrupcionSensor(ahora, nivel);
}

bool extraer(Pulso &p) {
  noInterrupts();
  if (lecturaCola == escritura) { interrupts(); return false; }
  p.instanteUs = cola[lecturaCola].instanteUs;
  p.periodoUs = cola[lecturaCola].periodoUs;
  p.tipo = cola[lecturaCola].tipo;
  lecturaCola = (lecturaCola + 1) % capacidadColaPulsos;
  interrupts();
  return true;
}

void aceptar(const Pulso &p) {
  periodoValidadoUs = p.periodoUs;
  ultimaValidaUs = p.instanteUs;
  ultimaValidaMs = millis() - (micros() - p.instanteUs) / 1000U;
  hayValidacion = true;
  sospechosa = false;
  desbordamiento = false;
  confirmaciones = 0;
  if (!inicioDisponible) { inicioRpmUs = p.instanteUs; inicioDisponible = true; }
}
}

void iniciar() {
  pinMode(pinSensor, INPUT);
  detector.reiniciar(digitalRead(pinSensor) == nivelMarcaSensor, micros());
  attachInterrupt(digitalPinToInterrupt(pinSensor), detectarMarca, CHANGE);
}

bool diagnosticoActivo() { return sensorActivo; }

void configurarDiagnostico(bool activo) {
  // Solo habilita observacion. No cambia el modo ni la funcion de interrupcion.
  noInterrupts();
  if (activo) {
    sensorEscritura = sensorLectura = sensorPerdidos = sensorNumero = 0;
    sensorPerdidosInformados = 0;
    sensorAnterior = micros();
  }
  sensorActivo = activo;
  const uint32_t instante = micros();
  const uint32_t nivel = digitalRead(pinSensor);
  interrupts();
  Serial.print("#SENSOR_MODE,"); Serial.print(activo ? 1 : 0);
  Serial.print(','); Serial.print(instante);
  Serial.print(','); Serial.println(nivel);
}

void registrarDiagnostico() {
  // Limite por pasada para no monopolizar loop ante una entrada ruidosa.
  for (int i = 0; i < 8; ++i) {
    CambioSensor c;
    noInterrupts();
    if (sensorLectura == sensorEscritura) { interrupts(); break; }
    const uint32_t indice = sensorLectura;
    c.numero = cambiosSensor[indice].numero;
    c.instante = cambiosSensor[indice].instante;
    c.intervalo = cambiosSensor[indice].intervalo;
    c.nivel = cambiosSensor[indice].nivel;
    c.aceptados = cambiosSensor[indice].aceptados;
    c.cortos = cambiosSensor[indice].cortos;
    sensorLectura = (indice + 1) % capacidadSensor;
    interrupts();
    Serial.print("#SENSOR,"); Serial.print(c.numero);
    Serial.print(','); Serial.print(c.instante);
    Serial.print(','); Serial.print(c.intervalo);
    Serial.print(','); Serial.print(c.nivel);
    Serial.print(','); Serial.print(c.aceptados);
    Serial.print(','); Serial.println(c.cortos);
  }
  noInterrupts();
  const uint32_t perdidos = sensorPerdidos;
  interrupts();
  if (perdidos != sensorPerdidosInformados) {
    sensorPerdidosInformados = perdidos;
    Serial.print("#SENSOR_LOST,"); Serial.println(perdidos);
  }
}

void reiniciar() {
  noInterrupts();
  escritura = lecturaCola = 0;
  ultimaMarcaUs = ultimaMarcaRecibidaUs = ultimaMarcaRecibidaMs = 0; hayMarca = false;
  conteoPulsos = conteoRechazados = perdidos = 0;
  detector.reiniciar(digitalRead(pinSensor) == nivelMarcaSensor, micros());
  interrupts();
  periodoValidadoUs = ultimaValidaUs = ultimaValidaMs = inicioRpmUs = 0;
  inicioDisponible = hayValidacion = sospechosa = desbordamiento = false;
  perdidosVistos = saltos = ultimoRechazadoUs = periodoCrudoUs = 0;
  periodoPendienteUs = confirmaciones = 0;
}

void actualizar() {
  noInterrupts();
  const uint32_t descartados = perdidos;
  interrupts();
  if (descartados != perdidosVistos) {
    // No reconstruir una velocidad confiable con una secuencia incompleta.
    perdidosVistos = descartados;
    desbordamiento = true;
    hayValidacion = false;
    confirmaciones = 0;
    noInterrupts();
    lecturaCola = escritura;
    hayMarca = false;
    interrupts();
    return;
  }
  Pulso p;
  while (extraer(p)) {
    if (p.periodoUs != 0) periodoCrudoUs = p.periodoUs;
    if (p.tipo == 1) { ultimoRechazadoUs = p.periodoUs; continue; }
    if (p.tipo == 0) {
      // Primera marca o reanudacion tras silencio. Todavia no hay velocidad.
      hayValidacion = false;
      sospechosa = false;
      confirmaciones = 0;
      continue;
    }
    const uint32_t instanteMs = millis() - (micros() - p.instanteUs) / 1000U;
    if (hayValidacion && instanteMs - ultimaValidaMs > tiempoSinPulsoParaCeroUs / 1000U) {
      // El primer pulso despues de un silencio largo solo vuelve a anclar.
      // No inferir una vuelta completa a partir de un intervalo desconocido.
      hayValidacion = false;
      sospechosa = false;
      confirmaciones = 0;
      continue;
    }
    const bool aumentoBrusco = hayValidacion &&
        static_cast<uint64_t>(periodoValidadoUs) * factorSaltoDenominador >
        static_cast<uint64_t>(p.periodoUs) * factorSaltoNumerador;
    if (aumentoBrusco) {
      ultimoRechazadoUs = p.periodoUs;
      sospechosa = true;
      const uint32_t diferencia = p.periodoUs > periodoPendienteUs
          ? p.periodoUs - periodoPendienteUs : periodoPendienteUs - p.periodoUs;
      const bool consistente = confirmaciones != 0 &&
          static_cast<uint64_t>(diferencia) * 100 <=
          static_cast<uint64_t>(periodoPendienteUs) * toleranciaConfirmacionPorcentaje;
      confirmaciones = consistente ? confirmaciones + 1 : 1;
      periodoPendienteUs = p.periodoUs;
      if (confirmaciones < confirmacionesSalto) { ++saltos; continue; }
      // Permite recuperar un cambio sostenido. No certifica su origen fisico.
    }
    aceptar(p);
  }
}

bool leerInicio(uint32_t &inicio) { inicio = inicioRpmUs; return inicioDisponible; }

Lectura leerLectura() {
  noInterrupts();
  const uint32_t aceptados = conteoPulsos, rechazados = conteoRechazados;
  const uint32_t descartados = perdidos;
  const uint32_t ultimaRecibidaUs = ultimaMarcaRecibidaUs;
  const uint32_t ultimaRecibidaMs = ultimaMarcaRecibidaMs;
  interrupts();
  uint32_t edad = hayValidacion ? micros() - ultimaValidaUs :
      (aceptados ? micros() - ultimaRecibidaUs : UINT32_MAX);
  const uint32_t edadMs = hayValidacion ? millis() - ultimaValidaMs :
      (aceptados ? millis() - ultimaRecibidaMs : UINT32_MAX);
  if (edadMs > UINT32_MAX / 1000U) edad = UINT32_MAX;
  uint32_t limite = periodoValidadoUs > tiempoSinPulsoParaCeroUs / multiplicadorAntiguedad
      ? tiempoSinPulsoParaCeroUs : periodoValidadoUs * multiplicadorAntiguedad;
  if (limite < antiguedadMinimaUs) limite = antiguedadMinimaUs;
  Estado estado;
  if (desbordamiento || descartados != perdidosVistos) estado = Estado::Desbordamiento;
  else if (aceptados == 0) estado = Estado::SinPulsos;
  else if (edadMs > tiempoSinPulsoParaCeroUs / 1000U || edad > tiempoSinPulsoParaCeroUs)
    estado = Estado::SinSenal;
  else if (!hayValidacion) estado = Estado::UnaMarca;
  else if (sospechosa) estado = Estado::Sospechosa;
  else if (edad > limite) estado = Estado::Antigua;
  else estado = Estado::Reciente;
  const float ultima = hayValidacion ? 60000000.0f / (static_cast<float>(periodoValidadoUs) * marcasPorVuelta) : NAN;
  const float cruda = periodoCrudoUs ? 60000000.0f / (static_cast<float>(periodoCrudoUs) * marcasPorVuelta) : NAN;
  const bool valida = estado == Estado::Reciente;
  return {valida ? ultima : NAN, ultima, cruda, periodoValidadoUs, edad, ultimaValidaUs,
          aceptados, rechazados, saltos, descartados, ultimoRechazadoUs,
          hayValidacion, valida, estado};
}

float calcularRPM(uint32_t) {
  const Lectura l = leerLectura();
  // Compatibilidad visual con el CSV antiguo. No usar como entrada del PID.
  if (!l.disponible || l.estado == Estado::SinSenal) return 0.0f;
  return l.rpmUltimaValida;
}

const char *nombreEstado(Estado e) {
  switch (e) {
    case Estado::SinPulsos: return "SIN_PULSOS";
    case Estado::UnaMarca: return "UNA_MARCA";
    case Estado::Reciente: return "RECIENTE";
    case Estado::Antigua: return "ANTIGUA";
    case Estado::SinSenal: return "SIN_SENAL";
    case Estado::Sospechosa: return "SOSPECHOSA";
    case Estado::Desbordamiento: return "DESBORDAMIENTO";
  }
  return "DESCONOCIDO";
}

void leerConteos(uint32_t &aceptados, uint32_t &rechazados) {
  noInterrupts();
  aceptados = conteoPulsos; rechazados = conteoRechazados;
  interrupts();
}
}
