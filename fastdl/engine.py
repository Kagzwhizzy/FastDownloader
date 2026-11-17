"""Download engine: multi-connection HTTP downloads (IDM style) + video downloads via yt-dlp."""
import mimetypes
import os
import re
import threading
import time
import urllib.parse
import uuid

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
CHUNK = 64 * 1024
MIN_SEGMENT = 1024 * 1024  # don't split files into parts smaller than 1 MB


class StopDownload(Exception):
    pass


class RateLimiter:
    """One speed limit shared by all downloads (token bucket). rate = bytes/second, 0 = unlimited."""

    def __init__(self):
        self.rate = 0
        self._allow = 0.0
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def set_rate(self, bps):
        with self._lock:
            self.rate = max(0, int(bps or 0))
            self._allow = 0.0
            self._last = time.monotonic()

    def consume(self, n, stop=None):
        if self.rate <= 0 or n <= 0:
            return
        with self._lock:
            now = time.monotonic()
            self._allow = min(self.rate * 0.5, self._allow + (now - self._last) * self.rate)
            self._last = now
            self._allow -= n
            wait = -self._allow / self.rate if self._allow < 0 else 0
        while wait > 0:
            if stop is not None and stop.is_set():
                return
            step = min(wait, 0.1)
            time.sleep(step)
            wait -= step


LIMITER = RateLimiter()

# IDM-style automatic folders
CATEGORIES = {
    "Videos": {"mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "m4v", "3gp", "mpg", "mpeg", "ts"},
    "Music": {"mp3", "m4a", "aac", "flac", "wav", "ogg", "opus", "wma"},
    "Programs": {"exe", "msi", "apk", "xapk", "dmg", "appx", "msix", "deb", "rpm", "bat"},
    "Compressed": {"zip", "rar", "7z", "tar", "gz", "bz2", "xz", "iso", "img", "cab"},
    "Documents": {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "rtf", "odt", "epub", "csv"},
    "Pictures": {"jpg", "jpeg", "png", "gif", "webp", "bmp", "svg", "heic"},
}


def category_for(filename):
    ext = os.path.splitext(filename or "")[1].lower().lstrip(".")
    for cat, exts in CATEGORIES.items():
        if ext in exts:
            return cat
    return "Other"


def human_size(n):
    if n is None or n <= 0:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def human_time(sec):
    if sec is None or sec < 0:
        return ""
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else (f"{m}m {s:02d}s" if m else f"{s}s")


WIN_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_name(name):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    if os.path.splitext(name)[0].upper() in WIN_RESERVED:
        name = "_" + name
    if len(name) > 180:
        root, ext = os.path.splitext(name)
        name = root[: 180 - len(ext)] + ext
    return name or "download"


def unique_path(folder, filename):
    root, ext = os.path.splitext(filename)
    path = os.path.join(folder, filename)
    i = 1
    while os.path.exists(path) or os.path.exists(path + ".part0") or os.path.exists(path + ".part"):
        path = os.path.join(folder, f"{root} ({i}){ext}")
        i += 1
    return path


def _filename_from_response(r, url):
    cd = r.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*\s*=\s*[^']*''([^;]+)", cd, re.I)
    if m:
        return safe_name(re.split(r"[\\/]", urllib.parse.unquote(m.group(1).strip().strip('"')))[-1])
    m = re.search(r'filename\s*=\s*"?([^";]+)"?', cd, re.I)
    if m:
        return safe_name(re.split(r"[\\/]", m.group(1).strip())[-1])
    name = urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(r.url or url).path))
    name = safe_name(name) if name else "download"
    if "." not in name:
        ctype = r.headers.get("Content-Type", "").split(";")[0].strip()
        ext = mimetypes.guess_extension(ctype) if ctype else None
        if ext and ctype not in ("text/html", "application/octet-stream"):
            name += ext
    return name


def make_session(headers=None):
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    if headers:
        s.headers.update({k: v for k, v in headers.items() if v})
    return s


def probe(url, headers=None, timeout=20):
    """Ask the server about a file. Returns dict(final_url, filename, total, resumable, content_type)."""
    s = make_session(headers)
    r = s.get(url, stream=True, timeout=timeout, allow_redirects=True, headers={"Range": "bytes=0-"})
    if r.status_code >= 400:
        # some servers refuse Range requests (or empty files answer 416) -> ask normally
        r.close()
        r = s.get(url, stream=True, timeout=timeout, allow_redirects=True)
    try:
        if r.status_code >= 400:
            raise IOError(f"Server answered HTTP {r.status_code}")
        total = None
        resumable = r.status_code == 206
        cr = r.headers.get("Content-Range", "")
        m = re.search(r"/(\d+)$", cr)
        if m:
            total = int(m.group(1))
        elif r.headers.get("Content-Length", "").isdigit():
            total = int(r.headers["Content-Length"])
        return {
            "final_url": r.url,
            "filename": _filename_from_response(r, url),
            "total": total,
            "resumable": resumable and bool(total),
            "content_type": r.headers.get("Content-Type", ""),
        }
    finally:
        r.close()


