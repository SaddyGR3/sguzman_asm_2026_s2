#include "Arduino.h"
#include "configuracion.h"
#include "ensayos.h"
#include "freno.h"
#include "motor.h"
#include <cassert>
#include <iostream>

uint64_t relojUs = 0;
void (*interrupcion)() = nullptr;
std::vector<std::string> gpio;
std::vector<int> posiciones;
Puerto Serial;
void setup();
void loop();
using Ensayos::Estado;

void comando(const std::string &texto) {
  Serial.entrada = texto + "\n";
  loop();
}
void avanzar(uint64_t us) {
  relojUs += us;
  loop();
}
void pulso(uint64_t demoraUs) {
  relojUs += demoraUs;
  interrupcion();
  loop();
}
void prepararMedicion() {
  comando("preparar");
  assert(Ensayos::leerEstado() == Estado::Preparacion);
  assert(Motor::estaEncendido());
  assert(Freno::leerAngulo() == 90);
  pulso(50000);
  pulso(50000);
}
void esperarTexto(const std::string &texto) {
  assert(Serial.salida.find(texto) != std::string::npos);
}
void verificarNivelMotor(bool encendido) {
  if (!Configuracion::controlMotorHabilitado) return;
  const int activo = Configuracion::nivelMotorEncendido;
  const int esperado = encendido ? activo : (activo == HIGH ? LOW : HIGH);
  for (auto i = gpio.rbegin(); i != gpio.rend(); ++i) {
    if (i->find("nivel 25 ") == 0) {
      assert(*i == "nivel 25 " + std::to_string(esperado));
      return;
    }
  }
  assert(false);
}
void verificarParada(Estado estado) {
  assert(Ensayos::leerEstado() == estado);
  assert(!Motor::estaEncendido());
  assert(Freno::leerAngulo() == 90);
  verificarNivelMotor(false);
}

int main(int argc, char **argv) {
  assert(argc == 2);
  const std::string caso = argv[1];
  if (caso == "micros_wrap") relojUs = UINT32_MAX - 70000ULL;
  if (caso == "millis_wrap") relojUs = (UINT32_MAX - 70ULL) * 1000ULL;
  setup();
  assert(Ensayos::leerEstado() == Estado::Reposo);
  assert(!Motor::estaEncendido());
  assert(Freno::leerAngulo() == 90);
  esperarTexto("tiempo_ms,rpm,servo_cmd_grados\n");
  verificarNivelMotor(false);

  if (caso == "deshabilitado") {
    comando("preparar");
    assert(Ensayos::leerEstado() == Estado::Reposo);
    comando("fijo47");
    comando("motor_on");
    esperarTexto("MOTOR_NO_HABILITADO");
    for (const auto &linea : gpio) assert(linea.find("25 ") == std::string::npos);
    comando("g47");
    assert(Freno::leerAngulo() == 47);
    comando("cancelar");
    verificarParada(Estado::Cancelado);
  } else if (caso == "normal" || caso == "micros_wrap" || caso == "millis_wrap") {
    comando("tiempo1000");
    prepararMedicion();
    verificarNivelMotor(true);
    const auto antes = Serial.salida.size();
    comando("fijo47");
    assert(Ensayos::leerEstado() == Estado::Fijo);
    assert(!Motor::estaEncendido());
    assert(Freno::leerAngulo() == 47);
    verificarNivelMotor(false);
    const auto inicio = Serial.salida.substr(antes);
    assert(inicio.find("MOTOR_CMD,0") < inicio.find("ENSAYO_FIJO_INICIO"));
    assert(inicio.find("ENSAYO_FIJO_INICIO") < inicio.find("SERVO_CMD,47"));
    esperarTexto("RPM_INICIAL_X100,120000");
    comando("g90");
    comando("r");
    comando("motor_on");
    comando("0");
    comando("p5");
    comando("preparar");
    assert(Ensayos::leerEstado() == Estado::Fijo);
    assert(Freno::leerAngulo() == 47);
    assert(!Motor::estaEncendido());
    esperarTexto("COMANDO_BLOQUEADO_ENSAYO");
    comando("pid");
    esperarTexto("PID_ACTUACION_DESHABILITADA");
    avanzar(999000);
    assert(Ensayos::leerEstado() == Estado::Fijo);
    avanzar(1000);
    verificarParada(Estado::Finalizado);
    esperarTexto("ENSAYO_FIN_DURACION");
    comando("g60");
    assert(Freno::leerAngulo() == 60);
  } else if (caso == "cancelacion") {
    comando("g70");
    comando("motor_on");
    comando("cancelar");
    verificarParada(Estado::Cancelado);
    prepararMedicion();
    comando("motor_off");
    verificarParada(Estado::Cancelado);
    prepararMedicion();
    comando("fijo47");
    comando("cancelar");
    verificarParada(Estado::Cancelado);
    avanzar(12000000);
    verificarParada(Estado::Cancelado);
    assert(Serial.salida.find("ENSAYO_FIN_DURACION") == std::string::npos);
  } else if (caso == "validacion") {
    comando("fijo47");
    esperarTexto("REQUIERE_PREPARAR");
    comando("tiempo0");
    comando("tiempo-1");
    comando("tiempo30001");
    esperarTexto("DURACION_INVALIDA");
    comando("tiempoX");
    esperarTexto("COMANDO_INVALIDO");
    comando("preparar");
    comando("fijo47");
    esperarTexto("MEDICION_INICIO_INVALIDA");
    assert(Motor::estaEncendido());
    pulso(50000);
    comando("fijo47");
    assert(Ensayos::leerEstado() == Estado::Preparacion);
    pulso(50000);
    comando("fijo46");
    comando("fijo91");
    esperarTexto("ANGULO_ENSAYO_INVALIDO");
    avanzar(251000);
    comando("fijo47");
    assert(Ensayos::leerEstado() == Estado::Preparacion);
    comando("cancelar");
    // No se pueden reutilizar los pulsos de una preparacion anterior.
    comando("preparar");
    comando("fijo47");
    assert(Ensayos::leerEstado() == Estado::Preparacion);
    pulso(50000);
    comando("fijo47");
    assert(Ensayos::leerEstado() == Estado::Preparacion);
    pulso(50000);
    pulso(50000);
    pulso(50000);
    comando("fijo90");
    assert(Ensayos::leerEstado() == Estado::Fijo);
  } else if (caso == "timeout" || caso == "timeout_inicio") {
    prepararMedicion();
    relojUs += Configuracion::tiempoMaximoPreparacionMs * 1000ULL;
    if (caso == "timeout_inicio") comando("fijo47");
    else loop();
    verificarParada(Estado::Fallo);
    esperarTexto("FALLO_TIEMPO_PREPARACION");
  } else if (caso == "linea_larga") {
    comando(std::string(24, 'x') + "motor_on");
    assert(!Motor::estaEncendido());
    esperarTexto("COMANDO_MUY_LARGO");
  } else {
    assert(false);
  }
  std::cout << caso << " correcto\n";
}
