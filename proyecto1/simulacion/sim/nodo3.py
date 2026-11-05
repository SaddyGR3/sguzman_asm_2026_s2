"""Nodo 3: reducción espectral causal por tramas FFT/IFFT con solapamiento.

Cada llamada de ganancia recibe únicamente la trama actual y el historial de
tramas ya recibidas. La salida representa bloques emitidos en flujo: el bloque
que se completa al recibir el bloque j aparece en la posición j de la salida.
Por ello la señal devuelta tiene H muestras iniciales de silencio.
"""

import json
from collections import deque
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from sim.metricas import vector_real


def cargar_config_nodo3():
    """Lee los parámetros de diseño del nodo 3 desde su archivo JSON."""
    ruta = Path(__file__).resolve().parents[1] / "config" / "nodo3.json"
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


# Origen: proyecto1/tarea1/entrega/tarea1/src/filtrado_espectral.py (Tarea 1), sin cambios.
def ventana_sqrt_hann(N: int) -> np.ndarray:
    """Ventana de analisis y sintesis; w[n]^2 + w[n+N/2]^2 = 1."""
    n = np.arange(N)
    return np.sqrt(0.5 * (1.0 - np.cos(2.0 * np.pi * n / N)))


# Origen: proyecto1/tarea1/entrega/tarea1/src/filtrado_espectral.py (Tarea 1),
# parte de estimar_piso_ruido. Cambio: la mediana temporal usa solo el historial causal.
def suavizar_piso(perfil, ancho):
    """Mediana local de ancho impar, con reflexión en los extremos del espectro."""
    perfil = vector_real(perfil)
    if not isinstance(ancho, (int, np.integer)) or ancho < 1 or ancho % 2 == 0:
        raise ValueError("El ancho de suavizado debe ser un entero impar positivo")
    radio = ancho // 2
    extendido = np.pad(perfil, radio, mode="reflect")
    return np.median(sliding_window_view(extendido, ancho), axis=1)


def _validar_tramas(N, H):
    """La suma de ventanas requiere 50 % de solape y FFT de potencia de dos."""
    if not isinstance(N, (int, np.integer)) or N < 2 or N & (N - 1):
        raise ValueError("N debe ser una potencia de dos mayor o igual a 2")
    if not isinstance(H, (int, np.integer)) or H != N // 2:
        raise ValueError("H debe ser N/2 para reconstrucción por raíz de Hann")


def _procesar_tramas(x, N, H, calcular_ganancia):
    """FFT, ganancia y suma con solape; devuelve salida de flujo y matriz G.

    El prefijo de H ceros permite que el primer bloque real reciba ambas
    mitades de ventana. Se rellena el final solo para completar la última FFT;
    ese bloque final todavía no se emite dentro del largo original de x.
    """
    _validar_tramas(N, H)
    x = vector_real(x)
    cantidad = (x.size + H - 1) // H
    entrada = np.zeros((cantidad + 1) * H)
    entrada[H:H + x.size] = x
    salida = np.zeros(cantidad * H + N)
    ventana = ventana_sqrt_hann(N)
    ganancias = []

    for i in range(cantidad):
        inicio = i * H
        espectro = np.fft.rfft(entrada[inicio:inicio + N] * ventana)
        ganancia = np.asarray(calcular_ganancia(i, np.abs(espectro)), dtype=float)
        if ganancia.shape != espectro.shape or not np.all(np.isfinite(ganancia)):
            raise ValueError("La ganancia debe tener un valor finito por bin de la rFFT")
        ganancias.append(ganancia)
        salida[inicio:inicio + N] += np.fft.irfft(espectro * ganancia, n=N) * ventana

    return salida[:x.size], np.stack(ganancias)


def _maximos_locales(magnitudes):
    """Máximos interiores; DC y Nyquist no tienen dos vecinos."""
    maximos = np.zeros(magnitudes.size, dtype=bool)
    maximos[1:-1] = ((magnitudes[1:-1] >= magnitudes[:-2])
                       & (magnitudes[1:-1] >= magnitudes[2:]))
    return maximos


def _ganancias_picos(magnitudes, piso, banda, fs, N, cfg):
    """Atenúa máximos estrechos fuera de la banda útil y sus bins vecinos."""
    frecuencias = np.fft.rfftfreq(N, 1 / fs)
    protegido = (frecuencias >= banda[0]) & (frecuencias <= banda[1])
    candidatos = ((magnitudes > cfg["umbral"] * piso)
                  & _maximos_locales(magnitudes) & ~protegido)
    ganancia_minima = 10 ** (-cfg["atenuacion_dB"] / 20)
    G = np.ones(magnitudes.size)
    for centro in np.flatnonzero(candidatos):
        ancho = cfg["ancho_bins"]
        G[max(0, centro - ancho):centro + ancho + 1] = ganancia_minima
    return G


