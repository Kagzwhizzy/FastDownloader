"""FastDownloader - IDM-style download manager (files + videos)."""
import json
import os
import subprocess
import sys
import threading
import webbrowser

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QDialog, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QProgressBar,
    QPushButton, QSizePolicy, QSpinBox, QStyle, QSystemTrayIcon, QTableWidget, QTableWidgetItem, QToolBar,
    QVBoxLayout, QWidget,
)

from fastdl import bridge, config, engine, video
from fastdl.engine import human_size, human_time

STATUS_TEXT = {
    "queued": "Queued", "downloading": "Downloading", "processing": "Finishingâ€¦",
    "paused": "Paused", "done": "Complete", "error": "Error",
}

STYLE = """
QMainWindow, QDialog { background: #f6f7fb; }
QToolBar { background: #ffffff; border-bottom: 1px solid #dde1ea; spacing: 6px; padding: 6px; }
QToolButton { padding: 6px 10px; border-radius: 6px; font-size: 13px; }
QToolButton:hover { background: #e8eefc; }
QTableWidget { background: #ffffff; border: none; gridline-color: #eef0f5; font-size: 13px;
               selection-background-color: #dce7ff; selection-color: #111; }
QHeaderView::section { background: #f0f2f7; border: none; border-bottom: 1px solid #dde1ea;
                       padding: 6px; font-weight: 600; color: #444; }
QProgressBar { border: 1px solid #cfd6e4; border-radius: 4px; background: #eef1f7; text-align: center;
               height: 16px; font-size: 11px; }
QProgressBar::chunk { border-radius: 3px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #2563eb); }
QPushButton { padding: 7px 14px; border-radius: 8px; border: 1px solid #d5d9e6; background: #fff; }
QPushButton:hover { background: #f1efff; border-color: #b9b0f5; }
QPushButton#primary { color: white; border: none; font-weight: 600;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7c3aed, stop:1 #2563eb); }
QPushButton#primary:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6d28d9, stop:1 #1d4ed8); }
QPushButton#quality { text-align: left; padding: 9px 12px; font-size: 13px; border-radius: 10px; }
QPushButton#quality:hover { color: white; border: none;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7c3aed, stop:1 #2563eb); }
QPushButton#donate { background: #ffc439; border: none; font-weight: 700; color: #142c8e; border-radius: 16px; padding: 7px 16px; }
QPushButton#donate:hover { background: #f2b52a; }
QLineEdit, QSpinBox { padding: 6px; border: 1px solid #c9d1e1; border-radius: 6px; background: #fff; }
"""


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
    btn = QPushButton("Browseâ€¦")

    def pick():
        d = QFileDialog.getExistingDirectory(parent, "Save to", edit.text())
        if d:
            edit.setText(d)
    btn.clicked.connect(pick)
    row.addWidget(edit, 1)
    row.addWidget(btn)
    return row, edit


