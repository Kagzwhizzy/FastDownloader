// Modern floating "Download" button on top of videos (opens the quality picker in the app).
(() => {
  if (window.__fastdl) return;
  window.__fastdl = true;

  const host = document.createElement("div");
  host.style.cssText = "all:initial;position:fixed;z-index:2147483647;top:0;left:0;display:none;";
  const root = host.attachShadow({ mode: "closed" });
  root.innerHTML = `
    <style>
      :host { all: initial; }
      .wrap { display:flex; align-items:center; gap:6px; animation: in .28s cubic-bezier(.2,.9,.3,1.2); }
      @keyframes in { from { opacity:0; transform: translateY(-6px) scale(.96); } }
      .btn { display:flex; align-items:center; gap:8px; height:36px; padding:0 14px 0 6px; border-radius:999px;
             cursor:pointer; user-select:none; color:#fff; white-space:nowrap;
             font: 600 13px/1 "Segoe UI Variable Text","Segoe UI",system-ui,Arial,sans-serif;
             background: linear-gradient(135deg, rgba(124,58,237,.95), rgba(37,99,235,.95));
             box-shadow: 0 6px 20px rgba(37,99,235,.45), inset 0 1px 0 rgba(255,255,255,.25);
             backdrop-filter: blur(8px); transition: transform .15s, box-shadow .15s; }
      .btn:hover { transform: translateY(-1px); box-shadow: 0 10px 26px rgba(37,99,235,.6), inset 0 1px 0 rgba(255,255,255,.3); }
      .btn:active { transform: translateY(0) scale(.98); }
      .ic { width:26px; height:26px; border-radius:50%; background: rgba(255,255,255,.22);
            display:grid; place-items:center; }
      svg { width:15px; height:15px; fill:none; stroke:#fff; stroke-width:2.4; stroke-linecap:round; stroke-linejoin:round; }
      .q { font-size:10.5px; font-weight:700; padding:3px 6px; border-radius:6px; background: rgba(255,255,255,.2);
           letter-spacing:.3px; }
      .x { width:24px; height:24px; border-radius:50%; display:grid; place-items:center; cursor:pointer;
           background: rgba(17,17,27,.6); backdrop-filter: blur(6px); opacity:0; transition: opacity .15s; }
      .wrap:hover .x { opacity:1; }
      .x svg { width:11px; height:11px; }
      .ok .btn { background: linear-gradient(135deg, #16a34a, #059669); box-shadow: 0 6px 20px rgba(22,163,74,.45); }
      .bad .btn { background: linear-gradient(135deg, #dc2626, #ea580c); box-shadow: 0 6px 20px rgba(220,38,38,.45); }
    </style>
    <div class="wrap">
      <div class="btn" title="Download with FastDownloader">
        <span class="ic"><svg viewBox="0 0 24 24"><path d="M12 4v11m0 0-4.5-4.5M12 15l4.5-4.5M5 20h14"/></svg></span>
        <span class="t">Download</span>
        <span class="q">HD</span>
      </div>
      <div class="x" title="Hide"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg></div>
    </div>`;
  const wrap = root.querySelector(".wrap");
  const btn = root.querySelector(".btn");
  const label = root.querySelector(".t");
  const q = root.querySelector(".q");
  let current = null;
  const hidden = new WeakSet();

  function mount() {
    if (!host.isConnected) (document.body || document.documentElement).appendChild(host);
  }

  function pickVideo() {
    let best = null, area = 0;
    for (const v of document.querySelectorAll("video")) {
      if (hidden.has(v)) continue;
      const r = v.getBoundingClientRect();
      if (r.width < 200 || r.height < 110) continue;
      if (r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) continue;
      const a = r.width * r.height;
      if (a > area) { area = a; best = v; }
    }
    return best;
  }

  function qualityTag(v) {
    const h = v.videoHeight || 0;
    if (h >= 2000) return "4K";
    if (h >= 1400) return "2K";
    if (h >= 1000) return "HD";
    return "HD";
  }

  function place() {
    const v = pickVideo();
    current = v;
    if (!v || document.fullscreenElement) { host.style.display = "none"; return; }
    mount();
    host.style.display = "block";
    q.textContent = qualityTag(v);
    const r = v.getBoundingClientRect();
    const w = wrap.offsetWidth || 160;
    host.style.top = Math.max(6, r.top + 12) + "px";
    host.style.left = Math.max(6, Math.min(innerWidth - w - 10, r.right - w - 12)) + "px";
  }

  function flash(text, cls, ms = 2600) {
    label.textContent = text;
    wrap.classList.add(cls);
    setTimeout(() => { label.textContent = "Download"; wrap.classList.remove(cls); }, ms);
  }

  root.querySelector(".x").addEventListener("click", e => {
    e.stopPropagation(); e.preventDefault();
    if (current) hidden.add(current);
    host.style.display = "none";
  });

  btn.addEventListener("click", e => {
    e.stopPropagation(); e.preventDefault();
    const v = current;
    const src = v && (v.currentSrc || v.src);
    const direct = src && /^https?:/i.test(src) ? src : null;
    chrome.runtime.sendMessage(
      { type: "video", pageUrl: location.href, referrer: document.referrer || location.href, direct, title: document.title },
      res => {
        if (chrome.runtime.lastError || !res || !res.ok) flash("Open FastDownloader first", "bad", 3500);
        else flash("Choose quality in app", "ok");
      }
    );
  });

  setInterval(place, 800);
  addEventListener("scroll", place, { passive: true });
  addEventListener("resize", place);
  document.addEventListener("fullscreenchange", place);
})();
