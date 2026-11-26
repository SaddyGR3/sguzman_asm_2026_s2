#include "pid.h"
#include "configuracion.h"
#include "freno.h"
#include "registro.h"
namespace {
PID::Controlador controlador;
uint32_t reloj = 0;
}
uint32_t micros() { return reloj; }
uint32_t millis() { return reloj / 1000; }
namespace Registro {
void emitirEvento(const char *, int, uint32_t) {}
}
extern "C" {
struct Salida {
 float error, p, i, d, solicitada, limitada;
 uint32_t dtUs, omitidos;
 int disponible;
};
bool configurar(float kp, float ki, float kd) {
 reloj = 0;
 Freno::fijarAngulo(Configuracion::anguloLiberado);
 return controlador.configurar({kp,ki,kd,0.1f,20000,100000});
}
void reiniciar() { controlador.reiniciar(); }
Salida calcular(float referencia, float rpm, uint32_t ahora, bool valida) {
 reloj = ahora;
 controlador.actualizar(referencia,{rpm,ahora,valida},ahora);
 const auto &r = controlador.leer();
 return {r.error,r.p,r.i,r.d,r.solicitada,r.limitada,r.dtUs,r.omitidos,r.disponible};
}
float corteAutomatico() { return Configuracion::rpmApagadoAutomatico; }
float inicioAutomatico() { return Configuracion::rpmInicioAutomatico; }
uint32_t limitePreparacion() { return Configuracion::tiempoMaximoPreparacionMs; }
uint32_t limiteDescenso() { return Configuracion::tiempoMaximoDescensoMs; }
int convertir(float accion) { return Freno::anguloParaAccion(accion); }
}
