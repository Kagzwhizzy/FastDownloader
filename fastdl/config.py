"""App-wide settings and constants."""
import json
import os
import sys

APP_NAME = "FastDownloader"
VERSION = "1.2.0"
GITHUB_REPO = "Kagzwhizzy/FastDownloader"

# Local port the Chrome extension talks to (127.0.0.1 only, never the internet).
PORT = 47321

# PayPal donations go to this PayPal account email.
PAYPAL_EMAIL = "saidimwangi054@gmail.com"
PAYPAL_URL = ("https://www.paypal.com/donate/?business=" + PAYPAL_EMAIL.replace("@", "%40")
              + "&no_recurring=0&item_name=Support+FastDownloader&currency_code=USD")

# Crypto donations: USDT to the developer's Binance deposit address.
# The same address works on both networks listed below (only USDT, only these networks).
USDT_ADDRESS = "0x536dd935af551de218b7461d74ab12b42489363f"
USDT_NETWORKS = [
    ("BNB Smart Chain (BEP20)", "Recommended - very low fees"),
    ("Ethereum (ERC20)", "Works too, but network fees are higher"),
]

DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), APP_NAME)
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
TASKS_FILE = os.path.join(DATA_DIR, "downloads.json")

os.makedirs(DATA_DIR, exist_ok=True)


def resource_path(*parts):
    """Path to a bundled file, works both from source and from the built .exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, *parts)


DEFAULTS = {
    "download_dir": os.path.join(os.path.expanduser("~"), "Downloads", APP_NAME),
    "connections": 8,
    "start_with_windows": False,
    "max_parallel": 3,          # downloads running at the same time (rest wait in the queue)
    "speed_limit": 0,           # bytes/second for all downloads together, 0 = unlimited
    "auto_folders": True,       # Videos / Music / Programs / Compressed / Documents / Pictures / Other
    "theme": "system",          # system / light / dark
    "check_updates": True,
    "skip_version": "",
    "sched_start_on": False, "sched_start": "02:00",
    "sched_stop_on": False, "sched_stop": "07:00",
    "after_done": "nothing",    # nothing / sleep / shutdown / quit
}


def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            s.update(json.load(f))
    except Exception:
        pass
    return s


def save_settings(s):
    tmp = SETTINGS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    os.replace(tmp, SETTINGS_FILE)
