#pragma once
#include <Arduino.h>

namespace Configuracion {
constexpr int pinServo = 18;
constexpr int pinSensor = 34;
constexpr int pinMotor = 25;
// Dos marcas aproximadamente equidistantes. Cada marca genera una deteccion.
constexpr int marcasPorVuelta = 2;
constexpr int nivelMarcaSensor = LOW;
// Valores provisionales para rechazar transiciones breves. Validar en maqueta.
constexpr uint32_t minimoZonaLibreUs = 100;
constexpr uint32_t minimoMarcaUs = 100;

// Se conserva el rango manual de calibracion del firmware anterior.
// El futuro control automatico usara limites calibrados independientes.
constexpr int anguloMinimo = 0;
constexpr int anguloMaximo = 90;
constexpr int anguloLiberado = 45;
// Rango provisional observado en maqueta. No limita la calibracion manual.
// 45 liberado y 25 limite de frenado fuerte. Dos marcas aproximadamente opuestas.
constexpr int anguloMinimoEnsayo = 25;
constexpr int anguloMaximoEnsayo = 45;
constexpr uint32_t duracionEnsayoFijoMs = 10000;
constexpr uint32_t duracionMinimaEnsayoMs = 100;
constexpr uint32_t duracionMaximaEnsayoMs = 30000;
constexpr uint32_t tiempoMaximoPreparacionMs = 60000;
constexpr float rpmApagadoAutomatico = 1400.0f;
constexpr float rpmInicioAutomatico = 1300.0f;
constexpr uint32_t tiempoMaximoDescensoMs = 15000;
static_assert(rpmApagadoAutomatico > rpmInicioAutomatico && rpmInicioAutomatico > 0,
              "Umbrales automaticos inconsistentes");
// Antiguedad maxima para iniciar un ensayo.
constexpr uint32_t antiguedadMaximaInicioUs = 250000;
constexpr uint32_t velocidadNormal = 11;
constexpr uint32_t velocidadLenta = 18;
constexpr int puntoDesaceleracion = 20;

// Limite provisional exclusivo. El intervalo se adapta a las marcas por vuelta.
// Conserva 20 ms con una marca. Con seis marcas permite intervalos de 3,333 ms.
constexpr uint32_t rpmMaximaMedible = 3000;
constexpr uint32_t tiempoMinimoPulsoUs = 60000000ULL /
    (static_cast<uint64_t>(rpmMaximaMedible) * marcasPorVuelta);
constexpr uint32_t tiempoSinPulsoParaCeroUs = 1000000;
constexpr uint32_t intervaloRegistroMs = 100;
// Umbrales provisionales. No representan calibracion fisica final.
constexpr uint32_t antiguedadMinimaUs = 250000;
constexpr uint32_t multiplicadorAntiguedad = 3;
constexpr uint32_t falloMedicionPersistenteMs = 1500;
// Solo FIJO. Una ausencia tras desacelerar puede ser parada o perdida del sensor.
constexpr float rpmPosibleParadaFijo = 400.0f;
constexpr float proporcionPosibleParadaFijo = 0.5f;
constexpr uint32_t muestrasMinimasParadaFijo = 3;
constexpr uint32_t graciaMedicionPreparacionMs = 3000;
constexpr uint32_t capacidadColaPulsos = 32;
// Solo incrementos bruscos de RPM. Una desaceleracion rapida no se rechaza.
constexpr uint32_t factorSaltoNumerador = 18;
constexpr uint32_t factorSaltoDenominador = 10;
constexpr uint32_t confirmacionesSalto = 3;
constexpr uint32_t toleranciaConfirmacionPorcentaje = 20;

// Actuacion fisica habilitada. Ajuste PI exploratorio, pendiente de evaluar.
constexpr bool actuacionPIDHabilitada = true;
constexpr float rpmFinPid = 100.0f;
constexpr uint32_t confirmacionFinPidMs = 300;
constexpr uint32_t tiempoExtraFinPidMs = 2000;
// Kp conservado y Ki aumentado para comparar. D desactivado.
constexpr float pidKp = 0.005f;
constexpr float pidKi = 0.004f;
constexpr float pidKd = 0.0f;
// Precarga exploratoria para la recta de seis segundos. 0,55 equivale a 34 grados.
constexpr float pidAccionInicial = 0.55f;
// Candidato de seis segundos para la exponencial normalizada de forma dos.
constexpr float pidAccionInicialExponencial = 0.70f;
static_assert(pidAccionInicialExponencial >= 0 && pidAccionInicialExponencial <= 1,
              "Precarga exponencial fuera de rango");
constexpr uint32_t pidDuracionPrecargaMs = 6000;
static_assert(pidAccionInicial >= 0 && pidAccionInicial <= 1, "Precarga PID fuera de rango");
constexpr float pidTauDerivadaS = 0.1f;
constexpr uint32_t periodoPidUs = 20000;
constexpr uint32_t intervaloMaximoPidUs = 100000;

// Control habilitado para probar el driver con IN1 en GPIO25 e IN2 a GND.
// HIGH enciende y LOW apaga. Comprobar el funcionamiento en la maqueta.
constexpr bool controlMotorHabilitado = true;
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
static_assert(tiempoMinimoPulsoUs >= minimoZonaLibreUs + minimoMarcaUs,
              "Marcas demasiado estrechas para los tiempos minimos del detector");
static_assert(marcasPorVuelta > 0 && marcasPorVuelta <= 64,
              "La ventana admite entre una y 64 marcas por vuelta");
}
