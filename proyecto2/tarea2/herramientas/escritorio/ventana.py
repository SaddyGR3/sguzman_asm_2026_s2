"""Ventana nativa. Reutiliza Banco sin iniciar HTTP ni modificar el firmware.

Las conexiones, compilaciones de simulación y cierres de captura se ejecutan en
hilos para mantener la ventana disponible. Solo el hilo de Qt modifica widgets.
"""
from pathlib import Path
import signal
import time

from PySide6.QtCore import QThread, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from panel_frenado import Banco, RAIZ, seleccionar_puertos_usb
from .graficas import AZUL, NARANJA, VERDE, Grafica, numero

ACTIVOS = {'PREPARACION', 'DESCENSO_LIBRE', 'FIJO', 'PID'}
NOMBRES_CURVA = {'lineal': 'Lineal', 'exponencial': 'Exponencial normalizada', 'coseno': 'Coseno suave'}

ESTILO = '''
QMainWindow, QWidget#contenido { background: #f2f4f7; color: #18243b; }
QWidget { font-family: sans-serif; font-size: 12px; color: #18243b; }
QFrame#cabecera { background: #14243b; border-radius: 9px; }
QFrame#cabecera QLabel { color: white; background: transparent; }
QLabel#titulo { font-size: 12px; font-weight: 700; }
QLabel#conexionCabecera { color: #b9c9de; }
QWidget#lateral { background: #f9fafc; }
QGroupBox { background: #ffffff; border: 1px solid #dce3ed; border-radius: 9px; margin-top: 13px; padding: 13px 10px 9px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
QLabel#ayuda { color: #65718a; font-size: 11px; }
QLabel#aviso { color: #008478; }
QPushButton { background: #ffffff; border: 1px solid #cdd6e3; border-radius: 6px; padding: 8px 10px; }
QPushButton:hover { border-color: #3368e8; background: #edf3ff; }
QPushButton:disabled { color: #9aa5b5; background: #eef1f6; }
QPushButton#principal { background: #3368e8; color: white; border-color: #3368e8; font-weight: 600; }
QPushButton#principal:disabled { background: #a6bbed; border-color: #a6bbed; }
QPushButton#cancelar { background: #fff0f2; color: #b42140; border-color: #edb8c4; font-weight: 600; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: white; border: 1px solid #cdd6e3; border-radius: 5px; padding: 5px; min-height: 20px; }
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { color: #929cac; background: #f0f2f6; }
QFrame#tarjeta { background: white; border: 1px solid #dce3ed; border-radius: 9px; }
QLabel#nombreTarjeta { font-size: 10px; color: #65718a; }
QLabel#valorTarjeta { font-size: 24px; font-weight: 650; }
QLabel#unidadTarjeta { color: #65718a; font-size: 10px; }
QTableWidget, QPlainTextEdit { background: white; border: none; gridline-color: #edf0f5; selection-background-color: #e4eeff; }
QHeaderView::section { background: #f4f7fb; border: none; padding: 7px; color: #65718a; }
QPlainTextEdit { font-family: monospace; font-size: 11px; }
QScrollArea { border: none; background: transparent; }
'''


class Trabajo(QThread):
    resultado = Signal(object)
    error = Signal(str)

    def __init__(self, funcion):
        super().__init__()
        self.funcion = funcion

    def run(self):
        try:
            self.resultado.emit(self.funcion())
        except Exception as exc:
            self.error.emit(str(exc))


def listar_puertos():
    from serial.tools.list_ports import comports
    return seleccionar_puertos_usb(comports())