# ---------------------------------------------------------------------------
# Popups
# ---------------------------------------------------------------------------
class QualityDialog(QDialog):
    """IDM-style popup: shows the qualities a video really has and lets you pick one."""

    def __init__(self, main, page_url, referer=None, direct=None, title=""):
        super().__init__(None)
        self.main = main
        self.page_url = page_url
        self.referer = referer
        self.direct = direct
        self.setWindowTitle("Download video - FastDownloader")
        self.setWindowIcon(main.windowIcon())
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMinimumWidth(460)

        lay = QVBoxLayout(self)
        head = QLabel("â¬‡  Download this video")
        head.setStyleSheet("font-size:17px; font-weight:700; color:#5b3fe0;")
        lay.addWidget(head)
        self.title_lbl = QLabel(title or page_url)
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setStyleSheet("font-size:13px; font-weight:600; color:#222;")
        lay.addWidget(self.title_lbl)
        self.status = QLabel("Finding available qualitiesâ€¦")
        self.status.setStyleSheet("color:#666;")
        lay.addWidget(self.status)

        self.box = QGridLayout()
        self.box.setSpacing(6)
        lay.addLayout(self.box)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#dde1ea;")
        lay.addWidget(line)
        row, self.folder = folder_row(self, main.settings["download_dir"])
        lay.addWidget(QLabel("Save to:"))
        lay.addLayout(row)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.close)
        b = QHBoxLayout()
        b.addStretch(1)
        b.addWidget(cancel)
        lay.addLayout(b)

        self.worker = Worker()
        self.worker.finished.connect(self._got_info)
        self.worker.run(video.probe, page_url, referer)
        QTimer.singleShot(0, self._fit)

    def _got_info(self, info, err):
        if err is not None:
            msg = str(err).replace("ERROR: ", "")
            self.status.setText("Could not read this video:\n" + msg[:300])
            self.status.setWordWrap(True)
            self.status.setStyleSheet("color:#b3261e;")
            if self.direct:
                btn = QPushButton("Download the video file directly")
                btn.setObjectName("quality")
                btn.clicked.connect(self._direct)
                self.box.addWidget(btn, 0, 0, 1, 2)
            self._fit()
            return
        self.title_lbl.setText(info["title"])
        self.status.setText("Choose a quality:")
        self.info = info
        vids = [o for o in info["options"] if not o["audio_only"]]
        auds = [o for o in info["options"] if o["audio_only"]]
        for i, opt in enumerate(vids + auds):
            size = f"   ~{human_size(opt['size'])}" if opt.get("size") else ""
            icon = "ðŸŽµ " if opt["audio_only"] else "ðŸŽ¬ "
            btn = QPushButton(f"{icon}{opt['label']}{size}")
            btn.setObjectName("quality")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, o=opt: self._choose(o))
            if opt["audio_only"]:
                self.box.addWidget(btn, (len(vids) + 1) // 2, 0, 1, 2)
            else:
                self.box.addWidget(btn, i // 2, i % 2)
        self._fit()

    def _fit(self):
        """Resize to content and keep the whole popup on screen."""
        self.adjustSize()
        scr = (self.screen() or QApplication.primaryScreen()).availableGeometry()
        g = self.frameGeometry()
        g.moveCenter(scr.center())
        self.move(max(scr.left(), g.left()), max(scr.top(), g.top()))

    def _choose(self, opt):
        folder = self.folder.text().strip() or self.main.settings["download_dir"]
        headers = {"Referer": self.referer} if self.referer else {}
        task = engine.VideoTask(
            url=self.info["url"], folder=folder, format_spec=opt["format_spec"], label=opt["tag"],
            audio_only=opt["audio_only"], title=self.info["title"], expected_total=opt.get("size"),
            headers=headers,
        )
        self.main.add_task(task)
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
        self.setMinimumWidth(520)

        lay = QVBoxLayout(self)
        head = QLabel("â¬‡  Download file")
        head.setStyleSheet("font-size:17px; font-weight:700; color:#5b3fe0;")
        lay.addWidget(head)
        form = QFormLayout()
        url_lbl = QLabel(url if len(url) < 90 else url[:87] + "â€¦")
        url_lbl.setToolTip(url)
        url_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow("Address:", url_lbl)
        self.name = QLineEdit(filename or "")
        self.name.setPlaceholderText("checkingâ€¦")
        form.addRow("File name:", self.name)
        self.size = QLabel("checkingâ€¦")
        form.addRow("Size:", self.size)
        row, self.folder = folder_row(self, main.settings["download_dir"])
        form.addRow("Save to:", row)
        lay.addLayout(form)

        b = QHBoxLayout()
        b.addStretch(1)
        self.start_btn = QPushButton("Start download")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(self._start)
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
            txt += "   Â·   resume supported, fast multi-part download"
        else:
            txt += "   Â·   server does not allow resume (single connection)"
        self.size.setText(txt)

    def _start(self):
        folder = self.folder.text().strip() or self.main.settings["download_dir"]
        os.makedirs(folder, exist_ok=True)
        name = engine.safe_name(self.name.text().strip() or "download")
        name = os.path.basename(engine.unique_path(folder, name))
        task = engine.HttpTask(url=self.url, folder=folder, filename=name, headers=self.headers,
                               connections=self.main.settings["connections"])
        if self.info:
            task.apply_probe(self.info)
            task.filename = name
        self.main.add_task(task)
        self.close()


class AddUrlDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.setWindowTitle("Add download")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Paste a link (file, YouTube or other video page):"))
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
    from PySide6.QtGui import QColor, QPainter, QPixmap
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
        head = QLabel("ðŸŽ‰  Enjoying FastDownloader?" if thanks else "â¤  Support FastDownloader")
        head.setStyleSheet("font-size:17px; font-weight:700; color:#5b3fe0;")
        lay.addWidget(head)
        msg = QLabel(("You've finished several downloads with FastDownloader. " if thanks else "")
                     + "FastDownloader is free. If it saves you time, a small contribution "
                     "helps keep it updated. Thank you!")
        msg.setWordWrap(True)
        lay.addWidget(msg)

        pp = QPushButton("Donate with PayPal")
        pp.setObjectName("donate")
        pp.setCursor(Qt.PointingHandCursor)
        pp.clicked.connect(lambda: webbrowser.open(config.PAYPAL_URL))
        lay.addWidget(pp)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#dde1ea;")
        lay.addWidget(line)

        lay.addWidget(QLabel("<b>Or send USDT (crypto)</b>"))
        row = QHBoxLayout()
        qr = QLabel()
        qr.setPixmap(qr_pixmap(config.USDT_ADDRESS, 170))
        row.addWidget(qr)
        info = QVBoxLayout()
        info.addWidget(QLabel("Coin: <b>USDT</b>"))
        nets = "".join(f"â€¢ <b>{n}</b><br><span style='color:#666'>{d}</span><br>"
                       for n, d in config.USDT_NETWORKS)
        nl = QLabel("Network (use one of these):<br>" + nets)
        nl.setTextFormat(Qt.RichText)
        info.addWidget(nl)
        warn = QLabel("Send only USDT, only on the networks above.\nOther coins or networks will be lost.")
        warn.setStyleSheet("color:#b3261e; font-size:12px;")
        info.addWidget(warn)
        info.addStretch(1)
        row.addLayout(info, 1)
        lay.addLayout(row)

        lay.addWidget(QLabel("Address:"))
        arow = QHBoxLayout()
        addr = QLineEdit(config.USDT_ADDRESS)
        addr.setReadOnly(True)
        addr.setStyleSheet("font-family: Consolas; font-size: 12px;")
        copy = QPushButton("Copy")
        copy.setObjectName("primary")

        def do_copy():
            QApplication.clipboard().setText(config.USDT_ADDRESS)
            copy.setText("Copied âœ“")
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
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        lay = QFormLayout(self)
        row, self.folder = folder_row(self, main.settings["download_dir"])
        lay.addRow("Download folder:", row)
        self.conn = QSpinBox()
        self.conn.setRange(1, 32)
        self.conn.setValue(main.settings["connections"])
        lay.addRow("Connections per file:", self.conn)
        self.autostart = QCheckBox("Start FastDownloader when Windows starts (needed for the browser button)")
        self.autostart.setChecked(main.settings.get("start_with_windows", False))
        lay.addRow(self.autostart)
        b = QHBoxLayout()
        b.addStretch(1)
        ok = QPushButton("Save")
        ok.setObjectName("primary")
        ok.clicked.connect(self.accept)
        b.addWidget(ok)
        lay.addRow(b)


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
        self.setWindowTitle(f"{config.APP_NAME} {config.VERSION}")
        icon_file = config.resource_path("assets", "app.ico")
        self.setWindowIcon(QIcon(icon_file) if os.path.exists(icon_file)
                           else self.style().standardIcon(QStyle.SP_ArrowDown))
        self.resize(980, 520)

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
        act("Resume", QStyle.SP_MediaPlay, lambda: [t.start() for t in self.selected()])
        act("Pause", QStyle.SP_MediaPause, lambda: [t.pause() for t in self.selected()])
        act("Delete", QStyle.SP_TrashIcon, self.delete_selected)
        tb.addSeparator()
        act("Resume all", QStyle.SP_MediaSeekForward, self.resume_all)
        act("Pause all", QStyle.SP_MediaStop, lambda: [t.pause() for t in self.tasks])
        tb.addSeparator()
        act("Open folder", QStyle.SP_DirOpenIcon, lambda: os.startfile(self._ensure_dir()))
        act("Settings", QStyle.SP_FileDialogDetailedView, self.open_settings)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        donate = QPushButton("â¤  Support (PayPal / USDT)")
        donate.setObjectName("donate")
        donate.setCursor(Qt.PointingHandCursor)
        donate.clicked.connect(lambda: self.open_support())
        tb.addWidget(donate)

        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for i, w in ((1, 90), (2, 170), (3, 100), (4, 90), (5, 110)):
            h.setSectionResizeMode(i, QHeaderView.Fixed)
            self.table.setColumnWidth(i, w)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.row_menu)
        self.table.cellDoubleClicked.connect(self.double_click)
        self.setCentralWidget(self.table)
        self.statusBar().showMessage("Ready")

        # tray icon so the app keeps running for the browser extension
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        menu = QMenu()
        menu.addAction("Show FastDownloader", self.show_window)
        menu.addAction("Add URL", self.add_url)
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
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(500)
        self.save_timer = QTimer(self)
        self.save_timer.timeout.connect(self.save_tasks)
        self.save_timer.start(5000)

    # ---- tasks --------------------------------------------------------
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
                            t.start()   # it was downloading when the app closed -> continue
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

    def add_task(self, task):
        self._append_row(task)
        task.start()
        self.save_tasks()
        self.statusBar().showMessage(f"Started: {task.filename or task.url}", 5000)
        # bring the list forward so the progress is visible (like IDM's progress window)
        self.show_window()
        self.table.selectRow(len(self.tasks) - 1)
        self.table.scrollToBottom()

    def selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return [self.tasks[r] for r in rows if r < len(self.tasks)]

    def resume_all(self):
        for t in self.tasks:
            if t.status in ("paused", "error", "queued"):
                t.start()

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
        any_active = False
        for r, t in enumerate(self.tasks):
            t.tick()
            active = t.active
            any_active |= active
            name = t.filename or t.url
            self.table.item(r, 0).setText(name)
            self.table.item(r, 0).setToolTip(f"{name}\n{t.url}")
            self.table.item(r, 1).setText(human_size(t.total))
            bar = self.table.cellWidget(r, 2)
            if t.total:
                bar.setRange(0, 1000)
                bar.setValue(int(1000 * min(1.0, t.done / t.total)))
                bar.setFormat(f"{100 * min(1.0, t.done / t.total):.1f}%")
            elif t.status == "done":
                bar.setRange(0, 1000)
                bar.setValue(1000)
                bar.setFormat("100%")
            else:
                bar.setRange(0, 1000)
                bar.setValue(0)
                bar.setFormat(human_size(t.done) or "")
            self.table.item(r, 3).setText(f"{human_size(t.speed)}/s" if t.speed > 1 and active else "")
            self.table.item(r, 4).setText(human_time(t.eta) if active else "")
            st = STATUS_TEXT.get(t.status, t.status)
            item = self.table.item(r, 5)
            item.setText(st)
            item.setToolTip(t.error or "")
            item.setForeground(Qt.red if t.status == "error" else (Qt.darkGreen if t.status == "done" else Qt.black))
            was = self._was_active.get(t.id)
            if was and not active:
                if t.status == "done":
                    self.tray.showMessage("Download complete", t.filename or "", QSystemTrayIcon.Information, 4000)
                    self._count_completed()
                elif t.status == "error":
                    self.tray.showMessage("Download failed", f"{t.filename}\n{t.error}", QSystemTrayIcon.Warning, 6000)
                self.save_tasks()
            self._was_active[t.id] = active
        total_speed = sum(t.speed for t in self.tasks if t.active)
        n = sum(1 for t in self.tasks if t.active)
        if n:
            self.statusBar().showMessage(f"{n} downloading  Â·  {human_size(total_speed) or '0 B'}/s")
        elif any_active is False and self.statusBar().currentMessage().endswith("/s"):
            self.statusBar().showMessage("Ready")

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
        m.addAction("Resume", lambda: [x.start() for x in tasks])
        m.addAction("Pause", lambda: [x.pause() for x in tasks])
        m.addAction("Copy link", lambda: QApplication.clipboard().setText(t.url))
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
            t.start()

    def add_url(self):
        self.show_window()
        d = AddUrlDialog(self)
        if d.exec() != QDialog.Accepted:
            return
        url = d.edit.text().strip()
        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(self, "Add download", "Please paste a link that starts with http:// or https://")
            return
        if video.is_video_site(url):
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
        self.settings["download_dir"] = d.folder.text().strip() or config.DEFAULTS["download_dir"]
        self.settings["connections"] = d.conn.value()
        self.settings["start_with_windows"] = d.autostart.isChecked()
        config.save_settings(self.settings)
        set_autostart(self.settings["start_with_windows"])

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
                                  "Right-click the tray icon â†’ Quit to close.", QSystemTrayIcon.Information, 4000)
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
    app.setStyleSheet(STYLE)
    app.setFont(QFont("Segoe UI", 10))

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
