#include "Arduino.h"
#include "configuracion.h"
#include "control_pid.h"
#include "ensayos.h"
#include "freno.h"
#include "motor.h"
#include <cassert>
#include <iostream>
uint64_t relojUs=0;
void (*interrupcion)()=nullptr;
std::vector<std::string> gpio;
std::vector<int> posiciones;
Puerto Serial;
void setup();void loop();
void comando(const std::string &s){Serial.entrada=s+"\n";loop();}
void esperar(uint32_t us){while(us){auto d=us>20000?20000:us;relojUs+=d;us-=d;loop();}}
void marca(uint32_t periodo=24000){esperar(periodo-200);relojUs+=200;emitirMarcaPrueba();loop();}
int main(int argc,char **argv){
 assert(argc==2);
 const std::string caso=argv[1];
 assert(Configuracion::marcasPorVuelta==2);
 assert(Configuracion::anguloMinimoEnsayo==25);
 assert(Configuracion::actuacionPIDHabilitada && Configuracion::pidKp==0.005f);
 assert(Configuracion::pidKi==0.004f && Configuracion::pidKd==0);
 setup();comando(caso=="sin_precarga" ? "tiempo20000" : "tiempo6000");if(caso=="exponencial") comando("curva_exponencial");
 comando("preparar");marca();marca();marca();comando("pid");
 assert(Ensayos::leerEstado()==Ensayos::Estado::Pid && !Motor::estaEncendido());
 if(caso=="sin_precarga") {
   assert(Freno::leerAngulo()==45);
   assert(Serial.salida.find("PID_PRECARGA_X1000000,0")!=std::string::npos);
 }else if(caso=="exponencial") {
   assert(Freno::leerAngulo()==31);
   assert(Serial.salida.find("PID_PRECARGA_X1000000,700000")!=std::string::npos);
   assert(Serial.salida.find("REFERENCIA_TIPO,1")!=std::string::npos);
   assert(Serial.salida.find("REFERENCIA_FORMA_X1000,2000")!=std::string::npos);
   assert(Serial.salida.find("REFERENCIA_EXPONENCIAL_MS,6000")!=std::string::npos);
   comando("curva_lineal");
   assert(Serial.salida.find("REFERENCIA_BLOQUEADA_ENSAYO")!=std::string::npos);
 }else {
   assert(Freno::leerAngulo()==34);
   assert(Serial.salida.find("PID_PRECARGA_X1000000,550000")!=std::string::npos);
 }
 for(int i=0;i<35;++i){marca();assert(Freno::leerAngulo()>=25 && Freno::leerAngulo()<=45);}
 assert(Freno::leerAngulo()<45 && ControlPID::leer().disponible);
 assert(Serial.salida.find("PID_KP_X1000000,5000")!=std::string::npos);
 assert(Serial.salida.find("PID_KI_X1000000,4000")!=std::string::npos);
 assert(Serial.salida.find("MARCAS_POR_VUELTA,2")!=std::string::npos);
 if(caso=="inicio_cancelacion" || caso=="sin_precarga" || caso=="exponencial"){
   comando("cancelar");assert(Ensayos::leerEstado()==Ensayos::Estado::Cancelado);
 }else if(caso=="liberar"){
   marca(80000);esperar(20000);
   assert(ControlPID::leer().error<0 && Freno::leerAngulo()==45);
   comando("cancelar");
 }else if(caso=="perdida"){
   esperar(2500000);
   assert(Ensayos::leerEstado()==Ensayos::Estado::Fallo);
   assert(Serial.salida.find("FALLO_MEDICION")!=std::string::npos);
 }else assert(false);
 assert(!Motor::estaEncendido() && Freno::leerAngulo()==45);
 std::cout<<"Configuracion actual dos marcas y PI inicial, "<<caso<<" correcto\n";
}
