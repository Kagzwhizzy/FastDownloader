"""App-wide settings and constants."""
import json
import os
import sys

APP_NAME = "FastDownloader"
VERSION = "1.0.0"

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
