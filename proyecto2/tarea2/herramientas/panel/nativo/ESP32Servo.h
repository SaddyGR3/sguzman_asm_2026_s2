#pragma once
// Sustituye exclusivamente la salida fisica del servo durante la simulacion.
class Servo {
 public:
  void setPeriodHertz(int) {}
  void attach(int, int, int) {}
  void write(int) {}
};
