"""Genera la figura teórica usada por ASMTarea2.tex; no usa datos medidos."""

from math import exp
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen


def main() -> None:
    app = QGuiApplication([])
    image = QImage(1200, 700, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    left, top, right, bottom = 115, 75, 1140, 560
    blue = QColor("#2367aa")
    gray = QColor("#d9e0e8")
    dark = QColor("#243447")

    def px(t: float) -> float:
        return left + t / 1.2 * (right - left)

    def py(w: float) -> float:
        return bottom - (w - 5) / 25 * (bottom - top)

    painter.setFont(QFont("Arial", 16))
    for t in (0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2):
        x = px(t)
        painter.setPen(QPen(gray, 1))
        painter.drawLine(QPointF(x, top), QPointF(x, bottom))
        painter.setPen(dark)
        painter.drawText(QRectF(x - 30, bottom + 10, 60, 28), Qt.AlignmentFlag.AlignCenter, f"{t:.1f}")
    for w in (5, 10, 15, 20, 25, 30):
        y = py(w)
        painter.setPen(QPen(gray, 1))
        painter.drawLine(QPointF(left, y), QPointF(right, y))
        painter.setPen(dark)
        painter.drawText(QRectF(48, y - 14, 55, 28), Qt.AlignmentFlag.AlignRight, str(w))

    painter.setPen(QPen(dark, 2))
    painter.drawLine(QPointF(left, top), QPointF(left, bottom))
    painter.drawLine(QPointF(left, bottom), QPointF(right, bottom))
    painter.setFont(QFont("Arial", 20, QFont.Weight.Bold))
    painter.drawText(QRectF(left, 12, right - left, 42), Qt.AlignmentFlag.AlignCenter,
                     "Respuesta teórica a un escalón de frenado")
    painter.setFont(QFont("Arial", 16))
    painter.drawText(QRectF(left, bottom + 47, right - left, 35), Qt.AlignmentFlag.AlignCenter,
                     "Tiempo (s)")
    painter.save()
    painter.translate(15, (top + bottom) / 2)
    painter.rotate(-90)
    painter.drawText(QRectF(-150, -16, 300, 32), Qt.AlignmentFlag.AlignCenter,
                     "Velocidad angular (rad/s)")
    painter.restore()

    painter.setPen(QPen(blue, 4))
    points = [QPointF(px(i * 1.2 / 300), py(25 - 15 * (1 - exp(-5 * i * 1.2 / 300))))
              for i in range(301)]
    for a, b in zip(points, points[1:]):
        painter.drawLine(a, b)
    painter.setPen(QPen(QColor("#b45309"), 2, Qt.PenStyle.DashLine))
    painter.drawLine(QPointF(left, py(10)), QPointF(right, py(10)))
    painter.setPen(dark)
    painter.drawText(QRectF(790, 132, 320, 35), Qt.AlignmentFlag.AlignRight,
                     "Valor final: 10 rad/s")
    painter.drawText(QRectF(790, 167, 320, 35), Qt.AlignmentFlag.AlignRight,
                     "Constante de tiempo: 0.20 s")
    painter.setFont(QFont("Arial", 13))
    painter.drawText(QRectF(left, 635, right - left, 25), Qt.AlignmentFlag.AlignCenter,
                     "J = 0.002 kg·m², b = 0.010 N·m·s/rad, Δτf = 0.15 N·m; parámetros hipotéticos")
    painter.end()
    destination = Path(__file__).parent / "imgs" / "simulacion_escalon_frenado.png"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(destination)):
        raise RuntimeError(f"No se pudo guardar {destination}")
    print(destination)
    del app


if __name__ == "__main__":
    main()
