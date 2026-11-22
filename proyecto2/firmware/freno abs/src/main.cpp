#include <Arduino.h>
#include <ESP32Servo.h>

// ====================================
// CONFIGURACION DEL SERVO
// ====================================

Servo servo;

const int pinServo = 18;

int posicionActual = 90;
bool moviendo = false;

// Milisegundos por grado
const unsigned long velocidadNormal = 11;
const unsigned long velocidadLenta = 18;

const int puntoDesaceleracion = 20;

unsigned long tiempoAnteriorServo = 0;


// ====================================
// CONFIGURACION DEL SENSOR KY-033
// ====================================

const int pinSensor = 34;

// Una marca negra por revolucion
const int marcasPorVuelta = 1;

// Variables utilizadas por la interrupcion
volatile unsigned long tiempoPulsoAnterior = 0;
volatile unsigned long periodoVuelta = 0;
volatile unsigned long ultimaDeteccion = 0;

// Rechaza pulsos extremadamente cercanos
const unsigned long tiempoMinimoPulso = 3000; // microsegundos

// Intervalo para imprimir datos
const unsigned long intervaloRegistro = 200; // milisegundos

unsigned long tiempoAnteriorRegistro = 0;


// ====================================
// INTERRUPCION DEL KY-033
// ====================================

void IRAM_ATTR detectarMarca() {

  unsigned long ahora = micros();

  if (ahora - ultimaDeteccion > tiempoMinimoPulso) {

    if (tiempoPulsoAnterior != 0) {

      periodoVuelta = ahora - tiempoPulsoAnterior;
    }

    tiempoPulsoAnterior = ahora;
    ultimaDeteccion = ahora;
  }
}


// ====================================
// CALCULAR RPM
// ====================================

float calcularRPM() {

  unsigned long periodo;
  unsigned long ultima;

  noInterrupts();

  periodo = periodoVuelta;
  ultima = ultimaDeteccion;

  interrupts();

  // Si todavia no hay dos pulsos, RPM = 0
  if (periodo == 0 || ultima == 0) {
    return 0;
  }

  // Si transcurrio demasiado tiempo sin pulsos,
  // consideramos que el disco se detuvo.
  unsigned long tiempoSinPulso = micros() - ultima;

  if (tiempoSinPulso > 1000000UL) {
    return 0;
  }

  float rpm = 60000000.0 / (periodo * marcasPorVuelta);

  return rpm;
}


// ====================================
// SETUP
// ====================================

void setup() {

  Serial.begin(115200);

  // Configuracion del servo
  servo.setPeriodHertz(50);
  servo.attach(pinServo, 500, 2400);

  servo.write(posicionActual);

  // Configuracion del KY-033
  pinMode(pinSensor, INPUT);

  attachInterrupt(
    digitalPinToInterrupt(pinSensor),
    detectarMarca,
    FALLING
  );

  Serial.println("=== CONTROL SG90 + SENSOR KY-033 ===");

  Serial.println("Comandos disponibles:");
  Serial.println("0  = Bajar hacia 0 grados");
  Serial.println("s  = Detener movimiento");
  Serial.println("90 = Regresar directamente a 90 grados");

  Serial.println();

  Serial.println("tiempo_ms,rpm,servo_grados");
}


// ====================================
// LOOP
// ====================================

void loop() {

  // ----------------------------------
  // 1. LEER COMANDOS DEL MONITOR SERIAL
  // ----------------------------------

  if (Serial.available() > 0) {

    String comando = Serial.readStringUntil('\n');
    comando.trim();

    if (comando == "0") {

      moviendo = true;
      tiempoAnteriorServo = millis();

      Serial.println("Bajando hacia 0 grados...");
    }

    else if (comando == "s") {

      moviendo = false;

      Serial.print("Detenido en: ");
      Serial.println(posicionActual);
    }

    else if (comando == "90") {

      moviendo = false;
      posicionActual = 90;

      servo.write(posicionActual);

      Serial.println("Regresando directamente a 90 grados");
    }

    else {

      Serial.println("Comando no valido");
    }
  }


  // ----------------------------------
  // 2. MOVIMIENTO PROGRESIVO DEL SERVO
  // ----------------------------------

  if (moviendo) {

    unsigned long intervalo;

    if (posicionActual > puntoDesaceleracion) {

      intervalo = velocidadNormal;
    }

    else {

      intervalo = velocidadLenta;
    }

    if (millis() - tiempoAnteriorServo >= intervalo) {

      tiempoAnteriorServo = millis();

      if (posicionActual > 0) {

        posicionActual--;

        servo.write(posicionActual);
      }

      else {

        moviendo = false;

        Serial.println("Servo llego a 0 grados");
      }
    }
  }


  // ----------------------------------
  // 3. MEDIR Y REGISTRAR RPM
  // ----------------------------------

  if (millis() - tiempoAnteriorRegistro >= intervaloRegistro) {

    tiempoAnteriorRegistro = millis();

    float rpm = calcularRPM();

    Serial.print(millis());
    Serial.print(",");

    Serial.print(rpm, 2);
    Serial.print(",");

    Serial.println(posicionActual);
  }
}