def _tonos_protegidos(historial, perfil, piso, banda, fs, N, cfg, epsilon):
    """Identifica picos persistentes de la banda útil usando solo tramas pasadas."""
    frecuencias = np.fft.rfftfreq(N, 1 / fs)
    en_banda = (frecuencias >= banda[0]) & (frecuencias <= banda[1])
    variacion = np.std(historial, axis=0) / np.maximum(np.mean(historial, axis=0), epsilon)
    centros = np.flatnonzero(en_banda
                            & (perfil > cfg["umbral"] * np.maximum(piso, epsilon))
                            & _maximos_locales(perfil)
                            & (variacion < cfg["variacion_max"]))
    protegidos = np.zeros(perfil.size, dtype=bool)
    for centro in centros:
        ancho = cfg["ancho_bins"]
        protegidos[max(0, centro - ancho):centro + ancho + 1] = True
    return protegidos


def _ganancias_resta(magnitudes, piso, alfa, cfg, epsilon, protegidos=None):
    """Resta el piso estimado y limita la ganancia para evitar ceros abruptos."""
    G = np.clip(1 - alfa * piso / np.maximum(magnitudes, epsilon),
                cfg["ganancia_minima"], 1.0)
    if protegidos is not None:
        G[protegidos] = 1.0
    return G


def filtrar_espectral_causal(x, metodo, banda_Hz, cfg_n3, fs, N, H,
                            alfa=None, proteccion=False):
    """Filtra x por picos o resta; devuelve y, ganancias y tramas de calentamiento.

    La trama inicial contiene H ceros y no participa en la estimación. Las
    siguientes ocho tramas reales llenan el historial; hasta entonces G=1.
    ``y`` tiene el mismo largo que x y un retardo declarado de H muestras.
    """
    _validar_tramas(N, H)
    if metodo not in ("picos", "resta"):
        raise ValueError(f"Método espectral desconocido: {metodo!r}")
    if fs <= 0 or len(banda_Hz) != 2 or not 0 <= banda_Hz[0] < banda_Hz[1] <= fs / 2:
        raise ValueError("Banda útil o frecuencia de muestreo inválida")
    if alfa is None:
        alfa = cfg_n3["resta"]["alfa"]
    if alfa < 0:
        raise ValueError("alfa no puede ser negativo")

    historia = deque(maxlen=cfg_n3["historial_tramas"])
    if historia.maxlen < 1:
        raise ValueError("El historial debe contener al menos una trama")
    calentamiento = 0

    def calcular_ganancia(i, magnitudes):
        nonlocal calentamiento
        if i > 0:
            historia.append(magnitudes)
        if len(historia) < historia.maxlen:
            calentamiento += 1
            return np.ones(magnitudes.size)

        bloques = np.stack(historia)
        perfil = np.median(bloques, axis=0)
        piso = suavizar_piso(perfil, cfg_n3["suavizado_bins"])
        if metodo == "picos":
            return _ganancias_picos(magnitudes, piso, banda_Hz, fs, N, cfg_n3["picos"])
        protegidos = None
        if proteccion:
            protegidos = _tonos_protegidos(bloques, perfil, piso, banda_Hz, fs, N,
                                           cfg_n3["proteccion_tonos"], cfg_n3["epsilon"])
        return _ganancias_resta(magnitudes, piso, alfa, cfg_n3["resta"],
                                cfg_n3["epsilon"], protegidos)

    y, G = _procesar_tramas(x, N, H, calcular_ganancia)
    return {"y": y, "G": G, "tramas_calentamiento": calentamiento}


def aplicar_ganancias(x, G, N, H):
    """Aplica a x una matriz G ya aprendida, sin reestimar el ruido.

    Usar las ganancias aprendidas de la mezcla sobre la referencia limpia
    permite medir cuánta señal útil conserva exactamente esa misma ruta.
    """
    G = np.asarray(G, dtype=float)
    x = vector_real(x)
    _validar_tramas(N, H)
    cantidad = (x.size + H - 1) // H
    if G.shape != (cantidad, N // 2 + 1):
        raise ValueError("G debe tener una fila por trama y N/2+1 columnas")
    return _procesar_tramas(x, N, H, lambda i, _: G[i])[0]


def parametros_nodo3(cfg_prueba, cfg_n3, nivel=None):
    """Traduce la elección de P1–P5 a método, alfa y protección tonal."""
    metodo = cfg_prueba["metodo_n3"]
    if metodo == "picos":
        return "picos", None, False
    if metodo not in ("resta", "resta_con_proteccion"):
        raise ValueError(f"Método de prueba desconocido: {metodo!r}")
    alfa = cfg_prueba.get("parametros_n3", {}).get("alfa", cfg_n3["resta"]["alfa"])
    proteccion = metodo == "resta_con_proteccion"
    if nivel is not None:
        alfa = nivel["alfa"]
        proteccion = nivel["proteccion_tonos"]
    return "resta", alfa, proteccion


def retardo_espectral(H):
    """Un bloque queda completo y se emite tras recibir el siguiente bloque."""
    if not isinstance(H, (int, np.integer)) or H < 1:
        raise ValueError("H debe ser un entero positivo")
    return H
