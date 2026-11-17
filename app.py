"""FastDownloader - IDM-style download manager (files + videos)."""
import json
import os
import string
import subprocess
import sys
import threading
import time
import webbrowser

from PySide6.QtCore import QObject, Qt, QTime, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QProgressBar,
    QProgressDialog, QPushButton, QSpinBox, QStyle, QSystemTrayIcon, QTableWidget, QTableWidgetItem,
    QTextBrowser, QTimeEdit, QToolBar, QVBoxLayout, QWidget,
)

from fastdl import bridge, config, engine, updater, video
from fastdl.engine import human_size, human_time

STATUS_TEXT = {
    "queued": "Queued", "scheduled": "Scheduled", "downloading": "Downloading", "processing": "Finishing…",
    "paused": "Paused", "done": "Complete", "error": "Error",
}

SPEEDS = [("Unlimited", 0), ("100 KB/s", 100 * 1024), ("250 KB/s", 250 * 1024), ("500 KB/s", 500 * 1024),
          ("1 MB/s", 1 << 20), ("2 MB/s", 2 << 20), ("5 MB/s", 5 << 20), ("10 MB/s", 10 << 20)]

SUB_LANGS = [("en", "English"), ("es", "Spanish"), ("fr", "French"), ("de", "German"), ("pt", "Portuguese"),
             ("ar", "Arabic"), ("hi", "Hindi"), ("sw", "Swahili"), ("zh-Hans", "Chinese"), ("ru", "Russian")]

# ---------------------------------------------------------------------------
# Themes (light / dark)
# ---------------------------------------------------------------------------
PALETTES = {
    "light": dict(bg="#f6f7fb", card="#ffffff", text="#151826", muted="#6b7185", line="#dde1ea",
                  head="#f0f2f7", sel="#e6e0ff", input="#ffffff", inputline="#c9d1e1", hover="#f1efff",
                  accent="#5b3fe0", error="#b3261e", ok="#15803d", trough="#eef1f7", scroll="#c9cedb"),
    "dark": dict(bg="#12141c", card="#1a1d28", text="#e9ebf3", muted="#9aa1b5", line="#2a2e3d",
                 head="#202433", sel="#3b3370", input="#202433", inputline="#343a4f", hover="#2a2550",
                 accent="#a78bfa", error="#f87171", ok="#4ade80", trough="#262a38", scroll="#3a4054"),
}
P = dict(PALETTES["light"])

STYLE_TEMPLATE = string.Template("""
QWidget { color: $text; }
QMainWindow, QDialog { background: $bg; }
QToolBar { background: $card; border-bottom: 1px solid $line; spacing: 4px; padding: 6px; }
QToolButton { padding: 6px 9px; border-radius: 6px; font-size: 13px; color: $text; }
QToolButton:hover { background: $hover; }
QStatusBar { background: $card; border-top: 1px solid $line; padding: 4px 8px; }
QStatusBar QLabel { color: $muted; }
QTableWidget { background: $card; border: none; gridline-color: $line; font-size: 13px;
               selection-background-color: $sel; selection-color: $text; }
QHeaderView::section { background: $head; border: none; border-bottom: 1px solid $line;
                       padding: 6px; font-weight: 600; color: $muted; }
QProgressBar { border: 1px solid $line; border-radius: 4px; background: $trough; text-align: center;
               height: 16px; font-size: 11px; color: $text; }
QProgressBar::chunk { border-radius: 3px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #2563eb); }
QPushButton { padding: 7px 14px; border-radius: 8px; border: 1px solid $inputline; background: $card; color: $text; }
QPushButton:hover { background: $hover; border-color: #8b7cf0; }
QPushButton:disabled { color: $muted; }
QPushButton#primary { color: white; border: none; font-weight: 600;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7c3aed, stop:1 #2563eb); }
QPushButton#primary:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6d28d9, stop:1 #1d4ed8); }
QPushButton#quality { text-align: left; padding: 9px 12px; font-size: 13px; border-radius: 10px; }
QPushButton#quality:hover { color: white; border: none;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7c3aed, stop:1 #2563eb); }
QPushButton#donate { background: #ffc439; border: none; font-weight: 700; color: #142c8e; border-radius: 15px; padding: 6px 16px; }
QPushButton#donate:hover { background: #f2b52a; }
QPushButton#update { background: #16a34a; border: none; font-weight: 700; color: white; border-radius: 15px; padding: 6px 14px; }
QLineEdit, QSpinBox, QComboBox, QTimeEdit { padding: 5px 6px; border: 1px solid $inputline; border-radius: 6px;
    background: $input; color: $text; selection-background-color: #7c3aed; }
QComboBox QAbstractItemView { background: $card; color: $text; selection-background-color: $sel; border: 1px solid $line; }
QMenu { background: $card; color: $text; border: 1px solid $line; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 4px; }
QMenu::item:selected { background: $sel; }
QMenu::separator { height: 1px; background: $line; margin: 4px 6px; }
QTextBrowser { background: $card; border: 1px solid $line; border-radius: 8px; padding: 6px; }
QToolTip { background: $card; color: $text; border: 1px solid $line; padding: 4px; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: $scroll; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; }
QScrollBar::handle:horizontal { background: $scroll; border-radius: 5px; min-width: 30px; }
QLabel#heading { font-size: 17px; font-weight: 700; color: $accent; }
QLabel#title { font-size: 13px; font-weight: 600; }
QLabel#muted { color: $muted; }
QLabel#error { color: $error; }
QLabel#ok { color: $ok; }
QFrame#sep { background: $line; max-height: 1px; min-height: 1px; border: none; }
""")


def system_dark():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def apply_theme(app, setting):
    dark = system_dark() if setting == "system" else setting == "dark"
    P.clear()
    P.update(PALETTES["dark" if dark else "light"])
    app.setStyleSheet(STYLE_TEMPLATE.substitute(P))


def set_role(widget, name):
    """Change a label's style role (heading/muted/error/ok) and refresh its look."""
    widget.setObjectName(name)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def label(text="", role=None, wrap=False):
    w = QLabel(text)
    if role:
        w.setObjectName(role)
    w.setWordWrap(wrap)
    return w


def separator():
    f = QFrame()
    f.setObjectName("sep")
    return f


def open_path(path):
    if path and os.path.exists(path):
        os.startfile(path)  # noqa: S606 - opening the user's own downloaded file


def show_in_folder(path, folder):
    if path and os.path.exists(path):
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    elif folder and os.path.isdir(folder):
        os.startfile(folder)


