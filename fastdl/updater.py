"""Checks GitHub Releases for a newer FastDownloader and downloads the installer."""
import os
import re
import sys
import tempfile

import requests

from . import config

API = f"https://api.github.com/repos/{config.GITHUB_REPO}/releases/latest"


def _ver(v):
    nums = [int(x) for x in re.findall(r"\d+", v or "")[:3]]
    return tuple(nums + [0] * (3 - len(nums)))


def is_installed():
    """True when running from the installer version (it has an uninstaller next to the exe)."""
    if not getattr(sys, "frozen", False):
        return False
    return os.path.exists(os.path.join(os.path.dirname(sys.executable), "unins000.exe"))


def check():
    """Returns dict(version, notes, page, setup_url) if a newer version exists, else None."""
    r = requests.get(API, timeout=15, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": f"{config.APP_NAME}-updater"})
    r.raise_for_status()
    j = r.json()
    tag = j.get("tag_name", "")
    if _ver(tag) <= _ver(config.VERSION):
        return None
    setup = next((a["browser_download_url"] for a in j.get("assets", [])
                  if a["name"].lower().startswith("fastdownloader_setup") and a["name"].lower().endswith(".exe")), None)
    return {"version": tag.lstrip("vV"), "notes": j.get("body") or "", "page": j.get("html_url"),
            "setup_url": setup}


def download(url, progress=None, cancelled=lambda: False):
    """Downloads the installer to a temp file and returns its path."""
    path = os.path.join(tempfile.gettempdir(), os.path.basename(url.split("?")[0]))
    with requests.get(url, stream=True, timeout=30, headers={"User-Agent": f"{config.APP_NAME}-updater"}) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        with open(path + ".part", "wb") as f:
            for chunk in r.iter_content(256 * 1024):
                if cancelled():
                    raise RuntimeError("cancelled")
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    os.replace(path + ".part", path)
    return path
