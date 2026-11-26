"""Pruebas de secuencia y GPIO simulados, sin conectar ni cargar la ESP32."""
from pathlib import Path
import argparse
import csv
import importlib.util
import io
import sys
import types
from contextlib import redirect_stdout
from unittest.mock import patch
import threading
import re
import shutil
import subprocess
import tempfile

proyecto = Path(__file__).resolve().parents[2]
pruebas = proyecto / "test" / "host"
parser = argparse.ArgumentParser()
parser.add_argument("--capturador", type=Path, default=proyecto.parents[1] / "tarea2/herramientas/registrar_ensayo.py")
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix="freno_ensayos_") as temporal:
    trabajo = Path(temporal)
    for variante in ("deshabilitado", "HIGH", "LOW"):
        copia = trabajo / variante
        shutil.copytree(proyecto / "include", copia / "include")
        shutil.copytree(proyecto / "src", copia / "src")
        config = copia / "include" / "configuracion.h"
        texto = re.sub(
            r"controlMotorHabilitado = (true|false)",
            "controlMotorHabilitado = " + ("false" if variante == "deshabilitado" else "true"),
            config.read_text(),
        )
        if variante != "deshabilitado":
            texto = re.sub(r"nivelMotorEncendido = (HIGH|LOW)",
                           f"nivelMotorEncendido = {variante}", texto)
        config.write_text(texto)
        ejecutable = copia / "prueba"
        subprocess.run([
            "g++", "-std=c++11", "-Wall", "-Wextra", "-Werror",
            "-I", str(pruebas), "-I", str(copia / "include"),
            *map(str, sorted((copia / "src").glob("*.cpp"))),
            str(pruebas / "ensayos_test.cpp"), "-o", str(ejecutable),
        ], check=True)
        casos = ["deshabilitado"] if variante == "deshabilitado" else [
            "normal", "cancelacion", "validacion", "timeout", "timeout_inicio",
            "linea_larga", "micros_wrap", "millis_wrap",
        ]
        for caso in casos:
            subprocess.run([str(ejecutable), caso], check=True)
    copia = trabajo / "HIGH"
    ejecutable = copia / "medicion"
    subprocess.run([
        "g++", "-std=c++11", "-Wall", "-Wextra", "-Werror",
        "-I", str(pruebas), "-I", str(copia / "include"),
        *map(str, sorted((copia / "src").glob("*.cpp"))),
        str(pruebas / "medicion_test.cpp"), "-o", str(ejecutable),
    ], check=True)
    for caso in ["inicial", "cortos", "salto", "sostenido", "desaceleracion",
                 "antiguedad", "cola", "silencio_wrap", "fallo", "reinicio", "referencia_cancelacion"]:
        subprocess.run([str(ejecutable), caso], check=True)
    prueba_referencia = trabajo / "referencia"
    subprocess.run([
        "g++", "-std=c++11", "-Wall", "-Wextra", "-Werror",
        "-I", str(copia / "include"), str(copia / "src/referencia.cpp"),
        str(pruebas / "referencia_test.cpp"), "-o", str(prueba_referencia),
    ], check=True)
    subprocess.run([str(prueba_referencia)], check=True)
    prueba_pid = trabajo / "pid"
    subprocess.run([
        "g++", "-std=c++11", "-Wall", "-Wextra", "-Werror",
        "-I", str(copia / "include"), str(copia / "src/pid.cpp"),
        str(pruebas / "pid_test.cpp"), "-o", str(prueba_pid),
    ], check=True)
    subprocess.run([str(prueba_pid)], check=True)
    observacion = trabajo / "observacion"
    shutil.copytree(copia / "include", observacion / "include")
    shutil.copytree(copia / "src", observacion / "src")
    conf = observacion / "include/configuracion.h"
    txt = conf.read_text().replace("pidKp = 0.0f", "pidKp = 0.002f").replace(
        "pidKi = 0.0f", "pidKi = 0.001f").replace("pidKd = 0.0f", "pidKd = 0.0001f")
    conf.write_text(txt)
    prueba_observacion = observacion / "prueba"
    subprocess.run([
        "g++", "-std=c++11", "-Wall", "-Wextra", "-Werror",
        "-I", str(pruebas), "-I", str(observacion / "include"),
        *map(str, sorted((observacion / "src").glob("*.cpp"))),
        str(pruebas / "pid_observacion_test.cpp"), "-o", str(prueba_observacion),
    ], check=True)
    salida_observacion = subprocess.check_output([str(prueba_observacion)], text=True)
    for variante_pid in ("bloqueado", "ganancias_cero", "activo"):
        carpeta_pid = trabajo / ("actuacion_" + variante_pid)
        shutil.copytree(observacion / "include", carpeta_pid / "include")
        shutil.copytree(observacion / "src", carpeta_pid / "src")
        config_pid = carpeta_pid / "include/configuracion.h"
        texto_pid = config_pid.read_text()
        if variante_pid != "bloqueado":
            texto_pid = texto_pid.replace("actuacionPIDHabilitada = false", "actuacionPIDHabilitada = true")
        if variante_pid == "ganancias_cero":
            for ganancia in ("Kp", "Ki", "Kd"):
                texto_pid = re.sub(r"pid" + ganancia + r" = [^;]+", "pid" + ganancia + " = 0.0f", texto_pid)
        config_pid.write_text(texto_pid)
        ejecutable_pid = carpeta_pid / "prueba"
        subprocess.run([
            "g++", "-std=c++11", "-Wall", "-Wextra", "-Werror",
            "-I", str(pruebas), "-I", str(carpeta_pid / "include"),
            *map(str, sorted((carpeta_pid / "src").glob("*.cpp"))),
            str(pruebas / "pid_actuacion_test.cpp"), "-o", str(ejecutable_pid),
        ], check=True)
        casos_pid = [variante_pid] if variante_pid != "activo" else [
            "conversion", "normal", "reloj", "debajo_referencia", "medicion",
            "tiempo", "sin_confirmacion", "fin_baja",
        ]
        for caso in casos_pid:
            subprocess.run([str(ejecutable_pid), caso], check=True)
    salida_pid_activo = subprocess.check_output([str(ejecutable_pid), "telemetria"], text=True)
    # Importar el parser sin requerir un puerto ni pyserial en estas pruebas.
    if importlib.util.find_spec("serial") is None:
        sys.modules["serial"] = types.ModuleType("serial")
    spec = importlib.util.spec_from_file_location("capturador_prueba", args.capturador)
    capturador = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(capturador)
    datos, eventos, diagnostico = io.StringIO(), io.StringIO(), io.StringIO()
    registro = capturador.Registro(datos, eventos, diagnostico)
    salida = subprocess.check_output([str(ejecutable), "telemetria"], text=True)
    with redirect_stdout(io.StringIO()):
        for linea in salida.splitlines():
            registro.procesar(linea)
    tabla = list(csv.DictReader(io.StringIO(diagnostico.getvalue())))
    assert tabla and any(f["estado_medicion"] == "RECIENTE" for f in tabla)
    assert any(f["ultimo_periodo_rechazado_us"] == "3000" for f in tabla)
    assert all(len(f) == len(capturador.ENCABEZADO_DIAGNOSTICO) for f in tabla)
    assert all(f["referencia_rpm"] == "nan" for f in tabla)
    assert list(csv.DictReader(io.StringIO(datos.getvalue())))
    d_ref, e_ref, diag_ref = io.StringIO(), io.StringIO(), io.StringIO()
    con_referencia = capturador.Registro(d_ref, e_ref, diag_ref)
    salida_ref = subprocess.check_output([str(ejecutable), "referencia_registro"], text=True)
    with redirect_stdout(io.StringIO()):
        for linea in salida_ref.splitlines():
            con_referencia.procesar(linea)
    filas_ref = list(csv.DictReader(io.StringIO(diag_ref.getvalue())))
    activas = [f for f in filas_ref if f["modo"] == "FIJO"]
    assert activas and all(f["referencia_rpm"] != "nan" for f in activas)
    assert all(f["u_aplicada"] == "nan" for f in filas_ref)
    calculadas = [f for f in activas if f["pid_estado"] == "GANANCIAS_CERO"]
    assert calculadas and all(float(f["u_solicitada"]) == 0 and float(f["pid_u_limitada"]) == 0 for f in calculadas)
    for fila in activas:
        t = int(fila["tiempo_ensayo_ms"])
        assert abs(float(fila["referencia_rpm"])-1200*max(0,1-t/6000)) < 0.02
        if fila["estado_medicion"] == "RECIENTE":
            assert abs(float(fila["error_rpm"])-(float(fila["rpm_validada"])-float(fila["referencia_rpm"]))) < 0.03
        else:
            assert fila["error_rpm"] == "nan"
    finales = [f for f in filas_ref if f["modo"] == "FINALIZADO"]
    assert finales and all(float(f["referencia_rpm"]) == 0 for f in finales)
    assert "REFERENCIA_LINEAL_MS,6000" in e_ref.getvalue()
    d_bad, e_bad, diag_bad = io.StringIO(), io.StringIO(), io.StringIO()
    invalida = capturador.Registro(d_bad, e_bad, diag_bad)
    salida_bad = subprocess.check_output([str(ejecutable), "referencia_dato_invalido"], text=True)
    with redirect_stdout(io.StringIO()):
        for linea in salida_bad.splitlines():
            invalida.procesar(linea)
    malas = [f for f in csv.DictReader(io.StringIO(diag_bad.getvalue()))
             if f["modo"] == "FIJO" and f["estado_medicion"] == "SOSPECHOSA"]
    assert malas and all(f["error_rpm"] == "nan" and f["referencia_rpm"] != "nan" for f in malas)
    print("Referencia y error guardados por el capturador sin alterar columnas.")
    d_pid, e_pid, diag_pid = io.StringIO(), io.StringIO(), io.StringIO()
    con_pid = capturador.Registro(d_pid, e_pid, diag_pid)
    with redirect_stdout(io.StringIO()):
        for linea in salida_observacion.splitlines():
            con_pid.procesar(linea)
    filas_pid = [f for f in csv.DictReader(io.StringIO(diag_pid.getvalue()))
                 if f["pid_estado"] == "OBSERVACION"]
    assert filas_pid and any(float(f["pid_u_limitada"]) > 0 for f in filas_pid)
    assert all(f["u_aplicada"] == "nan" for f in filas_pid)
    assert all(0 <= float(f["pid_u_limitada"]) <= 1 for f in filas_pid)
    # Un diagnostico del paso 3/4 conserva sus columnas y explicita datos PID ausentes.
    anterior = "#DIAG,0,1200,1200,RECIENTE,0,50000,2,0,0,0,0,FIJO,0,0,1200,0,nan,nan"
    con_pid.procesar(anterior)
    ultima = list(csv.DictReader(io.StringIO(diag_pid.getvalue())))[-1]
    assert ultima["pid_estado"] == "NO_DISPONIBLE" and ultima["pid_dt_us"] == ""
    print("PID con ganancias de prueba no mueve el servo. Diagnosticos anteriores compatibles.")
    da, ea, pa = io.StringIO(), io.StringIO(), io.StringIO()
    registro_activo = capturador.Registro(da, ea, pa)
    with redirect_stdout(io.StringIO()):
        for linea in salida_pid_activo.splitlines():
            registro_activo.procesar(linea)
    filas_activas = [f for f in csv.DictReader(io.StringIO(pa.getvalue())) if f["modo"] == "PID"]
    assert filas_activas and any(float(f["u_aplicada"]) > 0 for f in filas_activas)
    assert all(f["pid_estado"] == "CONTROLANDO" for f in filas_activas)
    assert all(0 <= float(f["u_aplicada"]) <= 1 for f in filas_activas)
    assert "ENSAYO_PID_INICIO" in ea.getvalue()
    print("Ensayo PID y accion al servo registrados por el capturador.")
    # El mismo capturador sigue leyendo las tres columnas y eventos historicos.
    d, e = io.StringIO(), io.StringIO()
    viejo = capturador.Registro(d, e)
    with redirect_stdout(io.StringIO()):
        viejo.procesar("tiempo_ms,rpm,servo_cmd_grados")
        viejo.procesar("100,1400.50,90")
        viejo.procesar("#EVENT,110,SERVO_CMD,47")
    assert "1400.50" in d.getvalue() and "SERVO_CMD,47" in e.getvalue()
    # Validacion de formato y numeracion de un archivo de diagnostico huerfano.
    longitud = len(diagnostico.getvalue())
    with redirect_stdout(io.StringIO()):
        registro.procesar("#DIAG,invalido")
    assert len(diagnostico.getvalue()) == longitud
    (trabajo / "diagnostico_9.csv").write_text("")
    assert capturador.siguiente_numero(trabajo) == 10
    # Las letras de los comandos nuevos no se consumen como atajos antiguos.
    class Puerto:
        def __init__(self): self.ordenes = []
        def write(self, valor): self.ordenes.append(valor)
        def flush(self): pass
    teclas = iter("fijo47\ncancelar\nmotor_on\nm\nq")
    puerto = Puerto()
    with patch.object(capturador.os, "name", "nt"), \
         patch.object(capturador, "leer_tecla_windows", lambda: next(teclas)), \
         redirect_stdout(io.StringIO()):
        capturador.teclado_interactivo(puerto, threading.Event())
    assert puerto.ordenes == [b"fijo47\n", b"cancelar\n", b"motor_on\n", b"m\n"]
    print("Capturador nuevo, formato historico y teclado completo correctos.")
print("Todas las secuencias pasaron. La respuesta fisica de la maqueta queda pendiente.")
