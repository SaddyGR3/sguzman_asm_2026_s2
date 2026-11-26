#include "Arduino.h"
#include "control_pid.h"
#include "ensayos.h"
#include "freno.h"
#include "motor.h"
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
void pulso(){relojUs+=50000;interrupcion();loop();}
int main(){
 setup();comando("tiempo6000");comando("preparar");pulso();pulso();
 comando("fijo47");
 const auto movimientos=posiciones.size();
 bool pidPideFrenar=false;
 for(int i=0;i<40;i++){
   pulso();
   const auto &r=ControlPID::leer();
   assert(r.disponible && r.limitada>=0 && r.limitada<=1);
   pidPideFrenar=pidPideFrenar || r.limitada>0;
   assert(!Motor::estaEncendido() && Freno::leerAngulo()==47);
   assert(posiciones.size()==movimientos);
 }
 assert(pidPideFrenar);
 std::cout<<Serial.salida;
 comando("cancelar");
 assert(!ControlPID::leer().disponible && Freno::leerAngulo()==90);
}
