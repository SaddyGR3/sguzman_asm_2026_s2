#include "pid.h"
#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>
#include <iostream>
using PID::Controlador;
using PID::Parametros;
using PID::Estado;
bool cerca(float a,float b){return std::fabs(a-b)<0.0001f;}
Parametros base(float kp=0,float ki=0,float kd=0) {
  return {kp,ki,kd,0.1f,20000,100000};
}
int main() {
  Controlador c;
  assert(!c.precargarIntegral(.55f));
  assert(!c.actualizar(1000,{1200,0,true},0));
  assert(c.leer().estado==Estado::SinConfigurar);
  assert(c.configurar(base(.002f)));
  assert(c.actualizar(1000,{1200,0,true},0));
  assert(cerca(c.leer().p,.4f) && cerca(c.leer().limitada,.4f));
  assert(c.leer().dtUs==0 && c.leer().i==0 && c.leer().d==0);
  assert(!c.actualizar(1000,{1200,0,true},19999));
  assert(c.actualizar(1000,{1100,20000,true},20000));
  assert(cerca(c.leer().limitada,.2f));
  assert(c.actualizar(1000,{2000,40000,true},40000));
  assert(c.leer().solicitada==2 && c.leer().limitada==1);

  assert(c.configurar(base(0,.1f)));
  c.actualizar(1000,{1001,0,true},0);
  c.actualizar(1000,{1001,100000,true},100000);
  assert(cerca(c.leer().i,.01f));
  c.actualizar(1000,{1001,200000,true},200000);
  assert(cerca(c.leer().i,.02f));

  assert(c.configurar(base(.01f,.1f)));
  for(uint32_t t=0;t<=1000000;t+=20000) {
    assert(c.actualizar(1000,{1200,t,true},t));
    assert(c.leer().limitada==1 && c.leer().i==0);
  }
  c.actualizar(1000,{1010,1020000,true},1020000);
  assert(cerca(c.leer().i,.02f) && cerca(c.leer().limitada,.12f));
  c.actualizar(1000,{999,1040000,true},1040000);
  assert(c.leer().liberacion && c.leer().limitada==0 && cerca(c.leer().i,.018f));
  // Una desviacion pequena libera sin borrar la integral acumulada.
  c.actualizar(1000,{1000,1060000,true},1060000);
  assert(cerca(c.leer().i,.018f));
  c.actualizar(1000,{1001,1080000,true},1080000);
  assert(cerca(c.leer().i,.020f) && cerca(c.leer().limitada,.030f));
  // El error negativo puede descargar hasta cero, incluso con P + I negativo.
  c.actualizar(1000,{900,1100000,true},1100000);
  assert(c.leer().liberacion && c.leer().limitada==0 && c.leer().i==0);
  c.actualizar(1000,{900,1120000,true},1120000);
  assert(c.leer().limitada==0 && c.leer().i==0);
  // Cancelar o invalidar una medicion sigue borrando la memoria del controlador.
  c.actualizar(1000,{1010,1140000,true},1140000);
  assert(c.leer().i>0);
  c.reiniciar();
  assert(!c.leer().disponible);
  c.actualizar(1000,{1000,1160000,true},1160000);
  assert(c.leer().i==0);
  c.actualizar(1000,{1010,1180000,true},1180000);
  assert(c.leer().i>0);
  assert(!c.actualizar(1000,{NAN,1200000,false},1200000));
  c.actualizar(1000,{1000,1220000,true},1220000);
  assert(c.leer().i==0);

  assert(c.configurar(base(0,0,.001f)));
  c.actualizar(1000,{1000,0,true},0);
  c.actualizar(500,{1000,0,true},20000);
  assert(c.leer().d==0); // Un cambio de referencia no dispara D.
  c.actualizar(1000,{1050,50000,true},50000);
  assert(cerca(c.leer().d,1.0f/3.0f));
  c.actualizar(1000,{1050,50000,true},70000);
  assert(cerca(c.leer().d,1.0f/3.0f)); // No derivar la misma muestra de nuevo.
  c.actualizar(1000,{1000,100000,true},100000);
  assert(c.leer().d<0 && c.leer().limitada==0);

  assert(!c.actualizar(1000,{NAN,100001,false},100001));
  assert(!c.leer().disponible && c.leer().estado==Estado::MedicionInvalida);
  c.actualizar(1000,{1100,120000,true},120000);
  assert(c.leer().d==0 && c.leer().i==0);
  assert(!c.actualizar(NAN,{1100,140000,true},140000));
  assert(c.leer().estado==Estado::EntradaInvalida);
  c.actualizar(1000,{1100,160000,true},160000);
  assert(!c.actualizar(1000,{1100,150000,true},180000));
  assert(c.leer().estado==Estado::MedicionInvalida);
  assert(!c.actualizar(1000,{1100,200001,true},200000));

  assert(c.configurar(base(.002f)));
  c.actualizar(1000,{1200,0,true},0);
  assert(!c.actualizar(1000,{1200,200000,true},200000));
  assert(c.leer().estado==Estado::TiempoExcedido && c.leer().omitidos==9);
  assert(c.leer().dtUs==200000 && !c.leer().disponible);
  c.actualizar(1000,{1200,220000,true},220000);
  assert(c.leer().omitidos==9 && c.leer().dtUs==0);
  c.reiniciar();assert(c.leer().omitidos==0 && !c.leer().disponible);

  assert(c.configurar(base(.002f)));
  uint32_t t=UINT32_MAX-10000U;
  c.actualizar(1000,{1200,t,true},t);
  t+=20000U;
  assert(c.actualizar(1000,{1100,t,true},t));
  assert(c.leer().dtUs==20000 && cerca(c.leer().limitada,.2f));

  auto p=base();p.kp=-1;assert(!c.configurar(p));
  p=base();p.ki=NAN;assert(!c.configurar(p));
  p=base();p.kd=INFINITY;assert(!c.configurar(p));
  p=base();p.tauDerivadaS=0;assert(!c.configurar(p));
  p=base();p.periodoUs=0;assert(!c.configurar(p));
  p=base();p.intervaloMaximoUs=1;assert(!c.configurar(p));
  p=base(std::numeric_limits<float>::max());assert(c.configurar(p));
  assert(!c.actualizar(0,{std::numeric_limits<float>::max(),0,true},0));
  assert(c.leer().estado==Estado::ErrorNumerico);

  // El primer calculo puede arrancar con accion aprendida sin esperar al error.
  assert(c.configurar(base(.005f,.004f)));
  assert(!c.precargarIntegral(NAN) && !c.precargarIntegral(-.1f) && !c.precargarIntegral(1.1f));
  assert(c.precargarIntegral(.55f));
  assert(c.actualizar(1300,{1300,0,true},0));
  assert(cerca(c.leer().i,.55f) && cerca(c.leer().limitada,.55f));
  assert(!c.precargarIntegral(.8f));
  c.actualizar(1300,{1290,20000,true},20000);
  assert(c.leer().liberacion && c.leer().limitada==0 && c.leer().i<.55f);
  c.reiniciar();c.actualizar(1300,{1300,40000,true},40000);
  assert(c.leer().i==0 && c.leer().limitada==0);

  // Simulacion didactica de seguimiento para verificar el sentido de la accion.
  // No es el modelo de la maqueta ni produce ganancias finales.
  auto simular=[](bool usarPID) {
    Controlador pid;assert(pid.configurar(base(.01f,.001f)));
    float rpm=1200, errorAcumulado=0;
    for(uint32_t paso=0;paso<250;paso++) {
      const uint32_t us=paso*20000U;
      const float referencia=1200*(1.0f-paso/250.0f);
      pid.actualizar(referencia,{rpm,us,true},us);
      const float u=usarPID ? pid.leer().limitada : 0;
      errorAcumulado+=std::fabs(rpm-referencia)*.02f;
      rpm-=.02f*(.05f*rpm+300*u);
      if(rpm<0)rpm=0;
    }
    return errorAcumulado;
  };
  assert(simular(true)<simular(false));
  std::cout<<"PID P/I/D, limites, anti-windup, temporizacion, datos invalidos y simulacion correctos\n";
}