class Worker(QObject):
    """Runs a function in a background thread and hands the result back to the UI thread."""
    finished = Signal(object, object)
    progress = Signal(object, object)

    def run(self, fn, *args):
        def target():
            try:
                self.finished.emit(fn(*args), None)
            except Exception as e:  # noqa: BLE001
                self.finished.emit(None, e)
        threading.Thread(target=target, daemon=True).start()


def folder_row(parent, folder):
    row = QHBoxLayout()
    edit = QLineEdit(folder)
    btn = QPushButton("Browse…")

    def pick():
        d = QFileDialog.getExistingDirectory(parent, "Save to", edit.text())
        if d:
            edit.setText(d)
    btn.clicked.connect(pick)
    row.addWidget(edit, 1)
    row.addWidget(btn)
    return row, edit


def target_folder(main, chosen, category):
    """IDM-style auto folders: if the user kept the default folder, sort into a category sub-folder."""
    base = main.settings["download_dir"]
    if main.settings.get("auto_folders", True) and os.path.normcase(os.path.abspath(chosen)) == \
            os.path.normcase(os.path.abspath(base)):
        return os.path.join(base, category)
    return chosen


# ---------------------------------------------------------------------------
# Popups
# ---------------------------------------------------------------------------
class QualityDialog(QDialog):
    """IDM-style popup: qualities the video really has, subtitles, whole-playlist download."""

    def __init__(self, main, page_url, referer=None, direct=None, title=""):
        super().__init__(None)
        self.main = main
        self.page_url = page_url
        self.referer = referer
        self.direct = direct
        self.info = None
        self.playlist = None
        self.is_list = video.is_playlist_url(page_url)
        self.is_single = (not self.is_list) or video.is_single_video_url(page_url)
        self._pending = 0
        self.setWindowTitle("Download video - FastDownloader")
        self.setWindowIcon(main.windowIcon())
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMinimumWidth(480)

        lay = QVBoxLayout(self)
        lay.addWidget(label("Download this video" if self.is_single else "Download playlist", "heading"))
        self.title_lbl = label(title or page_url, "title", wrap=True)
        lay.addWidget(self.title_lbl)
        self.status = label("Finding available qualities…" if self.is_single else "Reading the playlist…",
                            "muted", wrap=True)
        lay.addWidget(self.status)

        # playlist switch (shown when the link belongs to a playlist)
        self.pl_check = QCheckBox()
        self.pl_check.setVisible(False)
        self.pl_check.toggled.connect(self._render)
        lay.addWidget(self.pl_check)

        self.box = QGridLayout()
        self.box.setSpacing(6)
        lay.addLayout(self.box)

        # subtitles
        srow = QHBoxLayout()
        self.sub_check = QCheckBox("Subtitles:")
        self.sub_combo = QComboBox()
        self.sub_combo.setMinimumWidth(220)
        self.sub_combo.setEnabled(False)
        self.sub_check.toggled.connect(self.sub_combo.setEnabled)
        srow.addWidget(self.sub_check)
        srow.addWidget(self.sub_combo, 1)
        self.sub_wrap = QWidget()
        self.sub_wrap.setLayout(srow)
        srow.setContentsMargins(0, 0, 0, 0)
        self.sub_wrap.setVisible(False)
        lay.addWidget(self.sub_wrap)

        lay.addWidget(separator())
        row, self.folder = folder_row(self, main.settings["download_dir"])
        lay.addWidget(label("Save to:"))
        lay.addLayout(row)
        b = QHBoxLayout()
        self.later = QCheckBox("Download later (Scheduler)")
        b.addWidget(self.later)
        b.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.close)
        b.addWidget(cancel)
        lay.addLayout(b)

        if self.is_single:
            self._pending += 1
            self.w1 = Worker()
            self.w1.finished.connect(self._got_info)
            self.w1.run(video.probe, page_url, referer)
        if self.is_list:
            self._pending += 1
            self.w2 = Worker()
            self.w2.finished.connect(self._got_playlist)
            self.w2.run(video.probe_playlist, page_url)
        QTimer.singleShot(0, self._fit)

    # ---- results ---------------------------------------------------------
    def _got_info(self, info, err):
        try:
            self._pending -= 1
            if err is None:
                self.info = info
                self.title_lbl.setText(info["title"])
            else:
                self.err = err
            self._render()
        except RuntimeError:
            pass   # popup was closed

    def _got_playlist(self, pl, err):
        try:
            self._pending -= 1
            if err is None:
                self.playlist = pl
                self.pl_check.setText(f"Download the whole playlist:  {pl['title']}  ({len(pl['entries'])} videos)")
                self.pl_check.blockSignals(True)
                self.pl_check.setChecked(not self.is_single or self.info is None)
                self.pl_check.blockSignals(False)
                self.pl_check.setVisible(True)
            self._render()
        except RuntimeError:
            pass

    def _playlist_mode(self):
        return self.playlist is not None and (self.pl_check.isChecked() or self.info is None)

    def _render(self):
        while self.box.count():
            w = self.box.takeAt(0).widget()
            if w:
                w.deleteLater()
        if self._playlist_mode():
            self.title_lbl.setText(self.playlist["title"])
            set_role(self.status, "muted")
            self.status.setText(f"{len(self.playlist['entries'])} videos · choose a quality for all of them:")
            opts = [{"label": f"Up to {lbl}", "tag": f"{h}p", "format_spec": f"bv*[height<={h}]+ba/b[height<={h}]/b",
                     "size": None, "audio_only": False} for h, lbl in video.PLAYLIST_QUALITIES]
            opts.append({"label": "Audio only (MP3)", "tag": "mp3", "format_spec": "ba/b", "size": None,
                         "audio_only": True})
            self._buttons(opts)
            self._fill_subs([(c, n, False) for c, n in SUB_LANGS], note="when available")
        elif self.info is not None:
            self.title_lbl.setText(self.info["title"])
            set_role(self.status, "muted")
            self.status.setText("Choose a quality:")
            self._buttons(self.info["options"])
            self._fill_subs(self.info.get("subs") or [])
        elif self._pending == 0:
            err = getattr(self, "err", None)
            msg = str(err).replace("ERROR: ", "") if err else "No video found on this page"
            self.status.setText("Could not read this video:\n" + msg[:300])
            set_role(self.status, "error")
            if self.direct:
                btn = QPushButton("Download the video file directly")
                btn.setObjectName("quality")
                btn.clicked.connect(self._direct)
                self.box.addWidget(btn, 0, 0, 1, 2)
        self._fit()

    def _buttons(self, options):
        vids = [o for o in options if not o["audio_only"]]
        auds = [o for o in options if o["audio_only"]]
        for i, opt in enumerate(vids + auds):
            size = f"   ~{human_size(opt['size'])}" if opt.get("size") else ""
            icon = "🎵 " if opt["audio_only"] else "🎬 "
            btn = QPushButton(f"{icon}{opt['label']}{size}")
            btn.setObjectName("quality")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, o=opt: self._choose(o))
            if opt["audio_only"]:
                self.box.addWidget(btn, (len(vids) + 1) // 2, 0, 1, 2)
            else:
                self.box.addWidget(btn, i // 2, i % 2)

    def _fill_subs(self, subs, note=""):
        self.sub_combo.clear()
        for code, name, _auto in subs:
            self.sub_combo.addItem(f"{name}" + (f"  ({note})" if note else ""), code)
        en = self.sub_combo.findData("en")
        if en >= 0:
            self.sub_combo.setCurrentIndex(en)
        self.sub_wrap.setVisible(bool(subs))

    def _fit(self):
        """Resize to content and keep the whole popup on screen."""
        try:
            self.adjustSize()
            scr = (self.screen() or QApplication.primaryScreen()).availableGeometry()
            g = self.frameGeometry()
            g.moveCenter(scr.center())
            self.move(max(scr.left(), g.left()), max(scr.top(), g.top()))
        except RuntimeError:
            pass

    # ---- start -----------------------------------------------------------
    def _choose(self, opt):
        chosen = self.folder.text().strip() or self.main.settings["download_dir"]
        folder = target_folder(self.main, chosen, "Music" if opt["audio_only"] else "Videos")
        headers = {"Referer": self.referer} if self.referer else {}
        subs = [self.sub_combo.currentData()] if self.sub_check.isChecked() and self.sub_combo.count() else []
        if self._playlist_mode():
            folder = os.path.join(folder, engine.safe_name(self.playlist["title"]))
            tasks = [engine.VideoTask(url=e["url"], folder=folder, format_spec=opt["format_spec"],
                                      label=opt["tag"], audio_only=opt["audio_only"],
                                      title=e["title"] or f"Video {i + 1}", headers=headers,
                                      subs=[] if opt["audio_only"] else subs)
                     for i, e in enumerate(self.playlist["entries"])]
        else:
            tasks = [engine.VideoTask(
                url=self.info["url"], folder=folder, format_spec=opt["format_spec"], label=opt["tag"],
                audio_only=opt["audio_only"], title=self.info["title"], expected_total=opt.get("size"),
                headers=headers, subs=[] if opt["audio_only"] else subs)]
        self.main.add_tasks(tasks, later=self.later.isChecked())
        self.close()

    def _direct(self):
        headers = {"Referer": self.referer} if self.referer else {}
        self.close()
        self.main.open_file_dialog(self.direct, headers)


class FileDialog(QDialog):
    """IDM-style 'Download file info' popup for normal files."""

    def __init__(self, main, url, headers=None, filename=None, info=None):
        super().__init__(None)
        self.main = main
        self.url = url
        self.headers = headers or {}
        self.info = None
        self.setWindowTitle("Download file - FastDownloader")
        self.setWindowIcon(main.windowIcon())
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMinimumWidth(540)

        lay = QVBoxLayout(self)
        lay.addWidget(label("Download file", "heading"))
        form = QFormLayout()
        url_lbl = label(url if len(url) < 90 else url[:87] + "…", "muted")
        url_lbl.setToolTip(url)
        url_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow("Address:", url_lbl)
        self.name = QLineEdit(filename or "")
        self.name.setPlaceholderText("checking…")
        form.addRow("File name:", self.name)
        self.size = label("checking…", "muted")
        form.addRow("Size:", self.size)
        row, self.folder = folder_row(self, main.settings["download_dir"])
        form.addRow("Save to:", row)
        lay.addLayout(form)

        b = QHBoxLayout()
        later = QPushButton("Download later")
        later.setToolTip("Add to the Scheduler – it starts at your scheduled time")
        later.clicked.connect(lambda: self._start(later=True))
        b.addWidget(later)
        b.addStretch(1)
        self.start_btn = QPushButton("Start download")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(lambda: self._start(later=False))
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.close)
        b.addWidget(self.start_btn)
        b.addWidget(cancel)
        lay.addLayout(b)

        if info:   # the extension already checked the link
            self._got_info(info, None)
        else:
            self.worker = Worker()
            self.worker.finished.connect(self._got_info)
            self.worker.run(engine.probe, url, self.headers)

    def _got_info(self, info, err):
        try:
            if err is not None:
                self.size.setText("unknown (" + str(err)[:120] + ")")
                if not self.name.text():
                    self.name.setText(engine.safe_name(os.path.basename(self.url.split("?")[0])) or "download")
                return
            self.info = info
            if not self.name.text():
                self.name.setText(info["filename"])
            txt = human_size(info["total"]) or "unknown"
            if info["resumable"]:
                txt += "   ·   resume supported, fast multi-part download"
            else:
                txt += "   ·   server does not allow resume (single connection)"
            self.size.setText(txt)
        except RuntimeError:
            pass

    def _start(self, later=False):
        name = engine.safe_name(self.name.text().strip() or "download")
        chosen = self.folder.text().strip() or self.main.settings["download_dir"]
        folder = target_folder(self.main, chosen, engine.category_for(name))
        os.makedirs(folder, exist_ok=True)
        name = os.path.basename(engine.unique_path(folder, name))
        task = engine.HttpTask(url=self.url, folder=folder, filename=name, headers=self.headers,
                               connections=self.main.settings["connections"])
        if self.info:
            task.apply_probe(self.info)
            task.filename = name
        self.main.add_tasks([task], later=later)
        self.close()


class AddUrlDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.setWindowTitle("Add download")
        self.setMinimumWidth(540)
        lay = QVBoxLayout(self)
        lay.addWidget(label("Paste a link – a file, a video page, or a whole playlist / channel:"))
        self.edit = QLineEdit()
        clip = QApplication.clipboard().text().strip()
        if clip.startswith(("http://", "https://")) and " " not in clip:
            self.edit.setText(clip)
        lay.addWidget(self.edit)
        b = QHBoxLayout()
        b.addStretch(1)
        ok = QPushButton("OK")
        ok.setObjectName("primary")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        b.addWidget(ok)
        b.addWidget(cancel)
        lay.addLayout(b)


def qr_pixmap(text, size=200):
    """Draw a QR code for `text` (no image files needed)."""
    import qrcode
    from PySide6.QtGui import QPainter, QPixmap
    qr = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(text)
    qr.make(fit=True)
    m = qr.get_matrix()
    n = len(m)
    cell = max(1, size // n)
    pm = QPixmap(cell * n, cell * n)
    pm.fill(QColor("white"))
    p = QPainter(pm)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("black"))
    for y, row in enumerate(m):
        for x, on in enumerate(row):
            if on:
                p.drawRect(x * cell, y * cell, cell, cell)
    p.end()
    return pm


class SupportDialog(QDialog):
    """Donations: PayPal button + USDT (BEP20 / ERC20) address with copy button and QR code."""

    def __init__(self, main, thanks=False):
        super().__init__(main)
        self.setWindowTitle("Support FastDownloader")
        self.setMinimumWidth(500)
        lay = QVBoxLayout(self)
        lay.addWidget(label("🎉  Enjoying FastDownloader?" if thanks else "❤  Support FastDownloader", "heading"))
        lay.addWidget(label(("You've finished several downloads with FastDownloader. " if thanks else "")
                            + "FastDownloader is free. If it saves you time, a small contribution "
                            "helps keep it updated. Thank you!", wrap=True))

        pp = QPushButton("Donate with PayPal")
        pp.setObjectName("donate")
        pp.setCursor(Qt.PointingHandCursor)
        pp.clicked.connect(lambda: webbrowser.open(config.PAYPAL_URL))
        lay.addWidget(pp)
        lay.addWidget(separator())

        lay.addWidget(label("<b>Or send USDT (crypto)</b>"))
        row = QHBoxLayout()
        qr = QLabel()
        qr.setPixmap(qr_pixmap(config.USDT_ADDRESS, 170))
        row.addWidget(qr)
        info = QVBoxLayout()
        info.addWidget(label("Coin: <b>USDT</b>"))
        nets = "".join(f"• <b>{n}</b><br><span style='color:{P['muted']}'>{d}</span><br>"
                       for n, d in config.USDT_NETWORKS)
        nl = label("Network (use one of these):<br>" + nets)
        nl.setTextFormat(Qt.RichText)
        info.addWidget(nl)
        info.addWidget(label("Send only USDT, only on the networks above.\nOther coins or networks will be lost.",
                             "error"))
        info.addStretch(1)
        row.addLayout(info, 1)
        lay.addLayout(row)

        lay.addWidget(label("Address:"))
        arow = QHBoxLayout()
        addr = QLineEdit(config.USDT_ADDRESS)
        addr.setReadOnly(True)
        addr.setStyleSheet("font-family: Consolas; font-size: 12px;")
        copy = QPushButton("Copy")
        copy.setObjectName("primary")

        def do_copy():
            main._last_clip = config.USDT_ADDRESS
            QApplication.clipboard().setText(config.USDT_ADDRESS)
            copy.setText("Copied ✓")
            QTimer.singleShot(2000, lambda: copy.setText("Copy"))
        copy.clicked.connect(do_copy)
        arow.addWidget(addr, 1)
        arow.addWidget(copy)
        lay.addLayout(arow)

        self.dont_ask = QCheckBox("Don't show this again")
        self.dont_ask.setVisible(thanks)
        close = QPushButton("Maybe later" if thanks else "Close")
        close.clicked.connect(self.accept)
        b = QHBoxLayout()
        b.addWidget(self.dont_ask)
        b.addStretch(1)
        b.addWidget(close)
        lay.addLayout(b)


class SettingsDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        s = main.settings
        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)
        lay = QFormLayout(self)
        row, self.folder = folder_row(self, s["download_dir"])
        lay.addRow("Download folder:", row)
        self.auto_folders = QCheckBox("Sort into folders: Videos, Music, Programs, Compressed, Documents, Pictures")
        self.auto_folders.setChecked(s.get("auto_folders", True))
        lay.addRow("", self.auto_folders)
        self.conn = QSpinBox()
        self.conn.setRange(1, 32)
        self.conn.setValue(s["connections"])
        lay.addRow("Connections per file:", self.conn)
        self.par = QSpinBox()
        self.par.setRange(1, 20)
        self.par.setValue(s.get("max_parallel", 3))
        lay.addRow("Max downloads at once:", self.par)
        self.theme = QComboBox()
        for txt, val in (("Same as Windows", "system"), ("Light", "light"), ("Dark", "dark")):
            self.theme.addItem(txt, val)
        self.theme.setCurrentIndex(max(0, self.theme.findData(s.get("theme", "system"))))
        lay.addRow("Theme:", self.theme)
        self.autostart = QCheckBox("Start FastDownloader when Windows starts (needed for the browser button)")
        self.autostart.setChecked(s.get("start_with_windows", False))
        lay.addRow(self.autostart)
        self.clip = QCheckBox("When I copy a video link (YouTube, TikTok, Facebook …), show the quality picker")
        self.clip.setChecked(s.get("watch_clipboard", True))
        lay.addRow(self.clip)
        self.upd = QCheckBox("Check for updates automatically")
        self.upd.setChecked(s.get("check_updates", True))
        lay.addRow(self.upd)
        b = QHBoxLayout()
        b.addStretch(1)
        ok = QPushButton("Save")
        ok.setObjectName("primary")
        ok.clicked.connect(self.accept)
        b.addWidget(ok)
        lay.addRow(b)


