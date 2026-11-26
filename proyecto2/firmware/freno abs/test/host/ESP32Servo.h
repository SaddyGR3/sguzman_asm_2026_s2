#pragma once
#include <vector>
extern std::vector<int> posiciones;
struct Servo {
 void setPeriodHertz(int){}
 void attach(int,int=500,int=2400){}
 void write(int v){posiciones.push_back(v);}
};
