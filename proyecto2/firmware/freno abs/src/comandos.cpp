#include <Arduino.h>
#include <stdlib.h>
#include <string.h>
#include "comandos.h"
#include "ensayos.h"
#include "configuracion.h"
#include "freno.h"
#include "medicion.h"
#include "motor.h"
#include "registro.h"
#include "referencia.h"
#include "control_pid.h"

namespace Comandos {
using namespace Configuracion;
namespace {
char lineaComando[24];
size_t longitudComando = 0;
bool descartandoLinea = false;

bool leerEntero(const char *texto, int &valor) {
  if (*texto == '\0') {
    return false;
  }
  char *final = nullptr;
  const long numero = strtol(texto, &final, 10);
  if (final == texto || *final != '\0' || numero < -32768 || numero > 32767) {
    return false;
  }
  valor = static_cast<int>(numero);
  return true;
}

void procesarComando(const char *comando) {
  // Cancelar y consultar siguen disponibles mientras el ensayo gobierna actuadores.
  if (strcmp(comando, "cancelar") == 0) {
    Ensayos::cancelar();
    return;
  }
  if (strcmp(comando, "estado") == 0) {
    Ensayos::informarEstado();
    return;
  }
  if (strcmp(comando, "sensor_on") == 0 || strcmp(comando, "sensor_off") == 0) {
    if (Ensayos::estaActivo() || Motor::estaEncendido()) {
      Registro::emitirEvento("SENSOR_REQUIERE_REPOSO", 0, micros());
    } else {
      Medicion::configurarDiagnostico(strcmp(comando, "sensor_on") == 0);
    }
    return;
  }
  if (Medicion::diagnosticoActivo() &&
      (strcmp(comando, "preparar") == 0 || strcmp(comando, "motor_on") == 0)) {
    Registro::emitirEvento("SENSOR_DIAGNOSTICO_ACTIVO", 0, micros());
    return;
  }
  if (strcmp(comando, "motor_off") == 0 && Ensayos::estaActivo()) {
    Ensayos::cancelar();
    return;
  }
  if (strcmp(comando, "auto_preparar") == 0 || strcmp(comando, "auto_pid") == 0 ||
      strncmp(comando, "auto_fijo", 9) == 0) {
    if (Medicion::diagnosticoActivo()) {
      Registro::emitirEvento("SENSOR_DIAGNOSTICO_ACTIVO", 0, micros());
      return;
    }
    if (strcmp(comando, "auto_preparar") == 0) Ensayos::prepararAutomatico();
    else if (strcmp(comando, "auto_pid") == 0) Ensayos::armarPIDAutomatico();
    else {
      int angulo;
      if (leerEntero(comando + 9, angulo)) Ensayos::armarFijoAutomatico(angulo);
      else Registro::emitirEvento("COMANDO_INVALIDO", 0, micros());
    }
    return;
  }
  if (strncmp(comando, "fijo", 4) == 0) {
    int angulo;
    if (leerEntero(comando + 4, angulo)) {
      Ensayos::iniciarFijo(angulo);
    } else {
      Registro::emitirEvento("COMANDO_INVALIDO", 0, micros());
    }
    return;
  }
  if (strcmp(comando, "pid") == 0) {
    Ensayos::iniciarPID();
    return;
  }
  if (Ensayos::estaActivo() && strcmp(comando, "?") != 0 &&
      strcmp(comando, "v") != 0) {
    Registro::emitirEvento("COMANDO_BLOQUEADO_ENSAYO", 0, micros());
    return;
  }
  if (strcmp(comando, "preparar") == 0) {
    Ensayos::preparar();
    return;
  }
  if (strncmp(comando, "tiempo", 6) == 0) {
    int duracion;
    if (leerEntero(comando + 6, duracion)) {
      Ensayos::configurarDuracion(duracion);
    } else {
      Registro::emitirEvento("COMANDO_INVALIDO", 0, micros());
    }
    return;
  }
  if (strcmp(comando, "r") == 0) {
    Medicion::reiniciar();
    Referencia::reiniciar();
    ControlPID::reiniciar();
    Registro::reiniciar();
  } else if (strcmp(comando, "+") == 0) {
    Freno::fijarAngulo(min(Freno::leerAngulo() + Freno::leerPaso(), anguloMaximo));
  } else if (strcmp(comando, "-") == 0) {
    Freno::fijarAngulo(max(Freno::leerAngulo() - Freno::leerPaso(), anguloMinimo));
  } else if (comando[0] == 'g') {
    int angulo;
    if (leerEntero(comando + 1, angulo)) {
      Freno::fijarAngulo(angulo);
    } else {
      Registro::emitirEvento("COMANDO_INVALIDO", 0, micros());
    }
  } else if (comando[0] == 'p') {
    int paso;
    if (leerEntero(comando + 1, paso) && paso >= 1 && paso <= 10) {
      Freno::fijarPaso(paso);
    } else {
      Registro::emitirEvento("PASO_INVALIDO", 0, micros());
    }
  } else if (strcmp(comando, "m") == 0) {
    // Marca manual aproximada: pulsar al apagar la fuente del motor.
    Registro::emitirEvento("MOTOR_OFF_MANUAL", 1, micros());
  } else if (strcmp(comando, "c") == 0) {
    Registro::emitirEvento("CONTACTO_INICIAL", Freno::leerAngulo(), micros());
  } else if (strcmp(comando, "f") == 0) {
    Registro::emitirEvento("CONTACTO_UTIL", Freno::leerAngulo(), micros());
  } else if (strcmp(comando, "v") == 0) {
    uint32_t pulsos;
    uint32_t rechazados;
    Medicion::leerConteos(pulsos, rechazados);
    Registro::emitirEvento("PULSOS", static_cast<int>(pulsos), micros());
    Registro::emitirEvento("PULSOS_RECHAZADOS", static_cast<int>(rechazados), micros());
  } else if (strcmp(comando, "0") == 0) {
    Freno::iniciarRampa();
  } else if (strcmp(comando, "s") == 0) {
    Freno::detenerRampa();
  } else if (strcmp(comando, "90") == 0) {
    Freno::fijarAngulo(90);
  } else if (strcmp(comando, "motor_on") == 0) {
    Motor::establecerEncendido(true);
  } else if (strcmp(comando, "motor_off") == 0) {
    Motor::establecerEncendido(false);
  } else if (strcmp(comando, "?") == 0) {
    Registro::imprimirAyuda();
  } else if (*comando != '\0') {
    Registro::emitirEvento("COMANDO_INVALIDO", 0, micros());
  }
}
}

void leerComandos() {
  while (Serial.available() > 0) {
    const char recibido = static_cast<char>(Serial.read());
    if (recibido == '\r' || recibido == '\n') {
      if (descartandoLinea) {
        descartandoLinea = false;
        longitudComando = 0;
        continue;
      }
      if (longitudComando > 0) {
        lineaComando[longitudComando] = '\0';
        procesarComando(lineaComando);
        longitudComando = 0;
      }
    } else if (descartandoLinea) {
      continue;
    } else if (longitudComando < sizeof(lineaComando) - 1) {
      lineaComando[longitudComando++] = recibido;
    } else {
      longitudComando = 0;
      descartandoLinea = true;
      Registro::emitirEvento("COMANDO_MUY_LARGO", 0, micros());
    }
  }
}
}
