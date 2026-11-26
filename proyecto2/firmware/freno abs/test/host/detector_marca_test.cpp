#include "detector_marca.h"
#include <cassert>
#include <cstdint>
#include <iostream>
int main(){
 DetectorMarca d(100,100); uint32_t inicio=0;
 d.reiniciar(false,0);
 assert(!d.actualizar(true,1000,inicio));
 assert(d.actualizar(false,1200,inicio) && inicio==1000);
 assert(!d.actualizar(false,50000,inicio));
 // Pulso breve en la zona libre. Se descarta.
 assert(!d.actualizar(true,60000,inicio));
 assert(!d.actualizar(false,60010,inicio));
 // Una marca larga con una excursion breve a la zona libre no se duplica.
 assert(!d.actualizar(true,70000,inicio));
 assert(d.actualizar(false,70200,inicio));
 assert(!d.actualizar(true,70210,inicio));
 assert(!d.actualizar(false,71000,inicio));
 assert(!d.actualizar(true,80000,inicio));
 assert(d.actualizar(false,80200,inicio) && inicio==80000);
 // Arrancar dentro de una marca no cuenta una fraccion como vuelta.
 d.reiniciar(true,0);
 assert(!d.actualizar(false,5000,inicio));
 assert(!d.actualizar(true,10000,inicio));
 assert(d.actualizar(false,10200,inicio));
 // 100 marcas a aproximadamente 1800 RPM, estrechas y con notificaciones repetidas.
 d.reiniciar(false,0); int cuentas=0;
 for(uint32_t i=1;i<=100;i++){
   const uint32_t t=i*33333;
   assert(!d.actualizar(true,t,inicio));
   assert(!d.actualizar(true,t+10,inicio));
   if(d.actualizar(false,t+200,inicio))++cuentas;
   assert(inicio==t);
   assert(!d.actualizar(false,t+400,inicio));
 }
 assert(cuentas==100);
 // Giro lento y marca ancha. Un conteo, sin depender de la velocidad de giro.
 d.reiniciar(false,0);
 assert(!d.actualizar(true,2000000,inicio));
 assert(!d.actualizar(true,2500000,inicio));
 assert(d.actualizar(false,3000000,inicio) && inicio==2000000);
 // Cruce del limite del reloj de microsegundos.
 d.reiniciar(false,UINT32_MAX-500);
 assert(!d.actualizar(true,UINT32_MAX-150,inicio));
 assert(d.actualizar(false,100,inicio) && inicio==UINT32_MAX-150);
 std::cout<<"Detector de marcas completas, ruido breve, 1800 RPM y reloj correctos\n";
}