class VentanaBanco(QMainWindow):
    def __init__(self, banco=None, busqueda=None, temporizadores=True):
        super().__init__()
        self.banco = banco if banco is not None else Banco(RAIZ.parent / 'capturas' / 'escritorio')
        self.busqueda = busqueda or listar_puertos
        self._trabajos = {}
        self.actual = None
        self.vista = None
        self.pausado = False
        self.ultimo_evento = 0
        self._puertos = None
        self._cierre_al_terminar = False
        self._espera_cancelacion = None
        self._estado_salida = None
        self._cierre_sin_confirmacion = False
        self.setWindowTitle('Sistema de control de frenado')
        self.resize(1440, 940)
        self.setMinimumSize(1080, 720)
        self.setStyleSheet(ESTILO)
        self._construir()
        self.reloj = QTimer(self)
        self.reloj.setInterval(200)
        self.reloj.timeout.connect(self.actualizar)
        self.reloj_puertos = QTimer(self)
        self.reloj_puertos.setInterval(2500)
        self.reloj_puertos.timeout.connect(self.buscar_puertos)
        if temporizadores:
            self.reloj.start()
            self.reloj_puertos.start()
            QTimer.singleShot(0, self.buscar_puertos)
        self.actualizar()

    def _ayuda(self, texto):
        etiqueta = QLabel(texto)
        etiqueta.setObjectName('ayuda')
        etiqueta.setWordWrap(True)
        etiqueta.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        return etiqueta

    def _boton(self, texto, funcion, nombre=None):
        boton = QPushButton(texto)
        if nombre:
            boton.setObjectName(nombre)
        boton.clicked.connect(funcion)
        return boton

    def _grupo(self, titulo, padre):
        grupo = QGroupBox(titulo)
        caja = QVBoxLayout(grupo)
        caja.setSpacing(8)
        padre.addWidget(grupo)
        return grupo, caja

    def _construir(self):
        contenedor = QWidget()
        contenedor.setObjectName('contenido')
        self.setCentralWidget(contenedor)
        raiz = QVBoxLayout(contenedor)
        raiz.setContentsMargins(12, 12, 12, 12)
        cabecera = QFrame()
        cabecera.setObjectName('cabecera')
        cab = QHBoxLayout(cabecera)
        titulo = QLabel('Sistema de control de frenado')
        titulo.setObjectName('titulo')
        self.conexion_cabecera = QLabel('Sin conexión')
        self.conexion_cabecera.setObjectName('conexionCabecera')
        cab.addWidget(titulo, 1)
        cab.addWidget(self.conexion_cabecera)
        raiz.addWidget(cabecera)
        cuerpo = QHBoxLayout()
        raiz.addLayout(cuerpo, 1)
        lateral_scroll = QScrollArea()
        lateral_scroll.setWidgetResizable(True)
        lateral_scroll.setFixedWidth(328)
        lateral_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lateral = QWidget()
        lateral.setObjectName('lateral')
        lateral_scroll.setWidget(lateral)
        controles = QVBoxLayout(lateral)
        controles.setContentsMargins(5, 0, 9, 6)
        controles.setSpacing(6)
        cuerpo.addWidget(lateral_scroll)
        _, caja = self._grupo('Fuente de datos', controles)
        self.fuente = QComboBox()
        self.fuente.addItem('ESP32 · puerto USB', 'ESP32')
        self.fuente.addItem('Simulación · planta ficticia', 'SIMULACION')
        self.fuente.currentIndexChanged.connect(self.cambiar_fuente)
        caja.addWidget(self.fuente)
        self.campos_usb = QWidget()
        usb = QVBoxLayout(self.campos_usb)
        usb.setContentsMargins(0, 0, 0, 0)
        usb.addWidget(QLabel('Puerto a 115200 baudios'))
        fila = QHBoxLayout()
        self.puerto = QComboBox()
        self.puerto.setEditable(True)
        self.puerto.setMinimumContentsLength(12)
        self.puerto.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.puerto.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.puerto.lineEdit().setPlaceholderText('Detección automática o puerto manual')
        self.boton_buscar = self._boton('Buscar', lambda: self.buscar_puertos(forzar=True))
        fila.addWidget(self.puerto, 1)
        fila.addWidget(self.boton_buscar)
        usb.addLayout(fila)
        usb.addWidget(self._ayuda('La búsqueda no abre el puerto. Cierra el monitor de PlatformIO antes de conectar.'))
        caja.addWidget(self.campos_usb)
        self.campos_sim = QWidget()
        sim = QVBoxLayout(self.campos_sim)
        sim.setContentsMargins(0, 0, 0, 0)
        self.rpm_objetivo = QSpinBox()
        self.rpm_objetivo.setRange(100, 2000)
        self.rpm_objetivo.setSingleStep(100)
        self.rpm_objetivo.setValue(1500)
        sim.addWidget(QLabel('Objetivo al preparar · RPM'))
        sim.addWidget(self.rpm_objetivo)
        fila_ganancias = QHBoxLayout()
        fila_ganancias.setSpacing(6)
        self.ganancias = {}
        for nombre, valor in (('Kp', .005), ('Ki', 0), ('Kd', 0)):
            campo = QDoubleSpinBox()
            campo.setRange(0, 1)
            campo.setDecimals(4)
            campo.setSingleStep(.001)
            campo.setValue(valor)
            self.ganancias[nombre.lower()] = campo
            campo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            columna = QVBoxLayout()
            columna.setSpacing(4)
            columna.addWidget(QLabel(nombre))
            columna.addWidget(campo)
            fila_ganancias.addLayout(columna, 1)
        sim.addLayout(fila_ganancias)
        sim.addWidget(self._ayuda('Ganancias solo de simulación. El objetivo debe superar 1400 RPM para completar el ciclo.'))
        caja.addWidget(self.campos_sim)
        fila = QHBoxLayout()
        self.boton_conectar = self._boton('Conectar ESP32', self.conectar, 'principal')
        self.boton_desconectar = self._boton('Desconectar', self.desconectar)
        fila.addWidget(self.boton_conectar)
        fila.addWidget(self.boton_desconectar)
        caja.addLayout(fila)
        self.aviso = QLabel('Conecta la ESP32 o selecciona la simulación.')
        self.aviso.setObjectName('aviso')
        self.aviso.setTextFormat(Qt.TextFormat.PlainText)
        self.aviso.setWordWrap(True)
        caja.addWidget(self.aviso)

        _, caja = self._grupo('Ensayo automático', controles)
        caja.addWidget(QLabel('Figura de referencia'))
        self.curva = QComboBox()
        for codigo, nombre in NOMBRES_CURVA.items():
            self.curva.addItem(nombre, codigo)
        caja.addWidget(self.curva)
        self.boton_curva = self._boton('Aplicar figura', lambda: self.enviar('curva_' + self.curva.currentData()))
        caja.addWidget(self.boton_curva)
        self.estado_curva = self._ayuda('ESP32 · lineal o exponencial. Aplicar figura antes del ensayo.')
        caja.addWidget(self.estado_curva)
        fila = QHBoxLayout()
        self.duracion = QDoubleSpinBox()
        self.duracion.setRange(1, 30)
        self.duracion.setSingleStep(.5)
        self.duracion.setValue(6)
        self.duracion.setSuffix(' s')
        self.boton_duracion = self._boton('Enviar duración', lambda: self.enviar('tiempo' + str(round(self.duracion.value() * 1000))))
        fila.addWidget(self.duracion)
        fila.addWidget(self.boton_duracion)
        caja.addLayout(fila)
        self.boton_preparar = self._boton('Preparar', lambda: self.enviar('auto_preparar'))
        self.boton_pid = self._boton('Iniciar ciclo PID', lambda: self.iniciar_ciclo('auto_pid'))
        fila = QHBoxLayout()
        fila.addWidget(self.boton_preparar)
        fila.addWidget(self.boton_pid)
        caja.addLayout(fila)
        self.boton_libre = self._boton('Ciclo libre · sin freno', lambda: self.iniciar_ciclo('auto_fijo45'))
        caja.addWidget(self.boton_libre)
        caja.addWidget(QLabel('Ángulo fijo · grados'))
        fila = QHBoxLayout()
        self.angulo_fijo = QSpinBox()
        self.angulo_fijo.setRange(25, 45)
        self.angulo_fijo.setValue(30)
        self.boton_fijo = self._boton('Iniciar ciclo fijo', lambda: self.iniciar_ciclo('auto_fijo' + str(self.angulo_fijo.value())), 'principal')
        fila.addWidget(self.angulo_fijo)
        fila.addWidget(self.boton_fijo)
        caja.addLayout(fila)
        caja.addWidget(self._ayuda('Apaga a 1400 RPM, espera con freno liberado y comienza el ensayo al bajar a 1300 RPM. La duración se envía al iniciar desde reposo.'))
        self.boton_cancelar = self._boton('Cancelar y liberar freno', lambda: self.enviar('cancelar'), 'cancelar')
        caja.addWidget(self.boton_cancelar)
        fila = QHBoxLayout()
        self.boton_estado = self._boton('Consultar estado', lambda: self.enviar('estado'))
        self.boton_pico = self._boton('Simular pico', lambda: self.enviar('pico_simulado'))
        fila.addWidget(self.boton_estado)
        fila.addWidget(self.boton_pico)
        caja.addLayout(fila)

        _, caja = self._grupo('Control manual y calibración', controles)
        fila = QHBoxLayout()
        self.angulo_manual = QSpinBox()
        self.angulo_manual.setRange(0, 90)
        self.angulo_manual.setValue(45)
        self.angulo_manual.setSuffix('°')
        self.boton_angulo = self._boton('Enviar ángulo', lambda: self.enviar('g' + str(self.angulo_manual.value())))
        fila.addWidget(self.angulo_manual)
        fila.addWidget(self.boton_angulo)
        caja.addLayout(fila)
        caja.addWidget(self._ayuda('Rango manual de 0 a 90°. Para ensayos automáticos se usa 25 a 45°.'))
        fila = QHBoxLayout()
        self.boton_motor_on = self._boton('Encender motor', lambda: self.enviar('motor_on'))
        self.boton_motor_off = self._boton('Apagar motor', lambda: self.enviar('motor_off'))
        fila.addWidget(self.boton_motor_on)
        fila.addWidget(self.boton_motor_off)
        caja.addLayout(fila)
        fila = QHBoxLayout()
        self.comando = QLineEdit()
        self.comando.setPlaceholderText('Comando del firmware')
        self.boton_comando = self._boton('Enviar', self.enviar_texto)
        self.comando.returnPressed.connect(self.enviar_texto)
        fila.addWidget(self.comando)
        fila.addWidget(self.boton_comando)
        caja.addLayout(fila)
        fila = QHBoxLayout()
        self.boton_sensor_on = self._boton('Activar GPIO34', lambda: self.enviar('sensor_on'))
        self.boton_sensor_off = self._boton('Desactivar', lambda: self.enviar('sensor_off'))
        fila.addWidget(self.boton_sensor_on)
        fila.addWidget(self.boton_sensor_off)
        caja.addLayout(fila)
        _, caja = self._grupo('Captura automática', controles)
        self.carpeta = self._ayuda('Se crea al conectar la fuente.')
        self.carpeta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        caja.addWidget(self.carpeta)
        self.boton_carpeta = self._boton('Abrir carpeta de captura', self.abrir_carpeta)
        caja.addWidget(self.boton_carpeta)
        controles.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        centro = QWidget()
        centro.setMinimumWidth(720)
        principal = QVBoxLayout(centro)
        principal.setContentsMargins(5, 0, 5, 5)
        principal.setSpacing(12)
        scroll.setWidget(centro)
        cuerpo.addWidget(scroll, 1)
        fila = QHBoxLayout()
        self.estado_conexion = QLabel('Sin conexión')
        self.estado_conexion.setWordWrap(True)
        fila.addWidget(self.estado_conexion, 1)
        self.ventana_tiempo = QComboBox()
        for segundos in (15, 30, 60, 300):
            self.ventana_tiempo.addItem('Últimos ' + str(segundos) + ' s', segundos)
        self.ventana_tiempo.setCurrentIndex(1)
        self.ventana_tiempo.currentIndexChanged.connect(self.redibujar)
        self.boton_pausa = self._boton('Pausar vista', self.alternar_pausa)
        self.boton_pausa.setMinimumWidth(116)
        self.boton_imagen = self._boton('Guardar gráfica', self.guardar_grafica)
        fila.addWidget(self.ventana_tiempo)
        fila.addWidget(self.boton_pausa)
        fila.addWidget(self.boton_imagen)
        principal.addLayout(fila)
        tarjetas = QGridLayout()
        self.valores = {}
        self.unidades = {}
        especificaciones = (
            ('rpm_mostrada', 'VELOCIDAD', 'RPM'), ('referencia_rpm', 'REFERENCIA', 'RPM'),
            ('error_rpm', 'ERROR', 'medida − referencia'), ('angulo', 'ORDEN AL SERVO', 'grados'),
            ('u_aplicada', 'ACCIÓN AL SERVO', 'normalizada · 0 a 1'), ('tiempo', 'TIEMPO DE ENSAYO', 'segundos'),
        )
        for columna, (clave, nombre, unidad) in enumerate(especificaciones):
            tarjeta = QFrame()
            tarjeta.setObjectName('tarjeta')
            caja = QVBoxLayout(tarjeta)
            titulo = QLabel(nombre)
            titulo.setObjectName('nombreTarjeta')
            valor = QLabel('—')
            valor.setObjectName('valorTarjeta')
            etiqueta = QLabel(unidad)
            etiqueta.setObjectName('unidadTarjeta')
            etiqueta.setWordWrap(True)
            for widget in (titulo, valor, etiqueta):
                caja.addWidget(widget)
            self.valores[clave] = valor
            self.unidades[clave] = etiqueta
            tarjetas.addWidget(tarjeta, 0, columna)
        principal.addLayout(tarjetas)
        self.cruda = QCheckBox('Mostrar velocidad cruda · incluye picos')
        self.cruda.setChecked(True)
        self.cruda.toggled.connect(self.redibujar)
        principal.addWidget(self.cruda)
        self.graficas = {}
        series = {
            'velocidad': ('Seguimiento de velocidad · RPM', [('rpm_mostrada', VERDE, 'Medida / cero estimado'), ('referencia_rpm', AZUL, 'Referencia'), ('rpm_cruda_grafica', NARANJA, 'Cruda')]),
            'accion': ('Acción de frenado · normalizada', [('u_solicitada', '#a183c4', 'Solicitada'), ('pid_u_limitada', AZUL, 'Limitada'), ('u_aplicada', VERDE, 'Al servo')]),
            'angulo': ('Orden angular · grados', [('angulo', NARANJA, 'Servo')]),
            'error': ('Error de seguimiento · RPM', [('error_rpm', '#c33c51', 'Error')]),
            'pid': ('Contribuciones del controlador', [('pid_p', AZUL, 'P'), ('pid_i', VERDE, 'I'), ('pid_d', NARANJA, 'D')]),
        }
        for clave, (titulo, datos) in series.items():
            self.graficas[clave] = Grafica(titulo, datos, angular=clave == 'angulo', grande=clave == 'velocidad')
        principal.addWidget(self.graficas['velocidad'])
        secundarias = QGridLayout()
        for i, clave in enumerate(('accion', 'angulo', 'error', 'pid')):
            secundarias.addWidget(self.graficas[clave], i // 2, i % 2)
        principal.addLayout(secundarias)
        self.paneles_diagnostico = QWidget()
        paneles = QHBoxLayout(self.paneles_diagnostico)
        paneles.setContentsMargins(0, 0, 0, 0)
        paneles.setSpacing(12)
        self.cajas_diagnostico = []
        for titulo in ('Señal y temporización', 'Eventos y órdenes', 'Sensor GPIO34'):
            grupo = QGroupBox(titulo)
            grupo.setMinimumWidth(0)
            grupo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            paneles.addWidget(grupo, 1)
            self.cajas_diagnostico.append(grupo)
        self.diagnostico = QGridLayout(self.cajas_diagnostico[0])
        self.diagnostico.setHorizontalSpacing(8)
        self.diagnostico.setVerticalSpacing(8)
        self.diagnostico.setColumnStretch(0, 3)
        self.diagnostico.setColumnStretch(1, 2)
        self.etiquetas_diagnostico = {}
        self.eventos = QPlainTextEdit()
        self.eventos.setReadOnly(True)
        self.eventos.setMaximumBlockCount(500)
        caja_eventos = QVBoxLayout(self.cajas_diagnostico[1])
        caja_eventos.addWidget(self.eventos)
        caja_sensor = QVBoxLayout(self.cajas_diagnostico[2])
        self.estado_sensor = QLabel('Diagnóstico GPIO34 desactivado')
        self.estado_sensor.setWordWrap(True)
        self.estado_sensor.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        caja_sensor.addWidget(self.estado_sensor)
        self.tabla_sensor = QTableWidget(0, 6)
        self.tabla_sensor.setHorizontalHeaderLabels(['ISR', 't · µs', 'Δt · µs', 'Nivel', 'Acept.', 'Cortos'])
        self.tabla_sensor.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_sensor.verticalHeader().hide()
        self.tabla_sensor.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        caja_sensor.addWidget(self.tabla_sensor)
        principal.addWidget(self.paneles_diagnostico)
        principal.addWidget(self._ayuda('El cero tras un segundo sin pulsos es estimado y no se usa como RPM válida del PID. Pausar la vista no pausa la captura. El eje horizontal muestra segundos desde la conexión.'))
        self.botones_comando = [self.boton_curva, self.boton_duracion, self.boton_preparar,
            self.boton_pid, self.boton_libre, self.boton_fijo, self.boton_cancelar,
            self.boton_estado, self.boton_pico, self.boton_angulo, self.boton_comando,
            self.boton_motor_on, self.boton_motor_off, self.boton_sensor_on, self.boton_sensor_off]
        self.campos_sim.setVisible(False)

    def _ocupado(self):
        return any(k in self._trabajos for k in ('conectar', 'desconectar'))

    def _ejecutar(self, nombre, funcion, resultado):
        if nombre in self._trabajos:
            return
        trabajo = Trabajo(funcion)
        trabajo.nombre = nombre
        trabajo.al_resultado = resultado
        self._trabajos[nombre] = trabajo
        trabajo.resultado.connect(self._resultado_trabajo)
        trabajo.error.connect(self._error_trabajo)
        trabajo.finished.connect(self._termino_trabajo)
        trabajo.start()
        self._controles()

    @Slot(object)
    def _resultado_trabajo(self, resultado):
        self.sender().al_resultado(resultado)

    @Slot(str)
    def _error_trabajo(self, texto):
        self.mensaje(texto, error=True)

    @Slot()
    def _termino_trabajo(self):
        self._finalizar_trabajo(self.sender().nombre)

    def _finalizar_trabajo(self, nombre):
        trabajo = self._trabajos.pop(nombre)
        trabajo.deleteLater()
        self._controles()
        if self._cierre_al_terminar and not self._trabajos:
            self._cierre_al_terminar = False
            QTimer.singleShot(0, self.close)

    def mensaje(self, texto, error=False):
        self.aviso.setText(texto)
        self.aviso.setStyleSheet('color: #b42140;' if error else 'color: #008478;')

    def cambiar_fuente(self):
        sim = self.fuente.currentData() == 'SIMULACION'
        self.campos_sim.setVisible(sim)
        self.campos_usb.setVisible(not sim)
        self.boton_conectar.setText('Iniciar simulación' if sim else 'Conectar ESP32')
        if not sim:
            self.curva.setCurrentIndex(0)
            self.buscar_puertos(forzar=True)
        self._controles()

    def buscar_puertos(self, forzar=False):
        if self.fuente.currentData() != 'ESP32' or self._ocupado() or (self.actual and self.actual.get('activo')):
            return
        self._ejecutar('buscar', self.busqueda, lambda d: self.mostrar_puertos(d, forzar))

    def mostrar_puertos(self, datos, forzar=False):
        puertos = datos['puertos']
        anterior = self.puerto.currentText().strip()
        if puertos != self._puertos:
            self.puerto.blockSignals(True)
            self.puerto.clear()
            self.puerto.addItems(puertos)
            elegido = anterior if anterior in puertos else puertos[0] if len(puertos) == 1 else anterior if not puertos else ''
            self.puerto.setCurrentText(elegido)
            self.puerto.blockSignals(False)
            self._puertos = list(puertos)
            forzar = True
        if len(puertos) == 1 and not self.puerto.currentText().strip():
            self.puerto.setCurrentText(puertos[0])
        if forzar:
            if len(puertos) == 1:
                self.mensaje('Puerto USB seleccionado · ' + self.puerto.currentText())
            elif len(puertos) > 1:
                self.mensaje('Hay varios dispositivos USB. Elige el puerto de la ESP32.')
            else:
                self.mensaje(datos.get('aviso', 'No hay puertos USB. Puedes probar la simulación.'))

    def conectar(self):
        if self._ocupado() or (self.actual and self.actual.get('activo')):
            return
        opciones = dict(fuente=self.fuente.currentData(), puerto=self.puerto.currentText().strip(),
            rpm=self.rpm_objetivo.value(), duracion=self.duracion.value(), curva=self.curva.currentData(),
            interfaz='escritorio', **{k: campo.value() for k, campo in self.ganancias.items()})
        id_anterior = self.banco.secuencia

        def abrir():
            if opciones['fuente'] == 'ESP32' and not opciones['puerto']:
                dispositivos = self.busqueda()['puertos']
                if len(dispositivos) != 1:
                    raise ValueError('Elige el puerto USB de la ESP32.' if dispositivos else 'No se detecta la ESP32. Conéctala o selecciona Simulación.')
                opciones['puerto'] = dispositivos[0]
            self.banco.iniciar(opciones)
            return opciones

        def conectado(datos):
            self._cierre_sin_confirmacion = False
            self.ultimo_evento = id_anterior
            self.eventos.clear()
            self.pausado = False
            self.boton_pausa.setText('Pausar vista')
            if datos['puerto']:
                self.puerto.setCurrentText(datos['puerto'])
            self.mensaje('Fuente conectada. Captura automática activa.')
            self.actualizar()

        self.mensaje('Preparando la fuente y la captura…')
        self._ejecutar('conectar', abrir, conectado)

    def enviar(self, comando):
        try:
            self.banco.enviar(comando)
            self.mensaje('Orden enviada · ' + comando + ' · comprueba su evento')
            return True
        except (ValueError, RuntimeError) as exc:
            self.mensaje(str(exc), error=True)
            return False

    def enviar_texto(self):
        texto = self.comando.text().strip()
        if texto and self.enviar(texto):
            self.comando.clear()

    def iniciar_ciclo(self, comando):
        estado = self.banco.estado_actual()
        if estado.get('ultimo', {}).get('modo') not in ACTIVOS:
            if not self.enviar('tiempo' + str(round(self.duracion.value() * 1000))):
                return
        self.enviar(comando)

    def alternar_pausa(self):
        self.pausado = not self.pausado
        self.boton_pausa.setText('Reanudar vista' if self.pausado else 'Pausar vista')
        if not self.pausado:
            self.actualizar()

    def redibujar(self):
        if self.vista:
            for grafica in self.graficas.values():
                grafica.establecer_datos(self.vista['historia'], self.ventana_tiempo.currentData(), self.cruda.isChecked())

    def _controles(self):
        estado = self.actual or {}
        conectado = bool(estado.get('activo'))
        ocupado = self._ocupado() or self._espera_cancelacion is not None
        real = (estado.get('fuente') if conectado else self.fuente.currentData()) == 'ESP32'
        en_ensayo = conectado and estado.get('ultimo', {}).get('modo') in ACTIVOS
        self.fuente.setEnabled(not conectado and not ocupado)
        self.campos_sim.setEnabled(not conectado and not ocupado)
        self.puerto.setEnabled(not conectado and not ocupado)
        self.boton_buscar.setEnabled(not conectado and not ocupado and 'buscar' not in self._trabajos)
        self.boton_conectar.setEnabled(not conectado and not ocupado)
        self.boton_desconectar.setEnabled(conectado and not ocupado)
        for boton in self.botones_comando:
            boton.setEnabled(conectado and not ocupado)
        self.boton_pico.setEnabled(conectado and not real and not ocupado)
        self.boton_sensor_on.setEnabled(conectado and real and not en_ensayo and not ocupado)
        self.boton_sensor_off.setEnabled(conectado and real and not en_ensayo and not ocupado)
        for indice in range(self.curva.count()):
            self.curva.model().item(indice).setEnabled(not real or self.curva.itemData(indice) != 'coseno')
        if real and self.curva.currentData() == 'coseno':
            self.curva.setCurrentIndex(0)
        self.curva.setEnabled(not en_ensayo and not ocupado)
        self.boton_curva.setEnabled(conectado and not en_ensayo and not ocupado)
        self.boton_carpeta.setEnabled(bool(estado.get('carpeta')))
        if real:
            activa = NOMBRES_CURVA.get(estado.get('curva'), 'sin confirmar')
            self.estado_curva.setText('ESP32 · figura activa ' + activa + '. Pulsa Aplicar figura para confirmar la selección.')
        else:
            self.estado_curva.setText('Figura activa · ' + NOMBRES_CURVA.get(estado.get('curva'), self.curva.currentText()))

    def actualizar(self):
        estado = self.banco.estado_actual()
        self.actual = estado
        d = estado.get('ultimo', {})
        edad = estado.get('edad_diag_s')
        calidad = 'esperando diagnóstico' if edad is None else 'diagnóstico hace ' + numero(edad, 1) + ' s'
        if estado.get('activo') and (edad is None or edad > 1):
            calidad += ' · SIN DATOS RECIENTES'
        fuente = 'ESP32' if estado.get('fuente') == 'ESP32' else 'Simulación'
        self.conexion_cabecera.setText(fuente + ' conectada' if estado.get('activo') else 'Sin conexión')
        self.estado_conexion.setText(('● Conectado' if estado.get('activo') else '○ Desconectado') +
            ' · ' + estado.get('fuente', '') + ' · ' + d.get('modo', 'REPOSO') + ' · ' + calidad)
        self.carpeta.setText(estado.get('carpeta') or 'Se crea al conectar la fuente.')
        if estado.get('error'):
            self.mensaje(estado['error'], error=True)
        for evento in estado.get('eventos', []):
            if evento['id'] > self.ultimo_evento:
                self.eventos.appendPlainText(evento['hora'] + '  ' + evento['texto'])
                self.ultimo_evento = evento['id']
        if not self.pausado:
            self.vista = estado
            self._presentar(d, estado)
            self.redibujar()
        self._controles()
        if self._espera_cancelacion is not None:
            cerrar = self._estado_salida
            confirmado = d.get('modo') == 'CANCELADO' and d.get('motor_encendido') == 0 and estado.get('activo')
            # Exigir una muestra posterior al comando, no un CANCELADO de otra corrida.
            nuevo = any(e['id'] > self._espera_cancelacion[1] and 'ENSAYO_CANCELADO' in e['texto'] for e in estado.get('eventos', []))
            if confirmado and nuevo:
                self._espera_cancelacion = None
                self._desconectar_ahora(cerrar)
            elif time.monotonic() > self._espera_cancelacion[0]:
                self._espera_cancelacion = None
                self.mensaje('No se confirmó la cancelación. La ventana seguirá abierta. Comprueba el motor y la comunicación.', error=True)
                self._controles()

    def _presentar(self, d, estado):
        for clave, etiqueta in self.valores.items():
            valor = d.get(clave) if clave != 'tiempo' else (d['tiempo_ensayo_ms'] / 1000 if d.get('tiempo_ensayo_ms') is not None else None)
            etiqueta.setText(numero(valor, 2 if clave == 'u_aplicada' else 1 if clave == 'tiempo' else 0))
        self.unidades['rpm_mostrada'].setText('RPM · cero estimado' if d.get('cero_estimado') else 'RPM')
        campos = [
            ('Modo', d.get('modo', '—')), ('Medición', d.get('estado_medicion', '—')),
            ('Estado PID', d.get('pid_estado', '—')),
            ('Motor ordenado', '—' if d.get('motor_encendido') is None else 'ENCENDIDO' if d['motor_encendido'] else 'APAGADO'),
            ('RPM cruda', numero(d.get('rpm_cruda'))), ('RPM del CSV histórico', numero(d.get('rpm_csv'))),
            ('Antigüedad · ms', numero(d['antiguedad_us'] / 1000, 1) if d.get('antiguedad_us') is not None else '—'),
            ('Pulsos aceptados', numero(d.get('pulsos_aceptados'))), ('Pulsos cortos rechazados', numero(d.get('pulsos_rechazados'))),
            ('Saltos rechazados', numero(d.get('saltos_rechazados'))), ('Pérdidas de cola', numero(d.get('perdidos_cola'))),
            ('Último periodo rechazado · µs', numero(d.get('ultimo_periodo_rechazado_us'))),
            ('Intervalo PID · ms', numero(d['pid_dt_us'] / 1000, 1) if d.get('pid_dt_us') is not None else '—'),
            ('Periodos omitidos', numero(d.get('pid_omitidos'))),
            ('Tiempo de cálculo · µs', 'No medido en ESP32' if estado.get('fuente') == 'SIMULACION' else numero(d.get('pid_tiempo_calculo_us'))),
        ]
        for fila, (nombre, valor) in enumerate(campos):
            if nombre not in self.etiquetas_diagnostico:
                etiqueta = QLabel(nombre)
                dato = QLabel()
                for elemento in (etiqueta, dato):
                    elemento.setWordWrap(True)
                    elemento.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
                etiqueta.setStyleSheet('color: #65718a; font-size: 11px;')
                dato.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.diagnostico.addWidget(etiqueta, fila, 0)
                self.diagnostico.addWidget(dato, fila, 1)
                self.etiquetas_diagnostico[nombre] = dato
            self.etiquetas_diagnostico[nombre].setText(str(valor))
        sensor = estado.get('sensor', {})
        self.estado_sensor.setText(('Diagnóstico activo' if sensor.get('activo') else 'Diagnóstico desactivado') +
            ' · nivel ' + numero(sensor.get('nivel')) + ' · pérdidas ' + str(sensor.get('perdidos', 0)))
        cambios = sensor.get('cambios', [])
        self.tabla_sensor.setRowCount(len(cambios))
        for fila, cambio in enumerate(cambios):
            for columna, clave in enumerate(('numero', 'tiempo_us', 'intervalo_us', 'nivel', 'aceptados', 'cortos')):
                self.tabla_sensor.setItem(fila, columna, QTableWidgetItem(str(cambio[clave])))

    def confirmar_cancelacion(self, cerrar):
        dialogo = QMessageBox(self)
        dialogo.setWindowTitle('Hay una prueba o un motor activo')
        dialogo.setText('Para ' + ('cerrar la aplicación' if cerrar else 'desconectar') + ', primero se enviará Cancelar y se esperará su confirmación.')
        aceptar = dialogo.addButton('Cancelar y ' + ('cerrar' if cerrar else 'desconectar'), QMessageBox.ButtonRole.AcceptRole)
        volver = dialogo.addButton('Volver', QMessageBox.ButtonRole.RejectRole)
        dialogo.setDefaultButton(volver)
        dialogo.exec()
        return dialogo.clickedButton() is aceptar

    def confirmar_sin_conexion(self, cerrar):
        dialogo = QMessageBox(self)
        dialogo.setWindowTitle('Sin comunicación con la ESP32')
        dialogo.setText('El último estado recibido indicaba una prueba o un motor activo. Sin conexión no se puede confirmar su parada desde la aplicación.')
        aceptar = dialogo.addButton('Cerrar ventana' if cerrar else 'Cerrar captura', QMessageBox.ButtonRole.AcceptRole)
        volver = dialogo.addButton('Volver', QMessageBox.ButtonRole.RejectRole)
        dialogo.setDefaultButton(volver)
        dialogo.exec()
        return dialogo.clickedButton() is aceptar

    def desconectar(self, cerrar=False):
        if self._ocupado() or self._trabajos:
            if cerrar:
                self._cierre_al_terminar = True
            return
        estado = self.banco.estado_actual()
        d = estado.get('ultimo', {})
        activo = d.get('modo') in ACTIVOS or d.get('motor_encendido') == 1
        if not estado.get('activo') and estado.get('fuente') == 'ESP32' and activo:
            if not self.confirmar_sin_conexion(cerrar):
                return
            self._cierre_sin_confirmacion = True
        if estado.get('activo') and estado.get('fuente') == 'ESP32' and activo:
            if not self.confirmar_cancelacion(cerrar):
                return
            id_anterior = self.banco.secuencia
            if self.enviar('cancelar'):
                self._estado_salida = cerrar
                self._espera_cancelacion = (time.monotonic() + 4, id_anterior)
                self.mensaje('Esperando confirmación de cancelación…')
                self._controles()
            return
        self._desconectar_ahora(cerrar)

    def _desconectar_ahora(self, cerrar=False):
        def listo(_):
            self.mensaje('Fuente desconectada. Captura guardada.')
            self.actualizar()
            if cerrar:
                self._cierre_al_terminar = True
        self._ejecutar('desconectar', self.banco.desconectar, listo)

    def closeEvent(self, evento):
        if self._espera_cancelacion is not None:
            evento.ignore()
            return
        estado = self.banco.estado_actual()
        d = estado.get('ultimo', {})
        sin_parada = estado.get('fuente') == 'ESP32' and (d.get('modo') in ACTIVOS or d.get('motor_encendido') == 1)
        if self._trabajos or estado.get('activo') or (sin_parada and not self._cierre_sin_confirmacion):
            evento.ignore()
            self.desconectar(cerrar=True)
            return
        self.reloj.stop()
        self.reloj_puertos.stop()
        evento.accept()

    def abrir_carpeta(self):
        ruta = self.banco.estado_actual().get('carpeta')
        if ruta:
            QDesktopServices.openUrl(QUrl.fromLocalFile(ruta))

    def guardar_grafica(self):
        archivo, _ = QFileDialog.getSaveFileName(self, 'Guardar gráfica de velocidad', 'seguimiento_frenado.png', 'Imagen PNG (*.png)')
        if archivo:
            if not Path(archivo).suffix:
                archivo += '.png'
            if self.graficas['velocidad'].grab().save(archivo, 'PNG'):
                self.mensaje('Gráfica guardada · ' + archivo)
            else:
                self.mensaje('No se pudo guardar la gráfica.', error=True)


def ejecutar(salida=None, simulacion=False):
    app = QApplication.instance() or QApplication([])
    ventana = VentanaBanco(Banco(salida or RAIZ.parent / 'capturas' / 'escritorio'))
    ventana.show()
    if simulacion:
        ventana.fuente.setCurrentIndex(1)
        QTimer.singleShot(0, ventana.conectar)
    anterior = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, lambda *_: ventana.close())
    try:
        return app.exec()
    finally:
        signal.signal(signal.SIGINT, anterior)
