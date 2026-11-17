"""Makes store / download-site screenshots (1280x800) + Chrome promo tile (440x280) in release/marketing."""
import os
import sys
import time

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QApplication

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
out = os.path.join(here, "release", "marketing")
os.makedirs(out, exist_ok=True)

app = QApplication(sys.argv)
import app as fd  # noqa: E402
from fastdl import engine  # noqa: E402

fd.apply_theme(app, os.environ.get("FDL_THEME", "light"))
app.setFont(QFont("Segoe UI", 10))


def wait(sec, cond=lambda: False):
    t0 = time.time()
    while time.time() - t0 < sec and not cond():
        app.processEvents()
        time.sleep(0.05)


def canvas(w, h):
    img = QImage(w, h, QImage.Format_ARGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, QColor("#7c3aed"))
    g.setColorAt(1, QColor("#2563eb"))
    p.fillRect(0, 0, w, h, g)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 22))
    p.drawEllipse(QRectF(w * 0.62, -h * 0.35, w * 0.6, w * 0.6))
    p.drawEllipse(QRectF(-w * 0.15, h * 0.7, w * 0.35, w * 0.35))
    return img, p


def title(p, text, sub, w, y=70):
    p.setPen(QColor("white"))
    f = QFont("Segoe UI", 34, QFont.Bold)
    p.setFont(f)
    p.drawText(QRectF(0, y, w, 60), Qt.AlignHCenter, text)
    p.setPen(QColor(255, 255, 255, 215))
    p.setFont(QFont("Segoe UI", 16))
    p.drawText(QRectF(0, y + 62, w, 34), Qt.AlignHCenter, sub)


def paste(p, pix, cx, top, max_w, max_h):
    pix = pix.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    x = cx - pix.width() / 2
    # shadow
    for i in range(14, 0, -2):
        p.setBrush(QColor(0, 0, 0, 7))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(x - i, top - i + 8, pix.width() + 2 * i, pix.height() + 2 * i), 18, 18)
    path = QPainterPath()
    path.addRoundedRect(QRectF(x, top, pix.width(), pix.height()), 12, 12)
    p.save()
    p.setClipPath(path)
    p.drawPixmap(int(x), int(top), pix)
    p.restore()


def shot(name, head, sub, pix, max_w=1040, max_h=560):
    img, p = canvas(1280, 800)
    title(p, head, sub, 1280, 48)
    paste(p, pix, 640, 200, max_w, max_h)
    p.end()
    img.save(os.path.join(out, name))
    print("saved", name)


# ---- 1. main window with a download list ---------------------------------
w = fd.MainWindow()
w.tray.hide()
w.save_timer.stop()
w.save_tasks = lambda: None          # never touch the real download list
w.timer.stop()
w.tasks.clear()
w.table.setRowCount(0)
demo = [
    ("Ubuntu-24.04-desktop-amd64.iso", 6_114_656_256, 0.62, 9.8e6, "downloading"),
    ("Big Buck Bunny [1080p].mp4", 288_387_264, 1.0, 0, "done"),
    ("MinGit-2.47.0-64-bit.zip", 47_218_826, 1.0, 0, "done"),
    ("python-3.12.7-amd64.exe", 26_538_304, 1.0, 0, "done"),
    ("Podcast episode 42.mp3", 61_400_000, 0.35, 0, "paused"),
]
for name, total, frac, speed, status in demo:
    t = engine.HttpTask(url="https://example.com/" + name, folder="C:\\Downloads", filename=name,
                        total=total, done=int(total * frac), status=status)
    w._append_row(t)
    t.speed = speed
    t.tick = lambda: None
type(t).active = property(lambda self: self.status == "downloading")
w.resize(1060, 470)
w.show()
w.refresh()
w.table.clearSelection()
w.table.setCurrentCell(-1, -1)
w.table.setFocusPolicy(Qt.NoFocus)
wait(0.5)
shot("1-download-list.png", "Up to 32× faster downloads", "Multi-part downloading · pause & resume anytime",
     w.grab())

# ---- 2. quality picker -----------------------------------------------------
d = fd.QualityDialog(w, "https://www.youtube.com/watch?v=aqz-KE-bpKQ", title="Big Buck Bunny")
d.show()
wait(40, lambda: hasattr(d, "info"))
wait(0.5)
shot("2-quality-picker.png", "Pick any quality", "4K · 2K · 1080p · 720p · 480p · or audio only (MP3)",
     d.grab(), max_h=540)
d.close()

# ---- 3. support window -----------------------------------------------------
s = fd.SupportDialog(w)
s.show()
wait(0.3)
shot("4-support.png", "Free – no ads, no account", "Like it? Support the project with PayPal or USDT",
     s.grab(), max_h=540)

# ---- 3. extension popup (rendered earlier by Edge) ---------------------------
pp = sys.argv[1] if len(sys.argv) > 1 else None
if pp and os.path.exists(pp):
    pop = QPixmap(pp)
    shot("3-browser-extension.png", "One click from your browser",
         "Works in Chrome, Brave & Edge · catches every download", pop, max_w=520, max_h=540)

# ---- promo tile 440x280 ----------------------------------------------------
img, p = canvas(440, 280)
icon = QPixmap(os.path.join(here, "assets", "app.png")).scaled(84, 84, Qt.KeepAspectRatio, Qt.SmoothTransformation)
p.drawPixmap(178, 40, icon)
p.setPen(QColor("white"))
p.setFont(QFont("Segoe UI", 24, QFont.Bold))
p.drawText(QRectF(0, 136, 440, 40), Qt.AlignHCenter, "FastDownloader")
p.setFont(QFont("Segoe UI", 12))
p.setPen(QColor(255, 255, 255, 220))
p.drawText(QRectF(0, 182, 440, 60), Qt.AlignHCenter, "Faster downloads · pause & resume\nvideo quality picker")
p.end()
img.save(os.path.join(out, "promo-tile-440x280.png"))
print("saved promo tile")
