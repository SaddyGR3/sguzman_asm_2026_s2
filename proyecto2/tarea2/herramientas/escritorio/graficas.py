"""Gráficas nativas con Qt. Conservan los huecos de las mediciones inválidas."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

VERDE = '#008478'
AZUL = '#3368e8'
NARANJA = '#d5692e'


def finito(valor):
    return isinstance(valor, (float, int)) and math.isfinite(valor)


def numero(valor, decimales=0):
    if not finito(valor):
        return '—'
    return f'{valor:,.{decimales}f}'.replace(',', ' ').replace('.', ',')


class Grafica(QWidget):
    """Dibuja series recibidas de Banco, sin calcular ni interpolar RPM."""

    def __init__(self, titulo, series, parent=None, angular=False, grande=False):
        super().__init__(parent)
        self.titulo = titulo
        self.series = series
        self.angular = angular
        self.historia = []
        self.ventana = 30
        self.mostrar_cruda = True
        self._zona = QRectF()
        self._inicio = 0.0
        self._fin = 1.0
        self.setMouseTracking(True)
        self.setMinimumHeight(275 if grande else 205)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def establecer_datos(self, historia, ventana=30, mostrar_cruda=True):
        self.historia = historia
        self.ventana = ventana
        self.mostrar_cruda = mostrar_cruda
        self.update()

    def series_visibles(self):
        return [s for s in self.series if s[0] != 'rpm_cruda_grafica' or self.mostrar_cruda]

    def rango_tiempo(self):
        fin = self.historia[-1].get('t_pc_s', 0) if self.historia else 0
        inicio = max(0, fin - self.ventana)
        return inicio, max(fin, inicio + 1)

    def paintEvent(self, evento):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        exterior = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        painter.setPen(QPen(QColor('#dce3ed'), 1))
        painter.setBrush(QColor('#ffffff'))
        painter.drawRoundedRect(exterior, 10, 10)
        painter.setFont(QFont('sans-serif', 10, QFont.Weight.DemiBold))
        painter.setPen(QColor('#18243b'))
        painter.drawText(QRectF(16, 11, self.width() - 30, 22), self.titulo)
        painter.setFont(QFont('sans-serif', 8))
        x_leyenda = 17
        for clave, color, etiqueta in self.series_visibles():
            painter.setPen(QPen(QColor(color), 2))
            if clave == 'referencia_rpm':
                painter.setPen(QPen(QColor(color), 2, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(x_leyenda, 44), QPointF(x_leyenda + 12, 44))
            painter.setPen(QColor('#65718a'))
            ancho = painter.fontMetrics().horizontalAdvance(etiqueta)
            painter.drawText(QPointF(x_leyenda + 17, 48), etiqueta)
            x_leyenda += ancho + 33
        zona = QRectF(66, 65, max(1, self.width() - 85), max(1, self.height() - 101))
        self._zona = zona
        inicio, fin = self.rango_tiempo()
        self._inicio, self._fin = inicio, fin
        filas = [d for d in self.historia if finito(d.get('t_pc_s')) and d['t_pc_s'] >= inicio]
        series = self.series_visibles()
        valores = [d.get(clave) for d in filas for clave, _, _ in series if finito(d.get(clave))]
        minimo, maximo = min([0] + valores), max([1] + valores)
        if self.angular:
            minimo, maximo = 0, 95
        else:
            margen = (maximo - minimo) * .07
            maximo += margen
            if minimo < 0:
                minimo -= margen

        def x(t):
            return zona.left() + (t - inicio) / (fin - inicio) * zona.width()

        def y(v):
            return zona.bottom() - (v - minimo) / (maximo - minimo) * zona.height()

        painter.setFont(QFont('sans-serif', 8))
        for i in range(5):
            valor = minimo + (maximo - minimo) * i / 4
            altura = y(valor)
            painter.setPen(QColor('#e8edf4'))
            painter.drawLine(QPointF(zona.left(), altura), QPointF(zona.right(), altura))
            painter.setPen(QColor('#77849a'))
            painter.drawText(QRectF(1, altura - 8, 57, 17), Qt.AlignmentFlag.AlignRight,
                             numero(valor, 2 if maximo - minimo < 5 else 0))
        for i in range(6):
            t = inicio + (fin - inicio) * i / 5
            painter.setPen(QColor('#77849a'))
            painter.drawText(QRectF(x(t) - 27, zona.bottom() + 8, 54, 18),
                             Qt.AlignmentFlag.AlignCenter, numero(t, 1))
        if not valores:
            painter.setPen(QColor('#95a0b2'))
            painter.drawText(zona, Qt.AlignmentFlag.AlignCenter, 'Esperando datos de la fuente')
        painter.save()
        painter.setClipRect(zona.adjusted(-1, -1, 1, 1))
        for clave, color, _ in series:
            pen = QPen(QColor(color), 1.3 if clave == 'rpm_cruda_grafica' else 2)
            if clave == 'referencia_rpm':
                pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            camino = QPainterPath()
            trazando = False
            for dato in filas:
                valor = dato.get(clave)
                if not finito(valor):
                    trazando = False
                    continue
                punto = QPointF(x(dato['t_pc_s']), y(valor))
                if trazando:
                    camino.lineTo(punto)
                else:
                    camino.moveTo(punto)
                    trazando = True
            painter.drawPath(camino)
        painter.restore()

    def mouseMoveEvent(self, evento):
        if not self.historia or not self._zona.contains(evento.position()):
            QToolTip.hideText()
            return
        instante = self._inicio + (evento.position().x() - self._zona.left()) / self._zona.width() * (self._fin - self._inicio)
        dato = min(self.historia, key=lambda d: abs(d.get('t_pc_s', 0) - instante))
        lineas = [numero(dato.get('t_pc_s'), 2) + ' s']
        for clave, _, etiqueta in self.series_visibles():
            lineas.append(etiqueta + '  ' + numero(dato.get(clave), 2))
        if dato.get('cero_estimado') and any(s[0] == 'rpm_mostrada' for s in self.series):
            lineas.append('Cero estimado tras un segundo sin pulsos')
        QToolTip.showText(evento.globalPosition().toPoint(), '\n'.join(lineas), self)

    def leaveEvent(self, evento):
        QToolTip.hideText()
        super().leaveEvent(evento)