class BaseTask:
    kind = "base"

    def __init__(self, url, folder, filename=None, id=None, status="queued", total=None, done=0,
                 error="", created=None, headers=None, was_active=False, **_):
        self.id = id or uuid.uuid4().hex[:12]
        self.was_active = was_active   # was downloading when the app closed -> continue on start
        self.url = url
        self.folder = folder
        self.filename = filename
        self.status = status
        self.total = total
        self.done = done
        self.error = error
        self.created = created or time.time()
        self.headers = headers or {}
        self.speed = 0.0
        self._last = (time.time(), done)
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()

    # ---- control -------------------------------------------------------
    @property
    def active(self):
        return self._thread is not None and self._thread.is_alive()

    @property
    def path(self):
        return os.path.join(self.folder, self.filename) if self.filename else None

    def start(self):
        if self.active or self.status == "done":
            return
        os.makedirs(self.folder, exist_ok=True)
        self._stop.clear()
        self.error = ""
        self.status = "downloading"
        self._last = (time.time(), self.done)
        self._thread = threading.Thread(target=self._wrap, daemon=True)
        self._thread.start()

    def pause(self):
        if self.active:
            self._stop.set()

    def _wrap(self):
        try:
            self._run()
            if self._stop.is_set() and self.status != "done":
                self.status = "paused"
        except Exception as e:  # noqa: BLE001 - shown to the user
            if self._stop.is_set():
                self.status = "paused"
            else:
                self.status = "error"
                self.error = str(e).replace("ERROR: ", "")[:300]
        self.speed = 0.0

    def _add(self, n):
        with self._lock:
            self.done += n

    def tick(self):
        """Called by the UI about twice a second to update speed."""
        now = time.time()
        t0, d0 = self._last
        dt = now - t0
        if dt >= 0.4:
            inst = max(0.0, (self.done - d0) / dt)
            self.speed = inst if self.speed == 0 else self.speed * 0.6 + inst * 0.4
            self._last = (now, self.done)
        if not self.active:
            self.speed = 0.0

    @property
    def eta(self):
        if self.total and self.speed > 1:
            return (self.total - self.done) / self.speed
        return None

    def to_dict(self):
        return {
            "kind": self.kind, "id": self.id, "url": self.url, "folder": self.folder,
            "filename": self.filename,
            "status": "paused" if self.status in ("downloading", "processing") else self.status,
            "total": self.total, "done": self.done, "error": self.error, "created": self.created,
            "headers": self.headers, "was_active": self.active, **self.extra(),
        }

    def extra(self):
        return {}

    def temp_files(self):
        return []

    def delete_files(self, include_final=False):
        files = list(self.temp_files())
        if include_final and self.path:
            files.append(self.path)
        for f in files:
            try:
                if f and os.path.exists(f):
                    os.remove(f)
            except OSError:
                pass


