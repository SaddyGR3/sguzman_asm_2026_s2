"""Referencias de la simulacion. No configura curvas en el firmware de la ESP32."""
import math

CURVAS = {'lineal': 0, 'exponencial': 1, 'coseno': 2}


def evaluar_referencia(rpm_inicial, duracion_s, transcurrido_s, curva='lineal'):
    """Devuelve RPM deseadas y conserva los extremos antes y despues del ensayo.

    La exponencial usa factor de forma 3, igual al dibujo elegido. Se normaliza
    para llegar a cero en T. Estas formas requieren validar alcanzabilidad fisica.
    """
    if not isinstance(curva, str) or curva not in CURVAS:
        raise ValueError('Figura de referencia desconocida')
    if not all(math.isfinite(v) for v in (rpm_inicial, duracion_s, transcurrido_s)):
        raise ValueError('La referencia requiere valores finitos')
    if rpm_inicial < 0 or duracion_s <= 0:
        raise ValueError('Velocidad inicial o duracion invalida')
    if transcurrido_s <= 0:
        return float(rpm_inicial)
    if transcurrido_s >= duracion_s:
        return 0.0
    x = transcurrido_s / duracion_s
    if curva == 'lineal':
        fraccion = 1 - x
    elif curva == 'exponencial':
        fraccion = (math.exp(-3*x) - math.exp(-3)) / (1-math.exp(-3))
    else:
        fraccion = (1 + math.cos(math.pi*x)) / 2
    return rpm_inicial * min(1.0, max(0.0, fraccion))
