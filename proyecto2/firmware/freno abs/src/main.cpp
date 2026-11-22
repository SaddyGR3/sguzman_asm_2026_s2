#include <Arduino.h>
#include <ESP32Servo.h>
#include <stdlib.h>
#include <string.h>

Servo servo;

constexpr int pinServo = 18;
constexpr int pinSensor = 34;
constexpr int marcasPorVuelta = 1;
constexpr int anguloMinimo = 0;
constexpr int anguloMaximo = 90;

// Se conserva la velocidad del comando gradual "0" para calibracion.
constexpr unsigned long velocidadNormal = 11;
constexpr unsigned long velocidadLenta = 18;
constexpr int puntoDesaceleracion = 20;

// Con una marca/vuelta, 20 ms permiten hasta 3000 RPM. En las dos referencias
// las RPM estables no superan 1800 y los picos falsos implican 3-16 ms.
constexpr uint32_t tiempoMinimoPulsoUs = 20000;
// Este limite solo indica cuándo mostrar RPM=0; no invalida vueltas lentas.
constexpr uint32_t tiempoSinPulsoParaCeroUs = 1000000;
constexpr uint32_t intervaloRegistroMs = 100;

int posicionActual = 90;
int pasoGrados = 1;
bool moviendo = false;
bool inicioAnunciado = false;
uint32_t tiempoAnteriorServoMs = 0;
uint32_t tiempoAnteriorRegistroMs = 0;

volatile uint32_t tiempoPulsoAnteriorUs = 0;
volatile uint32_t periodoVueltaUs = 0;
volatile uint32_t ultimaDeteccionUs = 0;
volatile uint32_t inicioRpmUs = 0;
volatile bool inicioDisponible = false;
volatile uint32_t conteoPulsos = 0;
volatile uint32_t conteoPulsosRechazados = 0;

char lineaComando[24];
size_t longitudComando = 0;

void IRAM_ATTR detectarMarca() {
  const uint32_t ahora = micros();
  if (ahora - ultimaDeteccionUs <= tiempoMinimoPulsoUs) {
    ++conteoPulsosRechazados;
    return;
  }

  if (tiempoPulsoAnteriorUs != 0) {
    const uint32_t nuevoPeriodo = ahora - tiempoPulsoAnteriorUs;
    periodoVueltaUs = nuevoPeriodo;
    if (!inicioDisponible) {
      // t=0 es la segunda marca aceptada, incluso al girar a mano lentamente.
      inicioRpmUs = ahora;
      inicioDisponible = true;
    }
  }

  tiempoPulsoAnteriorUs = ahora;
  ultimaDeteccionUs = ahora;
  ++conteoPulsos;
}

bool leerInicio(uint32_t &inicio) {
  noInterrupts();
  const bool disponible = inicioDisponible;
  inicio = inicioRpmUs;
  interrupts();
  return disponible;
}

uint32_t tiempoRelativoMs(uint32_t ahoraUs, uint32_t inicioUs) {
  return (ahoraUs - inicioUs) / 1000U;
}

float calcularRPM(uint32_t ahoraUs) {
  noInterrupts();
  const uint32_t periodo = periodoVueltaUs;
  const uint32_t ultima = ultimaDeteccionUs;
  interrupts();

  if (periodo == 0 || ahoraUs - ultima > tiempoSinPulsoParaCeroUs) {
    return 0.0f;
  }
  return 60000000.0f / (static_cast<float>(periodo) * marcasPorVuelta);
}

void emitirEvento(const char *tipo, int valor, uint32_t instanteUs) {
  uint32_t inicio;
  Serial.print("#EVENT,");
  if (leerInicio(inicio)) {
    Serial.print(tiempoRelativoMs(instanteUs, inicio));
  } else {
    Serial.print(-1);  // Todavia no existe un origen de RPM.
  }
  Serial.print(',');
  Serial.print(tipo);
  Serial.print(',');
  Serial.println(valor);
}

