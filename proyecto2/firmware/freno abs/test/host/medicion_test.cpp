#include "Arduino.h"
#include "medicion.h"
#include "ensayos.h"
#include "motor.h"
#include "freno.h"
#include "referencia.h"
#include <cassert>
#include <cmath>
#include <iostream>
uint64_t relojUs = 0;
void (*interrupcion)() = nullptr;
std::vector<std::string> gpio;
std::vector<int> posiciones;
Puerto Serial;
void setup(); void loop();
void avanzar(uint64_t us) { relojUs += us; loop(); }
void pulso(uint64_t us) { relojUs += us; emitirMarcaPrueba(); loop(); }
void comando(const std::string &s) { Serial.entrada = s+"\n"; loop(); }
void normal() { pulso(50000); pulso(50000); assert(Medicion::leerLectura().valida); }
int main(int argc, char **argv) {
  assert(argc==2);
  const std::string caso=argv[1];
  setup(); loop();
  using M = Medicion::Estado;
  if(caso=="sensor") {
    auto isrOriginal=interrupcion;
    comando("sensor_on");
    assert(Medicion::diagnosticoActivo() && modoInterrupcionPrueba()==CHANGE);
    assert(interrupcion==isrOriginal);
    // Completar una marca. La entrada no cuenta, la salida confirma una sola.
    relojUs=50000; nivelSensorPrueba()=LOW; interrupcion(); loop();
    assert(Medicion::leerLectura().pulsosAceptados==0);
    relojUs=50200; nivelSensorPrueba()=HIGH; interrupcion(); loop();
    assert(Medicion::leerLectura().pulsosAceptados==1);
    // Llamada repetida del mismo nivel. No inventa otra marca.
    relojUs=75000; interrupcion(); loop();
    assert(Medicion::leerLectura().pulsosAceptados==1);
    assert(Serial.salida.find("#SENSOR,1,50000,50000,0,0,0")!=std::string::npos);
    assert(Serial.salida.find("#SENSOR,2,50200,200,1,1,0")!=std::string::npos);
    comando("preparar"); assert(!Motor::estaEncendido());
    assert(Serial.salida.find("SENSOR_DIAGNOSTICO_ACTIVO")!=std::string::npos);
    for(int i=0;i<140;i++){relojUs+=10;interrupcion();}
    loop(); assert(Serial.salida.find("#SENSOR_LOST,")!=std::string::npos);
    comando("sensor_off");
    assert(interrupcion==isrOriginal);
    assert(!Medicion::diagnosticoActivo() && modoInterrupcionPrueba()==CHANGE);
    pulso(50000); assert(Medicion::leerLectura().pulsosAceptados==2);
  } else if(caso=="inicial") {
    auto l=Medicion::leerLectura(); assert(l.estado==M::SinPulsos && std::isnan(l.rpm));
    pulso(50000); l=Medicion::leerLectura(); assert(l.estado==M::UnaMarca && !l.valida);
    pulso(50000); l=Medicion::leerLectura(); assert(l.valida && l.rpm==1200.0f);
  } else if(caso=="una_marca_timeout") {
    pulso(50000);
    auto l=Medicion::leerLectura();
    assert(l.estado==M::UnaMarca && l.pulsosAceptados==1 && !l.valida);
    avanzar(1000001);
    l=Medicion::leerLectura();
    assert(l.estado==M::SinSenal && l.pulsosAceptados==1 && std::isnan(l.rpm));
    avanzar(2000000);
    assert(Medicion::leerLectura().estado==M::SinSenal);
    // Giros manuales aislados no alternan entre una RPM inventada y UNA_MARCA.
    for(int i=0;i<4;++i){
      pulso(2000000);
      l=Medicion::leerLectura();
      assert(l.estado==M::UnaMarca && !l.disponible && !l.valida);
      avanzar(1000001);
      assert(Medicion::leerLectura().estado==M::SinSenal);
    }
    // Tras reanclar, la segunda marca cercana permite calcular velocidad.
    pulso(50000);
    assert(Medicion::leerLectura().estado==M::UnaMarca);
    pulso(50000);
    l=Medicion::leerLectura();
    assert(l.valida && l.rpm==1200 && l.pulsosAceptados==7);
  } else if(caso=="una_marca_wrap") {
    relojUs=(static_cast<uint64_t>(UINT32_MAX)-500ULL)*1000ULL;
    pulso(50000);
    assert(Medicion::leerLectura().estado==M::UnaMarca);
    avanzar(1000001);
    assert(Medicion::leerLectura().estado==M::SinSenal);
    avanzar(static_cast<uint64_t>(UINT32_MAX)+1000);
    assert(Medicion::leerLectura().estado==M::SinSenal);
  } else if(caso=="arranque_marca_larga") {
    normal();
    relojUs += 50000; nivelSensorPrueba()=LOW; interrupcion(); loop();
    // El disco queda detenido sobre negro y sale de la marca cien segundos despues.
    relojUs += 100000000; nivelSensorPrueba()=HIGH; interrupcion(); loop();
    assert(!Medicion::leerLectura().valida);
    pulso(200000);
    auto l=Medicion::leerLectura();
    assert(l.estado==M::UnaMarca && !l.valida && std::isnan(l.rpmCruda));
    pulso(200000);
    l=Medicion::leerLectura();
    assert(l.valida && l.rpm==300 && l.rpmCruda==300);
  } else if(caso=="parada_fijo" || caso=="perdida_baja_sin_descenso" || caso=="recupera_fijo" || caso=="pico_antes_parada") {
    comando("tiempo6000");comando("preparar");normal();comando("fijo30");
    if(caso=="perdida_baja_sin_descenso") {
      // Una sola lectura baja no basta para inferir desaceleracion observada.
      pulso(200000);
      avanzar(601000);avanzar(1500000);
      assert(Ensayos::leerEstado()==Ensayos::Estado::Fallo);
    } else {
      pulso(80000);pulso(120000);pulso(200000);pulso(250000);
      if(caso=="pico_antes_parada") {
        pulso(50000);
        assert(Medicion::leerLectura().estado==M::Sospechosa);
        avanzar(1001000);avanzar(600000);
        assert(Ensayos::leerEstado()==Ensayos::Estado::Fallo);
        assert(Serial.salida.find("FIJO_POSIBLE_PARADA_SIN_PULSOS")==std::string::npos);
        return 0;
      }
      avanzar(1001000);
      assert(Ensayos::leerEstado()==Ensayos::Estado::Fijo);
      assert(Serial.salida.find("FIJO_POSIBLE_PARADA_SIN_PULSOS")!=std::string::npos);
      assert(!Medicion::leerLectura().valida);
      if(caso=="recupera_fijo" || caso=="pico_antes_parada") {
        pulso(50000);pulso(50000);
        assert(Medicion::leerLectura().valida);
        assert(Serial.salida.find("FIJO_SENAL_RECUPERADA")!=std::string::npos);
        avanzar(251000);avanzar(1500000);
        assert(Ensayos::leerEstado()==Ensayos::Estado::Fallo);
      } else {
        avanzar(1500000);
        assert(Ensayos::leerEstado()==Ensayos::Estado::Fijo);
        avanzar(3000000);
        assert(Ensayos::leerEstado()==Ensayos::Estado::Finalizado);
        assert(!Motor::estaEncendido() && Freno::leerAngulo()==45);
        assert(Serial.salida.find("ENSAYO_FIN_DURACION_SIN_SENAL")!=std::string::npos);
        assert(Serial.salida.find("FALLO_MEDICION")==std::string::npos);
      }
    }
  } else if(caso=="cortos") {
    normal(); pulso(3000);
    auto l=Medicion::leerLectura();
    assert(l.valida && l.rpm==1200 && l.rpmCruda==20000);
    assert(l.pulsosRechazados==1 && l.ultimoPeriodoRechazadoUs==3000);
    pulso(47000); assert(Medicion::leerLectura().rpm==1200);
  } else if(caso=="salto") {
    normal(); pulso(25000);
    auto l=Medicion::leerLectura();
    assert(l.estado==M::Sospechosa && std::isnan(l.rpm));
    assert(l.rpmCruda==2400 && l.rpmUltimaValida==1200 && l.saltosRechazados==1);
    pulso(50000); assert(Medicion::leerLectura().valida);
  } else if(caso=="sostenido") {
    normal(); pulso(25000); pulso(25000);
    assert(!Medicion::leerLectura().valida);
    pulso(25000);
    auto l=Medicion::leerLectura(); assert(l.valida && l.rpm==2400 && l.saltosRechazados==2);
  } else if(caso=="desaceleracion") {
    normal(); pulso(200000);
    auto l=Medicion::leerLectura(); assert(l.valida && l.rpm==300 && l.saltosRechazados==0);
  } else if(caso=="antiguedad") {
    normal(); avanzar(251000);
    auto l=Medicion::leerLectura(); assert(l.estado==M::Antigua && std::isnan(l.rpm));
    avanzar(750000); l=Medicion::leerLectura();
    assert(l.estado==M::SinSenal && !l.valida && std::isnan(l.rpm));
    assert(Medicion::calcularRPM(micros())==0);
    pulso(50000); assert(!Medicion::leerLectura().valida);
    pulso(50000); assert(Medicion::leerLectura().valida);
  } else if(caso=="cola") {
    normal();
    for(int i=0;i<50;i++){relojUs+=1000;emitirMarcaPrueba();}
    loop();auto l=Medicion::leerLectura();
    assert(l.estado==M::Desbordamiento && l.perdidosCola>0 && !l.valida);
    pulso(50000); assert(!Medicion::leerLectura().valida);
    pulso(50000); assert(Medicion::leerLectura().valida);
  } else if(caso=="silencio_wrap") {
    normal();avanzar(static_cast<uint64_t>(UINT32_MAX)+100000);
    assert(Medicion::leerLectura().estado==M::SinSenal);
    pulso(50000);assert(!Medicion::leerLectura().valida);
    pulso(50000);assert(Medicion::leerLectura().valida);
  } else if(caso=="fallo") {
    comando("preparar");normal();comando("fijo30");
    assert(Ensayos::leerEstado()==Ensayos::Estado::Fijo);
    avanzar(251000);avanzar(1500000);
    assert(Ensayos::leerEstado()==Ensayos::Estado::Fallo);
    assert(!Motor::estaEncendido() && Freno::leerAngulo()==45);
    assert(Serial.salida.find("FALLO_MEDICION")!=std::string::npos);
    assert(Serial.salida.find("ENSAYO_FIN_DURACION")==std::string::npos);
  } else if(caso=="reinicio") {
    normal();comando("r");auto l=Medicion::leerLectura();
    assert(l.estado==M::SinPulsos && l.pulsosAceptados==0 && l.pulsosRechazados==0);
    normal();assert(Medicion::leerLectura().valida);
  } else if(caso=="referencia_registro") {
    comando("tiempo6000");comando("preparar");normal();
    assert(!Referencia::disponible());
    comando("fijo30");
    assert(Referencia::evaluar(millis())==1200);
    comando("tiempo3000");  // No puede alterar la curva activa.
    for(int i=0;i<40;i++) pulso(50000);
    assert(Referencia::evaluar(millis())==800);
    pulso(100000); // La velocidad cambia, pero la referencia no se reancla.
    assert(Medicion::leerLectura().rpm==600);
    assert(std::fabs(Referencia::evaluar(millis())-780)<0.01f);
    for(int i=0;i<39;i++) pulso(100000);
    assert(Ensayos::leerEstado()==Ensayos::Estado::Finalizado);
    assert(Referencia::disponible() && Referencia::evaluar(millis())==0);
    pulso(100000);assert(Referencia::evaluar(millis())==0);
    std::cout<<Serial.salida;
    return 0;
  } else if(caso=="referencia_dato_invalido") {
    comando("tiempo6000");comando("preparar");normal();comando("fijo30");
    pulso(25000);avanzar(100000);
    assert(!Medicion::leerLectura().valida && Referencia::disponible());
    std::cout<<Serial.salida;
    comando("cancelar");comando("r");
    assert(!Referencia::disponible());
    return 0;
  } else if(caso=="referencia_cancelacion") {
    comando("tiempo6000");comando("preparar");normal();comando("fijo30");
    assert(Referencia::disponible());
    comando("r");assert(Referencia::disponible()); // Bloqueado durante ensayo.
    comando("cancelar");assert(!Referencia::disponible());
    comando("preparar");assert(!Referencia::disponible());
    pulso(100000);pulso(100000);comando("fijo30");
    assert(Referencia::evaluar(millis())==600);
    avanzar(301000);avanzar(1500000);
    assert(Ensayos::leerEstado()==Ensayos::Estado::Fallo);
    assert(!Referencia::disponible() && std::isnan(Referencia::evaluar(millis())));
  } else if(caso=="telemetria") {
    normal();pulso(3000);avanzar(100000);
    assert(Serial.salida.find("#DIAG,")!=std::string::npos);
    std::cout<<Serial.salida;
    return 0;
  } else assert(false);
  std::cout<<caso<<" correcto\n";
}
