"""Video helpers: find which qualities a video has, ffmpeg + JS runtime setup for yt-dlp."""
import os
import shutil
import sys

from . import config

STANDARD = [4320, 2160, 1440, 1080, 720, 480, 360, 240, 144]
LABELS = {4320: "8K", 2160: "4K", 1440: "2K"}

_ffmpeg_dir = None


def ffmpeg_dir():
    """yt-dlp needs ffmpeg to join video+audio. We ship one inside imageio-ffmpeg and copy it as ffmpeg.exe."""
    global _ffmpeg_dir
    if _ffmpeg_dir:
        return _ffmpeg_dir
    bin_dir = os.path.join(config.DATA_DIR, "bin")
    target = os.path.join(bin_dir, "ffmpeg.exe")
    if not os.path.exists(target):
        try:
            import imageio_ffmpeg
            src = imageio_ffmpeg.get_ffmpeg_exe()
            os.makedirs(bin_dir, exist_ok=True)
            shutil.copy2(src, target)
        except Exception:
            found = shutil.which("ffmpeg")
            return os.path.dirname(found) if found else None
    _ffmpeg_dir = bin_dir
    return bin_dir


def _deno_path():
    """YouTube needs a JavaScript runtime for yt-dlp; we ship Deno (from the 'deno' pip package)."""
    cands = []
    if getattr(sys, "frozen", False):
        cands.append(config.resource_path("deno", "deno.exe"))
    try:
        import deno  # type: ignore
        cands.append(deno.find_deno_bin())
    except Exception:
        pass
    w = shutil.which("deno")
    if w:
        cands.append(w)
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


class _SilentLogger:
    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


def base_opts(referer=None):
    opts = {
        "logger": _SilentLogger(),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "noprogress": True,
        "windowsfilenames": True,
    }
    ff = ffmpeg_dir()
    if ff:
        opts["ffmpeg_location"] = ff
    deno = _deno_path()
    if deno:
        opts["js_runtimes"] = {"deno": {"path": deno}}
    if referer:
        opts["http_headers"] = {"Referer": referer}
    return opts


def is_video_site(url):
    """True if yt-dlp has a dedicated extractor for this link (YouTube, Vimeo, TikTok, ...)."""
    try:
        from yt_dlp.extractor import gen_extractor_classes
        for ie in gen_extractor_classes():
            if ie.ie_key() == "Generic":
                continue
            if ie.suitable(url) and ie.working():
                return True
    except Exception:
        pass
    return False


def _size(f):
    return f.get("filesize") or f.get("filesize_approx") or 0


def probe(url, referer=None):
    """Return {'title', 'options': [ {label, format_spec, size, audio_only} ... ]} for a video page."""
    from yt_dlp import YoutubeDL

    opts = base_opts(referer)
    opts["skip_download"] = True
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if info.get("_type") == "playlist":
        entries = [e for e in (info.get("entries") or []) if e]
        if not entries:
            raise ValueError("No video found on this page")
        info = entries[0]
    formats = info.get("formats") or [info]

    audio = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec") not in (None, "none")]
    best_audio = max((_size(f) for f in audio), default=0)

    buckets = {}   # standard height -> (real max height, best size)
    for f in formats:
        h = f.get("height")
        if not h or f.get("vcodec") == "none":
            continue
        std = next((s for s in STANDARD if h >= s * 0.9), None)
        if std is None:
            continue
        size = _size(f)
        if f.get("acodec") == "none":   # video only -> audio will be added
            size = size + best_audio if size else 0
        real, best = buckets.get(std, (0, 0))
        buckets[std] = (max(real, h), max(best, size))

    options = []
    for std in sorted(buckets, reverse=True):
        real, size = buckets[std]
        name = f"{std}p"
        label = f"{LABELS[std]} ({name})" if std in LABELS else name
        options.append({
            "label": label,
            "tag": name,
            "format_spec": f"bv*[height<={real}]+ba/b[height<={real}]/b",
            "size": size or None,
            "audio_only": False,
        })
    if not options:
        options.append({"label": "Best quality", "tag": "best", "format_spec": "bv*+ba/b",
                        "size": _size(info) or None, "audio_only": False})
    if audio or buckets:
        options.append({"label": "Audio only (MP3)", "tag": "mp3", "format_spec": "ba/b",
                        "size": best_audio or None, "audio_only": True})
    return {"title": info.get("title") or "video", "url": info.get("webpage_url") or url,
            "duration": info.get("duration"), "options": options}