void fijarAngulo(int nuevoAngulo) {
  if (nuevoAngulo < anguloMinimo || nuevoAngulo > anguloMaximo) {
    emitirEvento("ANGULO_INVALIDO", nuevoAngulo, micros());
    return;
  }

  moviendo = false;
  posicionActual = nuevoAngulo;
  const uint32_t instanteUs = micros();
  servo.write(posicionActual);
  emitirEvento("SERVO_CMD", posicionActual, instanteUs);
}

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
  if (strcmp(comando, "r") == 0) {
    noInterrupts();
    tiempoPulsoAnteriorUs = 0;
    periodoVueltaUs = 0;
    ultimaDeteccionUs = 0;
    inicioRpmUs = 0;
    inicioDisponible = false;
    conteoPulsos = 0;
    conteoPulsosRechazados = 0;
    interrupts();
    inicioAnunciado = false;
    Serial.println("#EVENT,-1,REINICIO,1");
  } else if (strcmp(comando, "+") == 0) {
    fijarAngulo(min(posicionActual + pasoGrados, anguloMaximo));
  } else if (strcmp(comando, "-") == 0) {
    fijarAngulo(max(posicionActual - pasoGrados, anguloMinimo));
  } else if (comando[0] == 'g') {
    int angulo;
    if (leerEntero(comando + 1, angulo)) {
      fijarAngulo(angulo);
    } else {
      emitirEvento("COMANDO_INVALIDO", 0, micros());
    }
  } else if (comando[0] == 'p') {
    int paso;
    if (leerEntero(comando + 1, paso) && paso >= 1 && paso <= 10) {
      pasoGrados = paso;
      emitirEvento("PASO_GRADOS", pasoGrados, micros());
    } else {
      emitirEvento("PASO_INVALIDO", 0, micros());
    }
  } else if (strcmp(comando, "m") == 0) {
    // Marca manual aproximada: pulsar al apagar la fuente del motor.
    emitirEvento("MOTOR_OFF_MANUAL", 1, micros());
  } else if (strcmp(comando, "c") == 0) {
    emitirEvento("CONTACTO_INICIAL", posicionActual, micros());
  } else if (strcmp(comando, "f") == 0) {
    emitirEvento("CONTACTO_UTIL", posicionActual, micros());
  } else if (strcmp(comando, "v") == 0) {
    noInterrupts();
    const uint32_t pulsos = conteoPulsos;
    const uint32_t rechazados = conteoPulsosRechazados;
    interrupts();
    emitirEvento("PULSOS", static_cast<int>(pulsos), micros());
    emitirEvento("PULSOS_RECHAZADOS", static_cast<int>(rechazados), micros());
  } else if (strcmp(comando, "0") == 0) {
    moviendo = true;
    tiempoAnteriorServoMs = millis();
    emitirEvento("RAMPA_INICIO", 0, micros());
  } else if (strcmp(comando, "s") == 0) {
    moviendo = false;
    emitirEvento("RAMPA_DETENIDA", posicionActual, micros());
  } else if (strcmp(comando, "90") == 0) {
    fijarAngulo(90);
  } else if (strcmp(comando, "?") == 0) {
    Serial.println("#HELP,+/-: paso; pN: paso 1..10; gN: angulo directo 0..90; c/f: contacto; m: fuente apagada; v: pulsos y rechazados; r: reiniciar reloj; 0: rampa; s: detener; 90: volver");
  } else if (*comando != '\0') {
    emitirEvento("COMANDO_INVALIDO", 0, micros());
  }
}

void leerComandos() {
  while (Serial.available() > 0) {
    const char recibido = static_cast<char>(Serial.read());
    if (recibido == '\r' || recibido == '\n') {
      if (longitudComando > 0) {
        lineaComando[longitudComando] = '\0';
        procesarComando(lineaComando);
        longitudComando = 0;
      }
    } else if (longitudComando < sizeof(lineaComando) - 1) {
      lineaComando[longitudComando++] = recibido;
    } else {
      longitudComando = 0;
      emitirEvento("COMANDO_MUY_LARGO", 0, micros());
    }
  }
}

void actualizarRampa() {
  if (!moviendo) {
    return;
  }

  const uint32_t intervalo = posicionActual > puntoDesaceleracion
                                 ? velocidadNormal : velocidadLenta;
  if (millis() - tiempoAnteriorServoMs < intervalo) {
    return;
  }
  tiempoAnteriorServoMs = millis();
  if (posicionActual > anguloMinimo) {
    --posicionActual;
    servo.write(posicionActual);
  } else {
    moviendo = false;
    emitirEvento("RAMPA_FIN", posicionActual, micros());
  }
}

void registrarMedicion() {
  uint32_t inicio;
  if (!leerInicio(inicio)) {
    return;  // No se inventan ceros antes de la primera RPM valida.
  }

  if (!inicioAnunciado) {
    inicioAnunciado = true;
    tiempoAnteriorRegistroMs = millis() - intervaloRegistroMs;
    Serial.println("#EVENT,0,RPM_INICIO,1");
  }

  const uint32_t ahoraMs = millis();
  if (ahoraMs - tiempoAnteriorRegistroMs < intervaloRegistroMs) {
    return;
  }
  tiempoAnteriorRegistroMs = ahoraMs;
  const uint32_t ahoraUs = micros();

  Serial.print(tiempoRelativoMs(ahoraUs, inicio));
  Serial.print(',');
  Serial.print(calcularRPM(ahoraUs), 2);
  Serial.print(',');
  Serial.println(posicionActual);
}

void setup() {
  Serial.begin(115200);
  servo.setPeriodHertz(50);
  servo.attach(pinServo, 500, 2400);
  servo.write(posicionActual);
  pinMode(pinSensor, INPUT);
  attachInterrupt(digitalPinToInterrupt(pinSensor), detectarMarca, FALLING);

  Serial.println("#READY: tiempo desde primera RPM valida; movimientos 0..90 grados");
  Serial.println("#HELP,+/-: paso; pN: paso 1..10; gN: angulo directo 0..90; c/f: contacto; m: fuente apagada; v: pulsos y rechazados; r: reiniciar reloj; 0: rampa; s: detener; 90: volver");
  Serial.println("tiempo_ms,rpm,servo_cmd_grados");
}

void loop() {
  leerComandos();
  actualizarRampa();
  registrarMedicion();
}
