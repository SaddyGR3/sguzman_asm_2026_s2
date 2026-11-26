#include "Arduino.h"
#include "ensayos.h"
#include "freno.h"
#include "motor.h"
#include "medicion.h"
#include "referencia.h"
#include "configuracion.h"
#include <cassert>
#include <cmath>
#include <iostream>
uint64_t relojUs=0;
void (*interrupcion)()=nullptr;
std::vector<std::string> gpio;
std::vector<int> posiciones;
Puerto Serial;
void setup();void loop();
void comando(const std::string &s){Serial.entrada=s+"\n";loop();}
void pulso(uint64_t t){relojUs+=t;emitirMarcaPrueba();loop();}
void avanzar(uint64_t t){relojUs+=t;loop();}
using E=Ensayos::Estado;
void cortar(const std::string &orden="auto_fijo30"){
 comando(orden);
 assert(Ensayos::leerEstado()==E::Preparacion && Motor::estaEncendido());
 assert(Freno::leerAngulo()==45 && !Referencia::disponible());
 pulso(50000);pulso(50000);
 assert(Motor::estaEncendido() && !Referencia::disponible());
 pulso(40000);
 assert(Ensayos::leerEstado()==E::DescensoLibre && !Motor::estaEncendido());
 assert(Freno::leerAngulo()==45 && !Referencia::disponible());
}
int main(int argc,char **argv){
 assert(argc==2);const std::string caso=argv[1];
 if(caso=="reloj")relojUs=(UINT32_MAX-100ULL)*1000ULL;
 setup();loop();
 if(caso=="normal" || caso=="libre" || caso=="reloj" || caso=="pid"){
   comando("tiempo2000");
   cortar(caso=="libre"?"auto_fijo45":caso=="pid"?"auto_pid":"auto_fijo30");
   pulso(45000);assert(Ensayos::leerEstado()==E::DescensoLibre);
   assert(Ensayos::leerTiempoEnsayoMs()==0 && !Referencia::disponible());
   pulso(47000);
   assert(Ensayos::leerEstado()==(caso=="pid"?E::Pid:E::Fijo));
   assert(!Motor::estaEncendido() && Referencia::disponible());
   assert(std::fabs(Referencia::evaluar(millis())-60000000.0f/47000)<0.1f);
   assert(Ensayos::leerTiempoEnsayoMs()==0);
   if(caso!="pid") assert(Freno::leerAngulo()==(caso=="libre"?45:30));
   const std::string salida=Serial.salida;
   assert(salida.find("AUTO_MOTOR_OFF_RPM_X100")<salida.find("AUTO_INICIO_RPM_X100"));
   assert(salida.find("AUTO_INICIO_RPM_X100")<salida.find("RPM_INICIAL_X100"));
   const auto primero=salida.find("MOTOR_CMD,0");
   assert(primero!=std::string::npos && salida.find("MOTOR_CMD,0",primero+1)==std::string::npos);
   if(caso!="pid"){
     for(int i=0;i<40;i++)pulso(50000);
     assert(Ensayos::leerEstado()==E::Finalizado && Freno::leerAngulo()==45);
   }
 } else if(caso=="cancelar_preparacion" || caso=="cancelar_descenso"){
   if(caso=="cancelar_descenso")cortar();else comando("auto_fijo30");
   comando("cancelar");
   assert(Ensayos::leerEstado()==E::Cancelado && !Motor::estaEncendido());
   for(int i=0;i<4;i++)pulso(50000);
   assert(Ensayos::leerEstado()==E::Cancelado && Freno::leerAngulo()==45);
   assert(!Referencia::disponible());
 } else if(caso=="sin_armar"){
   cortar("auto_preparar");pulso(47000);
   assert(Ensayos::leerEstado()==E::Fallo && !Referencia::disponible());
   assert(Serial.salida.find("AUTO_SIN_ENSAYO_ARMADO")!=std::string::npos);
 } else if(caso=="armar_en_descenso"){
   cortar("auto_preparar");pulso(45000);comando("auto_fijo33");
   assert(Freno::leerAngulo()==45);pulso(47000);
   assert(Ensayos::leerEstado()==E::Fijo && Freno::leerAngulo()==33);
 } else if(caso=="sin_senal"){
   cortar();avanzar(251000);avanzar(1500000);
   assert(Ensayos::leerEstado()==E::Fallo && Freno::leerAngulo()==45);
   assert(Serial.salida.find("FALLO_MEDICION")!=std::string::npos);
 } else if(caso=="timeout_descenso"){
   cortar();for(int i=0;i<334;i++)pulso(45000);
   assert(Ensayos::leerEstado()==E::Fallo && Freno::leerAngulo()==45);
   assert(Serial.salida.find("FALLO_TIEMPO_DESCENSO")!=std::string::npos);
 } else if(caso=="pico"){
   comando("auto_fijo30");pulso(50000);pulso(50000);pulso(25000);
   assert(!Medicion::leerLectura().valida);
   assert(Ensayos::leerEstado()==E::Preparacion && Motor::estaEncendido());
   pulso(50000);pulso(40000);
   assert(Ensayos::leerEstado()==E::DescensoLibre && !Motor::estaEncendido());
 } else if(caso=="bloqueos"){
   comando("auto_pid");assert(!Motor::estaEncendido());
   comando("sensor_on");comando("auto_fijo30");assert(!Motor::estaEncendido());
   comando("sensor_off");comando("auto_fijo14");assert(!Motor::estaEncendido());
   comando("auto_fijo46");assert(!Motor::estaEncendido());
   cortar();comando("auto_fijo15");pulso(47000);
   assert(Freno::leerAngulo()==30); // La segunda orden no reemplaza lo armado.
 } else assert(false);
 std::cout<<"Secuencia automatica "<<caso<<" correcta\n";
}
