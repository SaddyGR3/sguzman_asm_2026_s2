"""Métricas comunes del protocolo 2.5; no modifican ni normalizan señales."""

import math

import numpy as np


def vector_real(x):
    x = np.asarray(x)
    if np.iscomplexobj(x) or x.ndim != 1 or x.size == 0:
        raise ValueError("Se requiere un vector real unidimensional no vacío")
    x = np.asarray(x, dtype=np.float64)
    if not np.all(np.isfinite(x)):
        raise ValueError("La señal contiene valores no finitos")
    return x


def pareja(s, y):
    s, y = vector_real(s), vector_real(y)
    if s.shape != y.shape:
        raise ValueError("Referencia y salida deben tener la misma longitud")
    return s, y


def energia(x):
    x = vector_real(x)
    return float(np.sum(x * x))


def cociente_db(numerador, denominador):
    """Cociente de potencias; None si ambas son cero, sin epsilons."""
    if numerador < 0 or denominador < 0:
        raise ValueError("Las energías no pueden ser negativas")
    if numerador == 0:
        return None if denominador == 0 else float("-inf")
    if denominador == 0:
        return float("inf")
    return float(10 * np.log10(numerador / denominador))


def calidad(s, y):
    s, y = pareja(s, y)
    es = energia(s)
    if es == 0:
        raise ValueError("Referencia limpia con energía cero")
    ee = energia(s - y)
    return {"mse": ee / s.size, "snr_db": cociente_db(es, ee)}


def recortar(x, inicio, fin, retardo=0):
    """Compensa solo el desplazamiento declarado; nunca estima un retardo."""
    x = vector_real(x)
    if not all(isinstance(v, (int, np.integer)) for v in (inicio, fin, retardo)):
        raise ValueError("Índices y retardo deben ser enteros")
    if inicio < 0 or fin <= inicio or retardo < 0 or fin + retardo > x.size:
        raise ValueError("Tramo o retardo fuera de la señal")
    return x[inicio + retardo:fin + retardo]


def conservacion_pct(s, componente):
    s, componente = pareja(s, componente)
    es = energia(s)
    if es == 0:
        raise ValueError("Referencia limpia con energía cero")
    return 100 * energia(componente) / es


def atenuacion_total_db(ruido, residual):
    ruido, residual = pareja(ruido, residual)
    inicial = energia(ruido)
    if inicial == 0:
        return None
    return cociente_db(inicial, energia(residual))


def energia_banda(x, fs, banda):
    """Energía de la señal ventaneada, rFFT con ponderación unilateral."""
    x = vector_real(x)
    if fs <= 0 or len(banda) != 2 or not 0 <= banda[0] <= banda[1] <= fs / 2:
        raise ValueError("Banda o frecuencia de muestreo inválida")
    n = np.arange(x.size)
    ventana = 0.5 - 0.5 * np.cos(2 * np.pi * n / x.size)
    espectro = np.fft.rfft(x * ventana)
    frecuencia = np.fft.rfftfreq(x.size, 1 / fs)
    pesos = np.full(espectro.size, 2.0)
    pesos[0] = 1
    if x.size % 2 == 0:
        pesos[-1] = 1
    seleccion = (frecuencia >= banda[0]) & (frecuencia <= banda[1])
    return float(np.sum(pesos[seleccion] * np.abs(espectro[seleccion])**2) / x.size)


def atenuacion_banda_db(ruido, residual, fs, banda):
    ruido, residual = pareja(ruido, residual)
    if banda is None:
        return None
    inicial = energia_banda(ruido, fs, banda)
    if inicial == 0:
        return None
    return cociente_db(inicial, energia_banda(residual, fs, banda))


def amplitudes_tonos(x, fs, frecuencias):
    x = vector_real(x)
    if fs <= 0 or len(set(frecuencias)) != len(frecuencias):
        raise ValueError("Frecuencia de muestreo o tonos inválidos")
    if not all(0 < f < fs / 2 for f in frecuencias):
        raise ValueError("Los tonos deben estar entre DC y Nyquist")
    t = np.arange(x.size) / fs
    columnas = [np.ones(x.size)]
    for f in frecuencias:
        columnas.extend((np.sin(2 * np.pi * f * t), np.cos(2 * np.pi * f * t)))
    base = np.column_stack(columnas)
    coeficientes, _, rango, _ = np.linalg.lstsq(base, x, rcond=None)
    if rango != base.shape[1]:
        raise ValueError("No se pueden separar los tonos con este tramo")
    return {str(f): float(np.hypot(*coeficientes[1 + 2*i:3 + 2*i]))
            for i, f in enumerate(frecuencias)}


def ganancias_tonos_db(s, componente, fs, frecuencias):
    s, componente = pareja(s, componente)
    referencia = amplitudes_tonos(s, fs, frecuencias)
    salida = amplitudes_tonos(componente, fs, frecuencias)
    return {f: (None if referencia[f] == 0 else
                cociente_db(salida[f]**2, referencia[f]**2)) for f in referencia}


def serializable(valor):
    """JSON estándar: infinitos como cadenas, NaN como null."""
    if isinstance(valor, dict):
        return {str(k): serializable(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [serializable(v) for v in valor]
    if isinstance(valor, np.ndarray):
        return serializable(valor.tolist())
    if isinstance(valor, np.generic):
        return serializable(valor.item())
    if isinstance(valor, float) and not math.isfinite(valor):
        if math.isnan(valor):
            return None
        return "+inf" if valor > 0 else "-inf"
    return valor
