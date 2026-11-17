"""Draws the app/extension icons + the USDT QR image used by the extension."""
import os
import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QGuiApplication, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPen)

app = QGuiApplication(sys.argv)
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
from fastdl import config  # noqa: E402


def draw(size):
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    s = float(size)
    g = QLinearGradient(0, 0, s, s)
    g.setColorAt(0, QColor("#7c3aed"))
    g.setColorAt(1, QColor("#2563eb"))
    p.setBrush(QBrush(g))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(0, 0, s, s), s * 0.26, s * 0.26)
    # soft highlight
    hl = QLinearGradient(0, 0, 0, s * 0.6)
    hl.setColorAt(0, QColor(255, 255, 255, 60))
    hl.setColorAt(1, QColor(255, 255, 255, 0))
    p.setBrush(QBrush(hl))
    p.drawRoundedRect(QRectF(0, 0, s, s * 0.6), s * 0.26, s * 0.26)
    # arrow (rounded strokes)
    pen = QPen(QColor("white"), max(1.6, s * 0.11), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(s * 0.5, s * 0.22), QPointF(s * 0.5, s * 0.60))
    path = QPainterPath()
    path.moveTo(s * 0.32, s * 0.45)
    path.lineTo(s * 0.5, s * 0.63)
    path.lineTo(s * 0.68, s * 0.45)
    p.drawPath(path)
    p.drawLine(QPointF(s * 0.28, s * 0.78), QPointF(s * 0.72, s * 0.78))
    p.end()
    return img


def qr_image(text, px=220):
    import qrcode
    qr = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(text)
    qr.make(fit=True)
    m = qr.get_matrix()
    n = len(m)
    cell = max(1, px // n)
    img = QImage(cell * n, cell * n, QImage.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#111111"))
    for y, row in enumerate(m):
        for x, on in enumerate(row):
            if on:
                p.drawRect(x * cell, y * cell, cell, cell)
    p.end()
    return img


os.makedirs(os.path.join(here, "assets"), exist_ok=True)
for n in (16, 32, 48, 128):
    draw(n).save(os.path.join(here, "extension", f"icon{n}.png"))
draw(256).save(os.path.join(here, "assets", "app.ico"))
draw(256).save(os.path.join(here, "assets", "app.png"))
qr_image(config.USDT_ADDRESS).save(os.path.join(here, "extension", "usdt_qr.png"))
print("icons done")
