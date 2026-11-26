#pragma once
namespace Freno {
void iniciar();
int anguloParaAccion(float accion);
bool aplicarAccion(float accion);
float leerAccionAplicada();
void fijarAngulo(int nuevoAngulo);
int leerAngulo();
int leerPaso();
void fijarPaso(int paso);
void iniciarRampa();
void detenerRampa();
void actualizarRampa();
}
