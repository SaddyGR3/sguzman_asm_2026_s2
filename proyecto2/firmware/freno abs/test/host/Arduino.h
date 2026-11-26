#pragma once
#include <algorithm>
#include <cstdint>
#include <cstddef>
#include <iomanip>
#include <sstream>
#include <string>
#include <vector>
#define IRAM_ATTR
constexpr int HIGH=1, LOW=0, INPUT=1, OUTPUT=2, FALLING=3, CHANGE=4;
using std::min;
using std::max;
extern uint64_t relojUs;
extern void (*interrupcion)();
extern std::vector<std::string> gpio;
inline uint32_t micros(){return static_cast<uint32_t>(relojUs);}
inline uint32_t millis(){return static_cast<uint32_t>(relojUs/1000U);}
inline void noInterrupts(){}
inline void interrupts(){}
inline int digitalPinToInterrupt(int p){return p;}
inline int &nivelSensorPrueba(){static int nivel=HIGH;return nivel;}
inline int &modoInterrupcionPrueba(){static int modo=FALLING;return modo;}
inline int digitalRead(int){return nivelSensorPrueba();}
inline void attachInterrupt(int,void(*f)(),int modo){interrupcion=f;modoInterrupcionPrueba()=modo;}
inline void pinMode(int p,int v){gpio.push_back("modo "+std::to_string(p)+" "+std::to_string(v));}
inline void digitalWrite(int p,int v){gpio.push_back("nivel "+std::to_string(p)+" "+std::to_string(v));}
struct Puerto {
 std::string entrada, salida;
 void begin(int){}
 int available(){return entrada.size();}
 int read(){auto c=entrada.front();entrada.erase(0,1);return c;}
 template<class T> void print(T v){std::ostringstream o;o<<v;salida+=o.str();}
 void print(float v,int n){std::ostringstream o;o<<std::fixed<<std::setprecision(n)<<v;salida+=o.str();}
 template<class T> void println(T v){print(v);salida+='\n';}
 void println(){salida+='\n';}
};
extern Puerto Serial;

// Una marca completa de 200 us, terminando en el tiempo del caso de prueba.
// Entrega ambos flancos porque el detector de produccion usa CHANGE.
inline void emitirMarcaPrueba(){
 const uint64_t final=relojUs;
 relojUs=final-200; nivelSensorPrueba()=LOW; interrupcion();
 relojUs=final; nivelSensorPrueba()=HIGH; interrupcion();
}
