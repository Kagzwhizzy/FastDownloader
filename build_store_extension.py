"""Builds release/FastDownloader-ChromeWebStore.zip - the Chrome Web Store edition of the extension.

Chrome Web Store rules don't allow extensions that download YouTube videos, so this edition
openly does nothing on YouTube (no button, no menu, popup button hidden). Everything else is
identical to the full edition. YouTube still works through the desktop app (copy the link).
"""
import json
import os
import shutil
import zipfile

here = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(here, "extension")
out_dir = os.path.join(here, "release", "store-extension")
zip_path = os.path.join(here, "release", "FastDownloader-ChromeWebStore.zip")

shutil.rmtree(out_dir, ignore_errors=True)
shutil.copytree(src, out_dir)

with open(os.path.join(out_dir, "edition.js"), "w", encoding="utf-8") as f:
    f.write('''// Chrome Web Store edition: no video downloads on these sites (store rules).
self.FDL_EDITION = "store";
self.FDL_BLOCKED_HOSTS = ["youtube.com", "youtu.be", "youtube-nocookie.com", "youtubekids.com"];

self.fdlBlocked = function (url) {
  try {
    const h = new URL(url).hostname.toLowerCase();
    return self.FDL_BLOCKED_HOSTS.some(b => h === b || h.endsWith("." + b));
  } catch (e) {
    return false;
  }
};
''')

mf_path = os.path.join(out_dir, "manifest.json")
with open(mf_path, encoding="utf-8") as f:
    mf = json.load(f)
mf["name"] = "FastDownloader – Download Manager"
mf["description"] = ("Speed up downloads with the free FastDownloader app for Windows: "
                     "multi-part downloads, pause & resume, and video quality picker.")
with open(mf_path, "w", encoding="utf-8") as f:
    json.dump(mf, f, indent=2, ensure_ascii=False)

if os.path.exists(zip_path):
    os.remove(zip_path)
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(out_dir):
        for name in files:
            full = os.path.join(root, name)
            z.write(full, os.path.relpath(full, out_dir))
print("built", zip_path, os.path.getsize(zip_path), "bytes")