class SchedulerDialog(QDialog):
    AFTER = (("Do nothing", "nothing"), ("Sleep", "sleep"), ("Shut down the PC", "shutdown"),
             ("Close FastDownloader", "quit"))

    def __init__(self, main):
        super().__init__(main)
        s = main.settings
        self.setWindowTitle("Scheduler")
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        lay.addWidget(label("⏰  Scheduler", "heading"))
        n = sum(1 for t in main.tasks if t.status == "scheduled")
        lay.addWidget(label(f"Downloads you add with “Download later” wait here ({n} waiting now). "
                            "Great for cheaper night-time internet bundles.", "muted", wrap=True))
        form = QFormLayout()
        self.start_on = QCheckBox("Start scheduled downloads at")
        self.start_on.setChecked(s.get("sched_start_on", False))
        self.start_t = QTimeEdit(QTime.fromString(s.get("sched_start", "02:00"), "HH:mm"))
        self.start_t.setDisplayFormat("HH:mm")
        form.addRow(self.start_on, self.start_t)
        self.stop_on = QCheckBox("Pause all downloads at")
        self.stop_on.setChecked(s.get("sched_stop_on", False))
        self.stop_t = QTimeEdit(QTime.fromString(s.get("sched_stop", "07:00"), "HH:mm"))
        self.stop_t.setDisplayFormat("HH:mm")
        form.addRow(self.stop_on, self.stop_t)
        self.after = QComboBox()
        for txt, val in self.AFTER:
            self.after.addItem(txt, val)
        self.after.setCurrentIndex(max(0, self.after.findData(s.get("after_done", "nothing"))))
        form.addRow("When all downloads finish:", self.after)
        lay.addLayout(form)
        lay.addWidget(label("“Sleep” and “Shut down” give you 60 seconds to cancel. They happen once, "
                            "then switch back to “Do nothing”.", "muted", wrap=True))
        b = QHBoxLayout()
        start_now = QPushButton(f"Start the {n} waiting now")
        start_now.setEnabled(n > 0)
        start_now.clicked.connect(lambda: (main.start_scheduled(), self.accept()))
        b.addWidget(start_now)
        b.addStretch(1)
        ok = QPushButton("Save")
        ok.setObjectName("primary")
        ok.clicked.connect(self.accept)
        b.addWidget(ok)
        lay.addLayout(b)


