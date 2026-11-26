#include "Arduino.h"
#include "control_pid.h"
#include "ensayos.h"
#include "freno.h"
#include "motor.h"
#include "referencia.h"
#include <cassert>
#include <cmath>
#include <iostream>
uint64_t relojUs=0;
void (*interrupcion)()=nullptr;
std::vector<std::string> gpio;
std::vector<int> posiciones;
Puerto Serial;
void setup();void loop();
using E=Ensayos::Estado;
void comando(const std::string &s){Serial.entrada=s+"\n";loop();}
void avanzar(uint64_t us){
 while(us){const uint64_t d=us>20000?20000:us;relojUs+=d;us-=d;loop();}
}
void pulso(uint64_t us=50000){
 while(us>20000){relojUs+=20000;us-=20000;loop();}
 relojUs+=us;emitirMarcaPrueba();loop();
}
void preparar(){comando("preparar");pulso();pulso();}
void iniciar(int tiempo=6000){comando("tiempo"+std::to_string(tiempo));preparar();comando("pid");}
void parada(E estado){
 assert(Ensayos::leerEstado()==estado);
 assert(!Motor::estaEncendido() && Freno::leerAngulo()==45);
 assert(Freno::leerAccionAplicada()==0);
 assert(!ControlPID::leer().disponible);
}
int main(int argc,char **argv){
 assert(argc==2);const std::string caso=argv[1];
 if(caso=="reloj")relojUs=(UINT32_MAX-50ULL)*1000ULL;
 setup();
 if(caso=="bloqueado"){
   preparar();comando("pid");
   assert(Ensayos::leerEstado()==E::Preparacion);
   assert(Serial.salida.find("PID_ACTUACION_DESHABILITADA")!=std::string::npos);
 }else if(caso=="ganancias_cero"){
   preparar();comando("pid");
   assert(Ensayos::leerEstado()==E::Preparacion);
   assert(Serial.salida.find("PID_GANANCIAS_NO_CONFIGURADAS")!=std::string::npos);
 }else if(caso=="conversion"){
   assert(Freno::anguloParaAccion(0)==45 && Freno::anguloParaAccion(1)==15);
   assert(Freno::anguloParaAccion(-1)==45 && Freno::anguloParaAccion(2)==15);
   assert(Freno::anguloParaAccion(.5f)==30);
   const auto n=posiciones.size();
   assert(!Freno::aplicarAccion(NAN) && posiciones.size()==n);
   assert(Freno::aplicarAccion(1) && Freno::leerAngulo()==15);
   assert(Freno::leerAccionAplicada()==1);
   const auto m=posiciones.size();
   assert(Freno::aplicarAccion(1) && posiciones.size()==m);
   assert(Freno::aplicarAccion(.5f));
   assert(std::fabs(Freno::leerAccionAplicada()-15.0f/30)<0.001f);
 }else if(caso=="normal" || caso=="reloj" || caso=="telemetria"){
   comando("pid");assert(Ensayos::leerEstado()==E::Reposo);
   iniciar();assert(Ensayos::leerEstado()==E::Pid && !Motor::estaEncendido());
   for(int i=0;i<20;i++){pulso();assert(Freno::leerAngulo()>=15 && Freno::leerAngulo()<=45);}
   assert(Freno::leerAngulo()<45 && Freno::leerAccionAplicada()>0);
   comando("g90");comando("r");comando("motor_on");comando("fijo30");
   assert(Ensayos::leerEstado()==E::Pid && !Motor::estaEncendido());
   if(caso=="telemetria"){std::cout<<Serial.salida;return 0;}
   comando("cancelar");parada(E::Cancelado);assert(!Referencia::disponible());
 }else if(caso=="debajo_referencia"){
   iniciar();for(int i=0;i<10;i++)pulso();
   assert(Freno::leerAngulo()<45);
   pulso(200000);avanzar(20000);
   assert(Ensayos::leerEstado()==E::Pid);
   assert(ControlPID::leer().error<0 && Freno::leerAngulo()==45);
   assert(Freno::leerAccionAplicada()==0);
 }else if(caso=="medicion"){
   iniciar();for(int i=0;i<10;i++)pulso();
   pulso(25000);assert(!ControlPID::leer().disponible);
   assert(Freno::leerAngulo()==45 && Freno::leerAccionAplicada()==0);
   pulso();avanzar(20000);assert(ControlPID::leer().disponible);
   assert(Ensayos::leerEstado()==E::Pid);
   avanzar(2000000);parada(E::Fallo);
   assert(Serial.salida.find("FALLO_MEDICION")!=std::string::npos);
 }else if(caso=="tiempo"){
   iniciar();relojUs+=200000;loop();parada(E::Fallo);
   assert(Serial.salida.find("PID_FALLO_TIEMPO")!=std::string::npos);
   assert(Serial.salida.find("PID_RETRASO_US,200000")!=std::string::npos);
 }else if(caso=="sin_confirmacion"){
   iniciar(1000);for(int i=0;i<20;i++)pulso();
   assert(Ensayos::leerEstado()==E::Pid); // No basta terminar el reloj.
   for(int i=0;i<40;i++)pulso();
   parada(E::Fallo);
   assert(Serial.salida.find("PID_FIN_NO_CONFIRMADO")!=std::string::npos);
 }else if(caso=="fin_baja"){
   iniciar(1000);pulso(750000);avanzar(600000);parada(E::Finalizado);
   assert(Referencia::evaluar(millis())==0);
   assert(Serial.salida.find("ENSAYO_PID_FIN_BAJA_RPM")!=std::string::npos);
 }else assert(false);
 std::cout<<caso<<" correcto\n";
}
