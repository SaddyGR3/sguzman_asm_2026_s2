"""Datos derivados solo para pantalla. No cambian mediciones ni control."""
import math


def velocidad_para_pantalla(d):
    estado=d.get('estado_medicion')
    edad=d.get('antiguedad_us')
    aceptados=d.get('pulsos_aceptados',0)
    cero=(estado=='SIN_SENAL' and isinstance(edad,(int,float)) and
          math.isfinite(edad) and edad>=1000000 and aceptados>0)
    medida=d.get('rpm_validada')
    if not isinstance(medida,(int,float)) or not math.isfinite(medida): medida=None
    # No prolongar en la grafica el ultimo periodo crudo cuando ya caduco.
    cruda=d.get('rpm_cruda') if estado in ('RECIENTE','SOSPECHOSA') else None
    return dict(rpm_mostrada=0.0 if cero else medida,cero_estimado=cero,
                rpm_cruda_grafica=cruda)