class HttpTask(BaseTask):
    """Normal file download, split into several parts downloaded at the same time."""
    kind = "http"

    def __init__(self, url, folder, connections=8, segments=None, final_url=None, resumable=None,
                 probed=False, **kw):
        super().__init__(url, folder, **kw)
        self.connections = max(1, min(32, int(connections)))
        self.segments = segments or []          # list of [start, end] (inclusive)
        self.final_url = final_url or url
        self.resumable = resumable
        self.probed = probed

    def extra(self):
        return {"connections": self.connections, "segments": self.segments, "final_url": self.final_url,
                "resumable": self.resumable, "probed": self.probed}

    def _part(self, i):
        return f"{self.path}.part{i}"

    def temp_files(self):
        if not self.path:
            return []
        if self.segments:
            return [self._part(i) for i in range(len(self.segments))]
        return [self.path + ".part"]

    def apply_probe(self, info):
        self.final_url = info["final_url"]
        self.total = info["total"]
        self.resumable = info["resumable"]
        if not self.filename:
            self.filename = os.path.basename(unique_path(self.folder, info["filename"]))
        self.probed = True

    def _run(self):
        if not self.probed:
            self.apply_probe(probe(self.url, self.headers))
        if self._stop.is_set():
            raise StopDownload()
        if self.total == 0:   # empty file
            os.makedirs(self.folder, exist_ok=True)
            open(self.path, "wb").close()
            self.status = "done"
            return
        if self.resumable and self.total and not self.segments:
            n = max(1, min(self.connections, self.total // MIN_SEGMENT))
            size = self.total // n
            self.segments = [[i * size, (self.total - 1) if i == n - 1 else (i + 1) * size - 1] for i in range(n)]
        if self.segments:
            self._run_segmented()
        else:
            self._run_single()

    # ---- many connections ----------------------------------------------
    def _run_segmented(self):
        self.done = sum(os.path.getsize(self._part(i)) for i in range(len(self.segments))
                        if os.path.exists(self._part(i)))
        errors = []
        threads = []
        for i in range(len(self.segments)):
            t = threading.Thread(target=self._seg_worker, args=(i, errors), daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        if errors:            # a real failure: show it as an error, not as "paused"
            raise errors[0]
        if self._stop.is_set():
            raise StopDownload()
        # all parts complete -> join them into the final file
        self.status = "processing"
        final = self.path
        if os.path.exists(final):
            final = unique_path(self.folder, self.filename)
            self.filename = os.path.basename(final)
        with open(final + ".joining", "wb") as out:
            for i in range(len(self.segments)):
                with open(self._part(i), "rb") as f:
                    while True:
                        b = f.read(1024 * 1024)
                        if not b:
                            break
                        out.write(b)
        os.replace(final + ".joining", final)
        for i in range(len(self.segments)):
            try:
                os.remove(self._part(i))
            except OSError:
                pass
        self.done = self.total
        self.status = "done"

    def _seg_worker(self, i, errors):
        start, end = self.segments[i]
        need = end - start + 1
        path = self._part(i)
        s = make_session(self.headers)
        last = None
        hard_fails = 0
        # Many download sites allow only a few connections at once and answer "busy" (429/503)
        # or drop the connection. Those parts just wait and retry while the others keep going.
        for attempt in range(40):
            have = os.path.getsize(path) if os.path.exists(path) else 0
            if have >= need:
                return
            try:
                with s.get(self.final_url, headers={"Range": f"bytes={start + have}-{end}"},
                           stream=True, timeout=30) as r:
                    if r.status_code != 206:
                        if r.status_code in (401, 403, 404, 410):
                            hard_fails += 1
                        raise IOError(f"Server answered HTTP {r.status_code} for part {i + 1}")
                    with open(path, "ab") as f:
                        remaining = need - have
                        for chunk in r.iter_content(CHUNK):
                            if self._stop.is_set():
                                return
                            if not chunk:
                                continue
                            chunk = chunk[:remaining]
                            f.write(chunk)
                            remaining -= len(chunk)
                            self._add(len(chunk))
                            LIMITER.consume(len(chunk), self._stop)
                            if remaining <= 0:
                                break
                if os.path.getsize(path) >= need:
                    return
            except Exception as e:  # noqa: BLE001 - retry, then report
                last = e
                if self._stop.is_set():
                    return
                if hard_fails >= 5:      # link expired / forbidden -> stop trying
                    break
                wait = min(30, 2 + attempt * 2)
                for _ in range(wait * 10):
                    if self._stop.is_set():
                        return
                    time.sleep(0.1)
        errors.append(last or IOError(f"Part {i + 1} could not be downloaded"))
        self._stop.set()  # stop the other parts too

    # ---- single connection (server doesn't allow splitting) -----------
    def _run_single(self):
        tmp = self.path + ".part"
        self.done = 0
        s = make_session(self.headers)
        with s.get(self.final_url, stream=True, timeout=30) as r:
            if r.status_code >= 400:
                raise IOError(f"Server answered HTTP {r.status_code}")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(CHUNK):
                    if self._stop.is_set():
                        raise StopDownload()
                    if chunk:
                        f.write(chunk)
                        self._add(len(chunk))
                        LIMITER.consume(len(chunk), self._stop)
        final = self.path
        if os.path.exists(final):
            final = unique_path(self.folder, self.filename)
            self.filename = os.path.basename(final)
        os.replace(tmp, final)
        self.total = self.done
        self.status = "done"


class VideoTask(BaseTask):
    """Video/audio download from YouTube and ~1800 other sites, using yt-dlp."""
    kind = "video"

    def __init__(self, url, folder, format_spec="bv*+ba/b", label="best", audio_only=False,
                 title="", expected_total=None, partials=None, subs=None, sub_note="", **kw):
        super().__init__(url, folder, **kw)
        self.format_spec = format_spec
        self.label = label
        self.audio_only = audio_only
        self.title = title
        self.expected_total = expected_total
        self.partials = partials or []
        self.subs = subs or []          # subtitle languages, e.g. ["en"]
        self.sub_note = sub_note
        if not self.filename and title:
            self.filename = f"{safe_name(title)} [{label}]"   # display name until the real one is known

    def extra(self):
        return {"format_spec": self.format_spec, "label": self.label, "audio_only": self.audio_only,
                "title": self.title, "expected_total": self.expected_total, "partials": self.partials,
                "subs": self.subs, "sub_note": self.sub_note}

    def temp_files(self):
        out = []
        for p in self.partials:
            out += [p, p + ".part", p + ".ytdl"]
        return out

    def _run(self):
        from yt_dlp import YoutubeDL
        from . import video

        base = {"n": 0}
        last = {"b": 0}
        if self.expected_total:
            self.total = self.expected_total

        def hook(d):
            if self._stop.is_set():
                raise StopDownload()
            got = d.get("downloaded_bytes") or 0
            if got > last["b"]:
                LIMITER.consume(got - last["b"], self._stop)
            last["b"] = got if d["status"] == "downloading" else 0
            tmp = d.get("tmpfilename") or d.get("filename")
            if tmp and tmp.endswith(".part"):
                tmp = tmp[:-5]
            if tmp and tmp not in self.partials:
                self.partials.append(tmp)
            if d["status"] == "downloading":
                self.status = "downloading"
                cur_total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                self.done = base["n"] + (d.get("downloaded_bytes") or 0)
                if self.expected_total:
                    self.total = max(self.expected_total, self.done)
                elif cur_total:
                    self.total = base["n"] + cur_total
            elif d["status"] == "finished":
                base["n"] += d.get("total_bytes") or d.get("downloaded_bytes") or 0
                self.done = base["n"]

        def pp_hook(d):
            if d.get("status") == "started":
                self.status = "processing"

        name = "%(title).120B.%(ext)s" if self.audio_only else f"%(title).120B [{self.label}].%(ext)s"
        opts = video.base_opts(self.headers.get("Referer"))
        opts.update({
            "format": self.format_spec,
            "outtmpl": os.path.join(self.folder, name),
            "progress_hooks": [hook],
            "postprocessor_hooks": [pp_hook],
            "continuedl": True,
            "concurrent_fragment_downloads": 8,
            # same quality, but prefer H.264 + AAC so the file plays in any Windows/phone player
            "format_sort": ["res", "fps", "vcodec:h264", "acodec:aac", "ext:mp4:m4a"],
        })
        if self.audio_only:
            opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3",
                                       "preferredquality": "192"}]
        else:
            opts["merge_output_format"] = "mp4"
        # YouTube sometimes answers 403 for a moment; fresh links on a new try usually work
        for attempt in range(3):
            try:
                with YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(self.url, download=True)
                break
            except Exception as e:  # noqa: BLE001
                if self._stop.is_set() or attempt == 2 or not any(
                        s in str(e) for s in ("403", "Forbidden", "timed out", "Connection reset", "IncompleteRead")):
                    raise
                for _ in range(30 * (attempt + 1)):
                    if self._stop.is_set():
                        raise StopDownload()
                    time.sleep(0.1)
        if self._stop.is_set():
            raise StopDownload()
        if info and info.get("_type") == "playlist" and info.get("entries"):
            info = next(e for e in info["entries"] if e)
        path = None
        for rd in (info or {}).get("requested_downloads") or []:
            path = rd.get("filepath") or path
        if path and os.path.exists(path):
            self.folder = os.path.dirname(path)
            self.filename = os.path.basename(path)
            self.total = self.done = os.path.getsize(path)
        if self.subs and path:
            self._download_subs(name)
        self.status = "done"

    def _download_subs(self, name):
        """Subtitles in a separate pass, so a subtitle problem never ruins the video download."""
        from yt_dlp import YoutubeDL
        from . import video
        self.status = "processing"
        opts = video.base_opts(self.headers.get("Referer"))
        opts.update({
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": list(self.subs),
            "subtitlesformat": "srt/vtt/best",
            "outtmpl": os.path.join(self.folder, name),
            "postprocessors": [{"key": "FFmpegSubtitlesConvertor", "format": "srt"}],
        })
        try:
            with YoutubeDL(opts) as ydl:
                ydl.extract_info(self.url, download=True)
            self.sub_note = "subtitles saved"
        except Exception as e:  # noqa: BLE001
            self.sub_note = "subtitles not available: " + str(e).replace("ERROR: ", "")[:120]


def task_from_dict(d):
    d = dict(d)
    kind = d.pop("kind", "http")
    cls = VideoTask if kind == "video" else HttpTask
    try:
        return cls(**d)
    except TypeError:
        return None
