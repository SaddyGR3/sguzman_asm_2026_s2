"""Guarda solo METRICAS completas; devuelve toda la consola sin modificar."""
import csv
from datetime import datetime, timezone
from pathlib import Path
import sys

from platformio.device.monitor.filters.base import DeviceMonitorFilterBase

PC_DIR = Path(__file__).resolve().parents[3] / 'herramientas_pc'
if str(PC_DIR) not in sys.path:
    sys.path.insert(0, str(PC_DIR))
from metricas_csv import interpretar, CAMPOS, CAMPOS_V2  # noqa: E402


class GuardarMetricas(DeviceMonitorFilterBase):
    NAME = 'metricas_csv'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._archivo = None
        self._pendiente = ''
        self._descartando = False

    def __call__(self):
        self.cerrar()
        self._pendiente = ''
        self._descartando = False
        return self

    def cerrar(self):
        if self._archivo is not None:
            self._archivo.close()
            self._archivo = None

    def __del__(self):
        self.cerrar()

    def _linea(self, texto):
        # Un reinicio cambia la sesión porque el ID de reproducción vuelve a 1.
        if texto.startswith(('rst:', 'ets ', 'Nodos 2+3:')):
            self.cerrar()
        try:
            datos = interpretar(texto)
        except (ValueError, csv.Error) as exc:
            print(f'--- Métricas no guardadas: {exc}', file=sys.stderr)
            return
        if datos is None:
            return
        try:
            if self._archivo is None:
                destino = PC_DIR / 'resultados' / 'metricas'
                destino.mkdir(parents=True, exist_ok=True)
                fecha = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
                path = destino / f'metricas_{fecha}.csv'
                self._archivo = path.open('x', encoding='utf-8', newline='')
                print(f'--- Métricas guardadas en {path}', file=sys.stderr)
            campos = CAMPOS if datos['version'] == '3' else CAMPOS_V2
            self._archivo.write(','.join(datos[c] for c in campos) + '\n')
            self._archivo.flush()
        except OSError as exc:
            self.cerrar()
            print(f'--- No se pudo guardar métricas: {exc}', file=sys.stderr)

    def rx(self, texto):
        # Fragmentación arbitraria de UART; límite independiente del tamaño del log.
        for fragmento in texto.splitlines(keepends=True):
            termina = fragmento.endswith('\n')
            if not self._descartando:
                self._pendiente += fragmento
                if len(self._pendiente) > 4096:
                    self._pendiente = ''
                    self._descartando = True
            if termina:
                if not self._descartando:
                    self._linea(self._pendiente.rstrip('\r\n'))
                self._pendiente = ''
                self._descartando = False
        return texto