class UpdateDialog(QDialog):
    def __init__(self, main, upd):
        super().__init__(main)
        self.main = main
        self.upd = upd
        self.setWindowTitle("Update available")
        self.setMinimumSize(520, 420)
        lay = QVBoxLayout(self)
        lay.addWidget(label(f"✨  FastDownloader {upd['version']} is available", "heading"))
        lay.addWidget(label(f"You have version {config.VERSION}. What's new:", "muted"))
        notes = QTextBrowser()
        notes.setOpenExternalLinks(True)
        notes.setMarkdown(upd["notes"] or "Improvements and fixes.")
        lay.addWidget(notes, 1)
        b = QHBoxLayout()
        skip = QPushButton("Skip this version")
        skip.clicked.connect(self._skip)
        b.addWidget(skip)
        b.addStretch(1)
        later = QPushButton("Later")
        later.clicked.connect(self.reject)
        now = QPushButton("Update now")
        now.setObjectName("primary")
        now.clicked.connect(self._update)
        b.addWidget(later)
        b.addWidget(now)
        lay.addLayout(b)

    def _skip(self):
        self.main.settings["skip_version"] = self.upd["version"]
        config.save_settings(self.main.settings)
        self.reject()

    def _update(self):
        if not (updater.is_installed() and self.upd.get("setup_url")):
            webbrowser.open(self.upd["page"])     # portable version -> download page
            self.accept()
            return
        prog = QProgressDialog("Downloading the update…", "Cancel", 0, 100, self)
        prog.setWindowTitle("Updating FastDownloader")
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        prog.setValue(0)
        w = Worker()
        self._w = w
        w.progress.connect(lambda d, t: prog.setValue(int(100 * d / t)) if t else None)
        cancelled = {"v": False}
        prog.canceled.connect(lambda: cancelled.__setitem__("v", True))

        def done(path, err):
            prog.close()
            if err is not None:
                if not cancelled["v"]:
                    QMessageBox.warning(self, "Update", f"The update could not be downloaded:\n{err}")
                return
            # run the installer silently; it reopens FastDownloader when finished
            subprocess.Popen([path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/relaunch=1"])
            self.accept()
            self.main.quit_app()
        w.finished.connect(done)
        w.run(lambda: updater.download(self.upd["setup_url"], lambda d, t: w.progress.emit(d, t),
                                       lambda: cancelled["v"]))


class Countdown(QMessageBox):
    """'Shutting down in 60 s – Cancel' box."""

    def __init__(self, main, what, action, seconds=60):
        super().__init__(main)
        self.what, self.action, self.left = what, action, seconds
        self.setWindowTitle("FastDownloader")
        self.setIcon(QMessageBox.Information)
        self.setStandardButtons(QMessageBox.Cancel)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.t = QTimer(self)
        self.t.timeout.connect(self._tick)
        self._tick()
        self.t.start(1000)
        self.finished.connect(lambda _: self.t.stop())

    def _tick(self):
        if self.left <= 0:
            self.t.stop()
            self.done(0)
            self.action()
            return
        self.setText(f"All downloads are finished.\n{self.what} in {self.left} seconds.")
        self.left -= 1


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
COLS = ["File name", "Size", "Progress", "Speed", "Time left", "Status"]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = config.load_settings()
        self.tasks = []
        self.popups = []
        self._was_active = {}
        self._had_activity = False
        self._tick_n = 0
        self.setWindowTitle(f"{config.APP_NAME} {config.VERSION}")
        icon_file = config.resource_path("assets", "app.ico")
        self.setWindowIcon(QIcon(icon_file) if os.path.exists(icon_file)
                           else self.style().standardIcon(QStyle.SP_ArrowDown))
        self.resize(1100, 540)

        tb = QToolBar()
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(tb)
        st = self.style()

        def act(text, icon, fn):
            a = QAction(st.standardIcon(icon), text, self)
            a.triggered.connect(fn)
            tb.addAction(a)
            return a
        act("Add URL", QStyle.SP_FileDialogNewFolder, self.add_url)
        act("Resume", QStyle.SP_MediaPlay, lambda: [self.request_start(t) for t in self.selected()])
        act("Pause", QStyle.SP_MediaPause, lambda: [self.pause_task(t) for t in self.selected()])
        act("Delete", QStyle.SP_TrashIcon, self.delete_selected)
        tb.addSeparator()
        act("Resume all", QStyle.SP_MediaSeekForward, self.resume_all)
        act("Pause all", QStyle.SP_MediaStop, lambda: [self.pause_task(t) for t in self.tasks])
        tb.addSeparator()
        act("Scheduler", QStyle.SP_FileDialogInfoView, self.open_scheduler)
        act("Open folder", QStyle.SP_DirOpenIcon, lambda: os.startfile(self._ensure_dir()))
        act("Settings", QStyle.SP_FileDialogDetailedView, self.open_settings)

        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for i, w in ((1, 90), (2, 170), (3, 100), (4, 90), (5, 110)):
            h.setSectionResizeMode(i, QHeaderView.Fixed)
            self.table.setColumnWidth(i, w)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.row_menu)
        self.table.cellDoubleClicked.connect(self.double_click)
        self.setCentralWidget(self.table)

        # status bar: speed limit + update notice + support
        sb = self.statusBar()
        sb.addPermanentWidget(QLabel("Speed limit:"))
        self.speed = QComboBox()
        for txt, val in SPEEDS:
            self.speed.addItem(txt, val)
        cur = self.speed.findData(self.settings.get("speed_limit", 0))
        self.speed.setCurrentIndex(cur if cur >= 0 else 0)
        self.speed.currentIndexChanged.connect(self._speed_changed)
        engine.LIMITER.set_rate(self.speed.currentData())
        sb.addPermanentWidget(self.speed)
        self.update_btn = QPushButton("")
        self.update_btn.setObjectName("update")
        self.update_btn.setVisible(False)
        self.update_btn.clicked.connect(lambda: self._show_update(self._update_info))
        sb.addPermanentWidget(self.update_btn)
        donate = QPushButton("❤  Support (PayPal / USDT)")
        donate.setObjectName("donate")
        donate.setCursor(Qt.PointingHandCursor)
        donate.clicked.connect(lambda: self.open_support())
        sb.addPermanentWidget(donate)
        sb.showMessage("Ready")

        # tray icon so the app keeps running for the browser extension
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        menu = QMenu()
        menu.addAction("Show FastDownloader", self.show_window)
        menu.addAction("Add URL", self.add_url)
        menu.addAction("Scheduler", lambda: (self.show_window(), self.open_scheduler()))
        menu.addAction("Check for updates", lambda: self.check_updates(silent=False))
        menu.addAction("Support (PayPal / USDT)", lambda: (self.show_window(), self.open_support()))
        menu.addSeparator()
        menu.addAction("Quit", self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.show_window() if r == QSystemTrayIcon.Trigger else None)
        self.tray.setToolTip(config.APP_NAME)
        self.tray.show()
        self._quitting = False
        self._tray_hint_shown = False

        self.load_tasks()

        # copy a video link anywhere -> quality picker pops up (works without the browser extension)
        self._last_clip = QApplication.clipboard().text().strip()
        self._clip_worker = Worker()
        self._clip_worker.finished.connect(self._clip_checked)
        QApplication.clipboard().dataChanged.connect(self.on_clipboard)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(500)
        self.save_timer = QTimer(self)
        self.save_timer.timeout.connect(self.save_tasks)
        self.save_timer.start(5000)

        # updates: shortly after start, then every 12 hours
        self._update_info = None
        self._upd_worker = Worker()
        self._upd_worker.finished.connect(self._update_checked)
        self._upd_silent = True
        QTimer.singleShot(15000, lambda: self.check_updates(silent=True))
        self.upd_timer = QTimer(self)
        self.upd_timer.timeout.connect(lambda: self.check_updates(silent=True))
        self.upd_timer.start(12 * 3600 * 1000)

    # ---- tasks / queue ------------------------------------------------
    def _ensure_dir(self):
        os.makedirs(self.settings["download_dir"], exist_ok=True)
        return self.settings["download_dir"]

    def load_tasks(self):
        try:
            with open(config.TASKS_FILE, "r", encoding="utf-8") as f:
                for d in json.load(f):
                    t = engine.task_from_dict(d)
                    if t:
                        self._append_row(t)
                        if t.was_active and t.status != "done":
                            self.request_start(t)   # it was downloading when the app closed -> continue
        except FileNotFoundError:
            pass
        except Exception as e:  # noqa: BLE001
            self.statusBar().showMessage(f"Could not load download list: {e}")

    def save_tasks(self):
        data = [t.to_dict() for t in self.tasks]
        tmp = config.TASKS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, config.TASKS_FILE)

    def _append_row(self, task):
        self.tasks.append(task)
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c in range(len(COLS)):
            if c != 2:
                self.table.setItem(r, c, QTableWidgetItem(""))
        bar = QProgressBar()
        bar.setRange(0, 1000)
        self.table.setCellWidget(r, 2, bar)
        self.table.setRowHeight(r, 30)

    def _active_count(self):
        return sum(1 for t in self.tasks if t.active)

    def request_start(self, t):
        """Start now if there's room in the queue, otherwise wait as 'Queued'."""
        if t.active or t.status == "done":
            return
        if self._active_count() < self.settings.get("max_parallel", 3):
            t.start()
        else:
            t.status = "queued"

    def _pump_queue(self):
        free = self.settings.get("max_parallel", 3) - self._active_count()
        for t in self.tasks:
            if free <= 0:
                break
            if t.status == "queued" and not t.active:
                t.start()
                free -= 1

    def pause_task(self, t):
        if t.active:
            t.pause()
        elif t.status in ("queued", "scheduled"):
            t.status = "paused"

    def add_tasks(self, tasks, later=False):
        for t in tasks:
            self._append_row(t)
            if later:
                t.status = "scheduled"
            else:
                self.request_start(t)
        self.save_tasks()
        if later:
            s = self.settings
            when = f"starts at {s.get('sched_start', '02:00')}" if s.get("sched_start_on") else \
                "set a start time in Scheduler"
            self.statusBar().showMessage(f"Added {len(tasks)} to the Scheduler – {when}", 8000)
        else:
            self.statusBar().showMessage(
                f"Started: {tasks[0].filename or tasks[0].url}" if len(tasks) == 1 else
                f"Added {len(tasks)} downloads (max {self.settings.get('max_parallel', 3)} at once)", 6000)
        # bring the list forward so the progress is visible (like IDM's progress window)
        self.show_window()
        self.table.selectRow(len(self.tasks) - 1)
        self.table.scrollToBottom()

    def add_task(self, task):
        self.add_tasks([task])

    def start_scheduled(self):
        n = 0
        for t in self.tasks:
            if t.status == "scheduled":
                t.status = "queued"
                n += 1
        if n:
            self.tray.showMessage("Scheduler", f"Starting {n} scheduled download(s)", QSystemTrayIcon.Information, 4000)
        self._pump_queue()

    def selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return [self.tasks[r] for r in rows if r < len(self.tasks)]

    def resume_all(self):
        for t in self.tasks:
            if t.status in ("paused", "error"):
                self.request_start(t)

    def delete_selected(self, with_file=False):
        tasks = self.selected()
        if not tasks:
            return
        if with_file:
            q = QMessageBox.question(self, "Delete", f"Remove {len(tasks)} download(s) AND delete the file(s) from disk?")
            if q != QMessageBox.Yes:
                return
        for t in tasks:
            t.pause()
        for t in tasks:
            if t._thread:
                t._thread.join(timeout=3)
            if with_file:   # "Remove from list" keeps everything on disk
                t.delete_files(include_final=True)
            i = self.tasks.index(t)
            self.tasks.pop(i)
            self.table.removeRow(i)
        self.save_tasks()

    def refresh(self):
        self._pump_queue()
        self._tick_n += 1
        if self._tick_n % 10 == 0:
            self._check_schedule()
        text_brush = QBrush(QColor(P["text"]))
        for r, t in enumerate(self.tasks):
            t.tick()
            active = t.active
            if active:
                self._had_activity = True
            name = t.filename or t.url
            self.table.item(r, 0).setText(name)
            tip = f"{name}\n{t.url}\nFolder: {t.folder}"
            if getattr(t, "sub_note", ""):
                tip += f"\n{t.sub_note}"
            self.table.item(r, 0).setToolTip(tip)
            self.table.item(r, 1).setText(human_size(t.total))
            bar = self.table.cellWidget(r, 2)
            if t.total:
                bar.setValue(int(1000 * min(1.0, t.done / t.total)))
                bar.setFormat(f"{100 * min(1.0, t.done / t.total):.1f}%")
            elif t.status == "done":
                bar.setValue(1000)
                bar.setFormat("100%")
            else:
                bar.setValue(0)
                bar.setFormat(human_size(t.done) or "")
            self.table.item(r, 3).setText(f"{human_size(t.speed)}/s" if t.speed > 1 and active else "")
            self.table.item(r, 4).setText(human_time(t.eta) if active else "")
            item = self.table.item(r, 5)
            item.setText(STATUS_TEXT.get(t.status, t.status))
            item.setToolTip(t.error or "")
            if t.status == "error":
                item.setForeground(QBrush(QColor(P["error"])))
            elif t.status == "done":
                item.setForeground(QBrush(QColor(P["ok"])))
            elif t.status in ("queued", "scheduled", "paused"):
                item.setForeground(QBrush(QColor(P["muted"])))
            else:
                item.setForeground(text_brush)
            was = self._was_active.get(t.id)
            if was and not active:
                if t.status == "done":
                    self.tray.showMessage("Download complete", t.filename or "", QSystemTrayIcon.Information, 4000)
                    self._count_completed()
                elif t.status == "error":
                    self.tray.showMessage("Download failed", f"{t.filename}\n{t.error}", QSystemTrayIcon.Warning, 6000)
                self.save_tasks()
            self._was_active[t.id] = active
        n = self._active_count()
        q = sum(1 for t in self.tasks if t.status == "queued")
        if n:
            total_speed = sum(t.speed for t in self.tasks if t.active)
            extra = f"  ·  {q} queued" if q else ""
            self.statusBar().showMessage(f"{n} downloading  ·  {human_size(total_speed) or '0 B'}/s{extra}")
        else:
            if self.statusBar().currentMessage().endswith(("/s", "queued")):
                self.statusBar().showMessage("Ready")
            if q == 0:
                self._maybe_after_done()

    # ---- scheduler / after-done -------------------------------------------
    def _check_schedule(self):
        s = self.settings
        now = QTime.currentTime().toString("HH:mm")
        today = time.strftime("%Y-%m-%d")
        if s.get("sched_start_on") and now == s.get("sched_start") and s.get("_fired_start") != today:
            s["_fired_start"] = today
            config.save_settings(s)
            self.start_scheduled()
        if s.get("sched_stop_on") and now == s.get("sched_stop") and s.get("_fired_stop") != today:
            s["_fired_stop"] = today
            config.save_settings(s)
            stopping = [t for t in self.tasks if t.active or t.status == "queued"]
            for t in stopping:
                self.pause_task(t)
            # they continue at the next scheduled start time
            QTimer.singleShot(4000, lambda: [setattr(t, "status", "scheduled") for t in stopping
                                             if not t.active and t.status == "paused"])
            if stopping:
                self.tray.showMessage("Scheduler", f"Paused {len(stopping)} download(s) until the next start time",
                                      QSystemTrayIcon.Information, 4000)

    def _maybe_after_done(self):
        action = self.settings.get("after_done", "nothing")
        if action == "nothing" or not self._had_activity:
            return
        self._had_activity = False
        self.settings["after_done"] = "nothing"      # one-shot, like IDM
        config.save_settings(self.settings)
        self.save_tasks()
        if action == "quit":
            QTimer.singleShot(1500, self.quit_app)
            return
        what = {"sleep": "The PC will go to sleep", "shutdown": "The PC will shut down"}[action]

        def do_it():
            if action == "shutdown":
                subprocess.Popen(["shutdown", "/s", "/t", "0"])
            else:
                subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
        self.show_window()
        box = Countdown(self, what, do_it)
        box.show()
        self._countdown = box

    # ---- updates -------------------------------------------------------
    def check_updates(self, silent=True):
        if silent and not self.settings.get("check_updates", True):
            return
        self._upd_silent = silent
        self._upd_worker.run(updater.check)

    def _update_checked(self, upd, err):
        if err is not None:
            if not self._upd_silent:
                QMessageBox.warning(self, "Updates", f"Could not check for updates:\n{err}")
            return
        if upd is None:
            if not self._upd_silent:
                QMessageBox.information(self, "Updates", f"You have the latest version ({config.VERSION}).")
            return
        self._update_info = upd
        self.update_btn.setText(f"⬆  Update to {upd['version']}")
        self.update_btn.setVisible(True)
        if self._upd_silent and upd["version"] == self.settings.get("skip_version"):
            return
        if self._upd_silent:
            self.tray.showMessage("Update available", f"FastDownloader {upd['version']} is ready – click "
                                  "“Update” at the bottom of the window.", QSystemTrayIcon.Information, 6000)
        else:
            self._show_update(upd)

    def _show_update(self, upd):
        if upd:
            self.show_window()
            UpdateDialog(self, upd).exec()

    # ---- misc ----------------------------------------------------------
    def _speed_changed(self):
        val = self.speed.currentData()
        engine.LIMITER.set_rate(val)
        self.settings["speed_limit"] = val
        config.save_settings(self.settings)

    def on_clipboard(self):
        if not self.settings.get("watch_clipboard", True):
            return
        text = QApplication.clipboard().text().strip()
        if not text or text == self._last_clip:
            return
        self._last_clip = text
        if not text.startswith(("http://", "https://")) or any(c.isspace() for c in text) or len(text) > 2000:
            return
        if any(getattr(p, "page_url", None) == text for p in self.popups):
            return
        self._clip_worker.run(lambda u: (u, video.is_video_site(u)), text)

    def _clip_checked(self, result, err):
        if err is not None or not result:
            return
        url, is_video = result
        if is_video and url == self._last_clip:
            self.open_video_dialog(url)

    def _count_completed(self):
        """Polite thank-you prompt: after the 3rd finished download, then every 20th (can be turned off)."""
        n = self.settings.get("completed_count", 0) + 1
        self.settings["completed_count"] = n
        config.save_settings(self.settings)
        if self.settings.get("support_prompt", True) and (n == 3 or (n > 3 and (n - 3) % 20 == 0)):
            QTimer.singleShot(1500, lambda: self.open_support(thanks=True))

    def open_support(self, thanks=False):
        d = SupportDialog(self, thanks=thanks)
        d.exec()
        if thanks and d.dont_ask.isChecked():
            self.settings["support_prompt"] = False
            config.save_settings(self.settings)

    # ---- menus / actions ----------------------------------------------
    def row_menu(self, pos):
        tasks = self.selected()
        if not tasks:
            return
        t = tasks[0]
        m = QMenu(self)
        if t.status == "done":
            m.addAction("Open file", lambda: open_path(t.path))
        m.addAction("Show in folder", lambda: show_in_folder(t.path, t.folder))
        m.addSeparator()
        m.addAction("Resume", lambda: [self.request_start(x) for x in tasks])
        m.addAction("Start now (skip the queue)", lambda: [x.start() for x in tasks if not x.active])
        m.addAction("Pause", lambda: [self.pause_task(x) for x in tasks])
        m.addAction("Download later (Scheduler)",
                    lambda: [setattr(x, "status", "scheduled") for x in tasks
                             if not x.active and x.status != "done"])
        m.addAction("Copy link", lambda: (setattr(self, "_last_clip", t.url), QApplication.clipboard().setText(t.url)))
        if t.status == "error" and t.error:
            m.addAction("Show error", lambda: QMessageBox.warning(self, "Error", t.error))
        m.addSeparator()
        m.addAction("Remove from list", lambda: self.delete_selected(False))
        m.addAction("Remove and delete file", lambda: self.delete_selected(True))
        m.exec(self.table.viewport().mapToGlobal(pos))

    def double_click(self, row, _col):
        t = self.tasks[row]
        if t.status == "done":
            open_path(t.path)
        elif not t.active:
            self.request_start(t)

    def add_url(self):
        self.show_window()
        d = AddUrlDialog(self)
        if d.exec() != QDialog.Accepted:
            return
        url = d.edit.text().strip()
        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(self, "Add download", "Please paste a link that starts with http:// or https://")
            return
        if video.is_playlist_url(url) or video.is_video_site(url):
            self.open_video_dialog(url)
        else:
            self.open_file_dialog(url)

    def _keep(self, dlg):
        self.popups.append(dlg)
        dlg.destroyed.connect(lambda *_: self.popups.remove(dlg) if dlg in self.popups else None)
        # ignore clicks for a moment so a click meant for the browser can't hit a button by accident
        dlg.setEnabled(False)
        QTimer.singleShot(700, lambda: dlg.setEnabled(True) if dlg in self.popups else None)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def open_video_dialog(self, page_url, referer=None, direct=None, title=""):
        self._keep(QualityDialog(self, page_url, referer, direct, title))

    def open_file_dialog(self, url, headers=None, filename=None):
        self._keep(FileDialog(self, url, headers, filename))

    # from the browser extension
    def on_browser_download(self, data):
        headers = bridge.headers_from(data)
        name = engine.safe_name(data["filename"]) if data.get("filename") else None
        self._keep(FileDialog(self, data["url"], headers, name, info=data.get("info")))

    def on_browser_video(self, data):
        page = data.get("pageUrl") or data.get("direct")
        self.open_video_dialog(page, data.get("referrer"), data.get("direct"), data.get("title", ""))

    def open_settings(self):
        d = SettingsDialog(self)
        if d.exec() != QDialog.Accepted:
            return
        s = self.settings
        s["download_dir"] = d.folder.text().strip() or config.DEFAULTS["download_dir"]
        s["auto_folders"] = d.auto_folders.isChecked()
        s["connections"] = d.conn.value()
        s["max_parallel"] = d.par.value()
        s["theme"] = d.theme.currentData()
        s["start_with_windows"] = d.autostart.isChecked()
        s["watch_clipboard"] = d.clip.isChecked()
        s["check_updates"] = d.upd.isChecked()
        config.save_settings(s)
        set_autostart(s["start_with_windows"])
        apply_theme(QApplication.instance(), s["theme"])

    def open_scheduler(self):
        d = SchedulerDialog(self)
        if d.exec() != QDialog.Accepted:
            return
        s = self.settings
        s["sched_start_on"] = d.start_on.isChecked()
        s["sched_start"] = d.start_t.time().toString("HH:mm")
        s["sched_stop_on"] = d.stop_on.isChecked()
        s["sched_stop"] = d.stop_t.time().toString("HH:mm")
        s["after_done"] = d.after.currentData()
        s.pop("_fired_start", None)
        s.pop("_fired_stop", None)
        config.save_settings(s)
        self.statusBar().showMessage("Scheduler saved", 4000)

    # ---- window / tray ------------------------------------------------
    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        # Windows doesn't let background apps steal focus; briefly go on top so the window is seen
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.show()
        QTimer.singleShot(300, self._drop_on_top)

    def _drop_on_top(self):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.show()

    def closeEvent(self, e):
        if self._quitting:
            e.accept()
            return
        e.ignore()
        self.hide()
        if not self._tray_hint_shown:
            self.tray.showMessage(config.APP_NAME, "Still running in the tray so the browser button keeps working. "
                                  "Right-click the tray icon → Quit to close.", QSystemTrayIcon.Information, 4000)
            self._tray_hint_shown = True

    def quit_app(self):
        self._quitting = True
        for t in self.tasks:
            t.pause()
        for t in self.tasks:
            if t._thread:
                t._thread.join(timeout=3)
        self.save_tasks()
        self.tray.hide()
        QApplication.quit()


def set_autostart(enabled):
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            if getattr(sys, "frozen", False):
                cmd = f'"{sys.executable}" --tray'
            else:
                pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
                cmd = f'"{pyw}" "{os.path.abspath(__file__)}" --tray'
            winreg.SetValueEx(k, config.APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, config.APP_NAME)
            except FileNotFoundError:
                pass


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Segoe UI", 10))
    apply_theme(app, config.load_settings().get("theme", "system"))

    br = bridge.Bridge()
    try:
        br.start()
    except OSError:
        # already running -> just bring the existing window forward
        bridge.ask_running_instance_to_show()
        return 0

    win = MainWindow()
    br.download_requested.connect(win.on_browser_download)
    br.video_requested.connect(win.on_browser_video)
    br.show_requested.connect(win.show_window)
    if "--tray" not in sys.argv:
        win.show()
    rc = app.exec()
    br.stop()
    return rc


if __name__ == "__main__":
    sys.exit(main())
