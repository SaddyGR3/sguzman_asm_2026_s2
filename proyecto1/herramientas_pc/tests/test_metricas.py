"""Pruebas sin puerto serial ni compilación de firmware."""
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest

PC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PC))
from metricas_csv import CAMPOS, MODOS, agrupar, interpretar


def linea(modo='SIN_FILTRO', version=2, id=1, **cambios):
    valores = ['METRICAS', str(version), str(id), 'OK', 'temporal', modo,
               '100', '1200', '2150', '0', '0', '0', '100', '0', '0', '0',
               '0', '0', '0', '100000', '80000', '1024', '3', '10', '20',
               '15.625', '4', '8', '2150', '8.5', '3', '0.05', 'pico']
    d = dict(zip(CAMPOS, valores))
    if modo == 'RESTA':
        d['ruta'] = 'espectral'
        d['retardo_ms'] = '64'
    elif modo == 'FIR':
        d['retardo_ms'] = '2.25'
    d.update(cambios)
    return ','.join(d[c] for c in CAMPOS)+'\n'


class Parser(unittest.TestCase):
    def test_versiones_y_na(self):
        for version in (1,2):
            self.assertEqual(interpretar(linea('RESTA',version,snr_y_db='NA'))['snr_y_db'],'NA')
        self.assertIsNone(interpretar('#0012 | RX 15.6/s'))

    def test_invalidos(self):
        for row in [linea(version=3), linea(ruta='espectral'), linea(mse_x='nan'),
                    linea(proc_max_ms='NA'), linea(banda_hi_hz='99'), linea(modo='OTRO'),
                    linea().strip()+',extra', 'METRICAS,2,1', linea(muestras='-1')]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                interpretar(row)

    def test_deduplicacion_y_sesiones(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'a.csv',Path(tmp)/'b.csv'
            datos=''.join(linea(m) for m in MODOS)
            a.write_text(datos*2); b.write_text(datos)
            informes,avisos,dup=agrupar([a,a,b])
            self.assertEqual((len(informes),len(avisos),dup),(2,0,4))
            self.assertTrue(all(i.valido for i in informes))

    def test_no_silenciar_conflictos_incompletos_ni_invalidacion(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.csv'
            p.write_text(''.join(linea(m) for m in MODOS)+linea('FIR',mse_x='0.1'))
            self.assertFalse(agrupar([p])[0][0].valido)
            p.write_text(linea('FIR'))
            self.assertFalse(agrupar([p])[0][0].completo)
            p.write_text(''.join(linea(m,estado='CONFIG_CAMBIADA',mse_x='NA') for m in MODOS))
            self.assertFalse(agrupar([p])[0][0].valido)

    def test_campos_comunes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.csv'
            p.write_text(''.join(linea(m) for m in MODOS[:-1])+linea('RESTA',banda_hi_hz='3000'))
            self.assertIn('inconsistentes',agrupar([p])[0][0].problema)

    def test_v1_no_exige_cuatro(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.csv'
            p.write_text(linea('FIR',1)+linea('RESTA',1))
            self.assertTrue(agrupar([p])[0][0].valido)

    def test_cli_tabla_y_duplicados(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.csv'; dest=Path(tmp)/'informe'
            p.write_text('ruido consola\n'+''.join(linea(m) for m in MODOS)*2)
            run=subprocess.run([sys.executable,str(PC/'analizar_metricas.py'),str(p),
                                '--salida',str(dest),'--etiqueta','P1','--sin-graficos'],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertEqual(len((dest/'metricas.csv').read_text().splitlines()),5)
            self.assertIn('repetidos omitidos: 4',(dest/'informe.md').read_text())
            self.assertIn('P1',(dest/'informe.md').read_text())

    def test_cli_avisa_incompleto(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.csv'; dest=Path(tmp)/'informe'
            p.write_text(linea('FIR')+'METRICAS,2,1\n')
            run=subprocess.run([sys.executable,str(PC/'analizar_metricas.py'),str(p),
                                '--salida',str(dest),'--sin-graficos'],capture_output=True,text=True)
            self.assertEqual(run.returncode,2)
            self.assertIn('incompleto',(dest/'informe.md').read_text())


class Monitor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Sustituir solo la base de PlatformIO; probar callbacks reales del filtro.
        module=types.ModuleType('platformio.device.monitor.filters.base')
        module.DeviceMonitorFilterBase=type('Base',(),{})
        cls.nombre=module.__name__; cls.previo=sys.modules.get(cls.nombre)
        sys.modules[cls.nombre]=module
        ruta=PC.parent/'firmware/nodo2/monitor/filter_metricas.py'
        spec=importlib.util.spec_from_file_location('filtro_prueba',ruta)
        cls.modulo=importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.modulo)

    @classmethod
    def tearDownClass(cls):
        if cls.previo is None: del sys.modules[cls.nombre]
        else: sys.modules[cls.nombre]=cls.previo

    def test_fragmentacion_passthrough_y_reinicio(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            self.modulo.PC_DIR=Path(tmp)
            filtro=self.modulo.GuardarMetricas()()
            texto='console\r\n'+linea('FIR')
            for c in texto:
                self.assertEqual(filtro.rx(c),c)
            filtro.rx('metricas\r\n'+linea('FIR'))
            filtro.rx('Nodos 2+3: arranque\n')
            filtro.rx(linea('RESTA'))
            filtro.cerrar()
            files=list((Path(tmp)/'resultados/metricas').glob('*.csv'))
            self.assertEqual(len(files),2)
            rows=[r for p in files for r in p.read_text().splitlines()]
            self.assertEqual(len(rows),3)
            self.assertTrue(all(r.startswith('METRICAS,') for r in rows))

    def test_linea_excesiva_y_truncada_no_contamina(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            self.modulo.PC_DIR=Path(tmp)
            filtro=self.modulo.GuardarMetricas()()
            filtro.rx('x'*5000); filtro.rx('resto\n')
            filtro.rx('METRICAS,2,1\n'); filtro.rx(linea('FIR'))
            filtro.rx('METRICAS,2,1')  # sin fin de línea, no guardar
            filtro.cerrar()
            files=list((Path(tmp)/'resultados/metricas').glob('*.csv'))
            self.assertEqual(sum(len(p.read_text().splitlines()) for p in files),1)


if __name__=='__main__':
    unittest.main()
