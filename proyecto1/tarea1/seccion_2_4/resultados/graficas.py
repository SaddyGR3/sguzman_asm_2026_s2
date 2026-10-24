import numpy as np
import matplotlib.pyplot as plt

# Entrada oficial de 2.2
with np.load("seccion_2_2/2_2_generacionsenales/pruebas/caso_1/muestras_exactas.npz") as datos:
    print(datos.files)  # limpia, ruido, contaminada, fs
    contaminada = datos["contaminada"]
    limpia = datos["limpia"]
    print("fs:", datos["fs"])
    print("Primeras muestras:", contaminada[:10])

#Si quieren ver los distintos casos cambiar caso_1 por caso_2 o caso_3.
# Salida del filtro de 2.4
with np.load("seccion_2_4/resultados/caso_3/salida_filtrada.npz") as datos:
    print(datos.files)  # salida, fs
    salida = datos["salida"]
    print("Primeras muestras filtradas:", salida[:10])

t_ms = np.arange(len(limpia)) / 8000 * 1000
plt.plot(t_ms[:200], limpia[:200], label="Limpia")
plt.plot(t_ms[:200], contaminada[:200], label="Contaminada", alpha=0.6)
plt.plot(t_ms[:200], salida[:200], label="Filtrada", alpha=0.8)
plt.xlabel("Tiempo (ms)")
plt.ylabel("Amplitud")
plt.legend()
plt.show()