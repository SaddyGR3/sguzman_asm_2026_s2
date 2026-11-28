#!/usr/bin/env python3
"""Abre la aplicación de escritorio con un único archivo Python.

El primer inicio prepara .venv junto a este archivo si faltan dependencias.
Reutiliza un Python del sistema con PySide6 cuando está disponible. No instala
paquetes globales ni necesita que el usuario active un entorno manualmente.
"""
from __future__ import annotations
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

RAIZ = Path(__file__).resolve().parent


def dependencias_disponibles():
    return all(importlib.util.find_spec(nombre) is not None for nombre in ('PySide6', 'serial'))


def python_preparado(python):
    if not python.is_file():
        return False
    try:
        resultado = subprocess.run([str(python), '-c',
            'import PySide6.QtWidgets, serial'], capture_output=True, timeout=15)
        return resultado.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def preparar_entorno(sin_instalar=False):
    """Devuelve el intérprete correcto. Nunca usa pip sobre el Python global."""
    if dependencias_disponibles():
        return Path(sys.executable)
    entorno = RAIZ / '.venv'
    python = entorno / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if python_preparado(python):
        return python
    if sin_instalar:
        raise RuntimeError('Faltan PySide6 o pyserial. Ejecuta de nuevo sin --sin-instalar para preparar el entorno local.')
    base = sys.executable
    sistema = Path('/usr/bin/python3')
    if sistema.is_file():
        try:
            consulta = subprocess.run([str(sistema), '-c', 'import PySide6.QtWidgets'],
                                      capture_output=True, timeout=15)
            if consulta.returncode == 0:
                base = str(sistema)
        except (OSError, subprocess.TimeoutExpired):
            pass
    print('Preparando el entorno local del banco de frenado…', flush=True)
    if not python.is_file():
        subprocess.run([base, '-m', 'venv', '--system-site-packages', str(entorno)], check=True)
    print('Comprobando PySide6 y pyserial. La primera instalación puede necesitar internet.', flush=True)
    subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(RAIZ / 'requirements-escritorio.txt')], check=True)
    if not python_preparado(python):
        raise RuntimeError('El entorno se creó, pero no puede importar las dependencias. Revisa los mensajes de instalación.')
    return python


def main():
    parser = argparse.ArgumentParser(description='Ventana de escritorio del banco de frenado')
    parser.add_argument('--simulacion', action='store_true', help='Abrir y conectar la planta ficticia')
    parser.add_argument('--salida', type=Path, help='Carpeta de capturas')
    parser.add_argument('--comprobar', action='store_true', help='Comprobar dependencias sin abrir una ventana')
    parser.add_argument('--sin-instalar', action='store_true', help='No preparar dependencias nuevas')
    args = parser.parse_args()
    try:
        python = preparar_entorno(args.sin_instalar)
        if python != Path(sys.executable):
            # Mantener rutas absolutas para poder ejecutar desde cualquier carpeta.
            os.execv(str(python), [str(python), str(Path(__file__).resolve()), *sys.argv[1:]])
        if args.comprobar:
            import PySide6
            import serial
            print('Entorno listo · ' + sys.executable)
            print('PySide6 ' + PySide6.__version__ + ' · pyserial ' + serial.__version__)
            return 0
        from escritorio.ventana import ejecutar
        return ejecutar(args.salida, args.simulacion)
    except (ImportError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print('No se pudo abrir el banco de frenado · ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
