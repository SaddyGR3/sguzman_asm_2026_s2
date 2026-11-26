#pragma once
#include <Arduino.h>

namespace Configuracion {
constexpr int pinServo = 18;
constexpr int pinSensor = 34;
constexpr int pinMotor = 25;
constexpr int marcasPorVuelta = 1;

// Se conserva el rango manual de calibracion del firmware anterior.
// El futuro control automatico usara limites calibrados independientes.
constexpr int anguloMinimo = 0;
constexpr int anguloMaximo = 90;
constexpr int anguloLiberado = 90;
// Rango provisional para ensayos automaticos. No limita la calibracion manual.
constexpr int anguloMinimoEnsayo = 47;
constexpr int anguloMaximoEnsayo = 90;
constexpr uint32_t duracionEnsayoFijoMs = 10000;
constexpr uint32_t duracionMinimaEnsayoMs = 100;
constexpr uint32_t duracionMaximaEnsayoMs = 30000;
constexpr uint32_t tiempoMaximoPreparacionMs = 30000;
// Antiguedad maxima para iniciar un ensayo.
constexpr uint32_t antiguedadMaximaInicioUs = 250000;
constexpr uint32_t velocidadNormal = 11;
constexpr uint32_t velocidadLenta = 18;
constexpr int puntoDesaceleracion = 20;

// Conserva el filtro y el criterio de cero de las capturas existentes.
constexpr uint32_t tiempoMinimoPulsoUs = 20000;
constexpr uint32_t tiempoSinPulsoParaCeroUs = 1000000;
constexpr uint32_t intervaloRegistroMs = 100;
// Umbrales provisionales. No representan calibracion fisica final.
constexpr uint32_t antiguedadMinimaUs = 250000;
constexpr uint32_t multiplicadorAntiguedad = 3;
constexpr uint32_t falloMedicionPersistenteMs = 1500;
constexpr uint32_t graciaMedicionPreparacionMs = 3000;
constexpr uint32_t capacidadColaPulsos = 32;
// Solo incrementos bruscos de RPM. Una desaceleracion rapida no se rechaza.
constexpr uint32_t factorSaltoNumerador = 18;
constexpr uint32_t factorSaltoDenominador = 10;
constexpr uint32_t confirmacionesSalto = 3;
constexpr uint32_t toleranciaConfirmacionPorcentaje = 20;

// Actuacion deshabilitada hasta validar montaje y ganancias.
constexpr bool actuacionPIDHabilitada = false;
constexpr float rpmFinPid = 100.0f;
constexpr uint32_t confirmacionFinPidMs = 300;
constexpr uint32_t tiempoExtraFinPidMs = 2000;
// Ganancias sin ajustar y tiempos provisionales.
constexpr float pidKp = 0.0f;
constexpr float pidKi = 0.0f;
constexpr float pidKd = 0.0f;
constexpr float pidTauDerivadaS = 0.1f;
constexpr uint32_t periodoPidUs = 20000;
constexpr uint32_t intervaloMaximoPidUs = 100000;

// Activar solo despues de confirmar entrada del driver, polaridad y
// condicion de apagado. Deshabilitado no configura ni escribe GPIO25.
constexpr bool controlMotorHabilitado = false;
constexpr uint8_t nivelMotorEncendido = HIGH;
static_assert(anguloMinimoEnsayo >= anguloMinimo &&
              anguloMaximoEnsayo <= anguloMaximo &&
              anguloMinimoEnsayo <= anguloMaximoEnsayo,
              "Rango de ensayo fuera del rango manual");
static_assert(anguloLiberado == anguloMaximoEnsayo && anguloMinimoEnsayo < anguloLiberado,
              "Rango de accion del freno inconsistente");
static_assert(capacidadColaPulsos >= 2, "Cola de pulsos demasiado pequena");
static_assert(tiempoSinPulsoParaCeroUs >= antiguedadMinimaUs,
              "Antiguedades de medicion inconsistentes");
static_assert(marcasPorVuelta > 0, "Pulsos por vuelta debe ser positivo");
}
