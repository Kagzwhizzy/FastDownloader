// Talks to the FastDownloader app on this PC (127.0.0.1 only).
const API = "http://127.0.0.1:47321";

async function api(path, body) {
  const r = await fetch(API + path, {
    method: body ? "POST" : "GET",
    headers: { "X-FastDL": "1", "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}

async function appRunning() {
  try { await api("/ping"); return true; } catch { return false; }
}

async function cookieHeader(url) {
  try {
    const cs = await chrome.cookies.getAll({ url });
    return cs.map(c => c.name + "=" + c.value).join("; ");
  } catch { return ""; }
}

// ---- right-click menu ------------------------------------------------
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: "fdl-link", title: "Download with FastDownloader", contexts: ["link"] });
  chrome.contextMenus.create({ id: "fdl-video", title: "Download video with FastDownloader", contexts: ["video", "page", "frame"] });
  chrome.storage.local.get("intercept").then(v => {
    if (v.intercept === undefined) chrome.storage.local.set({ intercept: true });
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  try {
    if (info.menuItemId === "fdl-link") {
      await api("/download", { url: info.linkUrl, referrer: info.pageUrl, cookie: await cookieHeader(info.linkUrl), ua: navigator.userAgent });
    } else if (info.menuItemId === "fdl-video") {
      const direct = info.srcUrl && /^https?:/i.test(info.srcUrl) ? info.srcUrl : null;
      await api("/video", { pageUrl: info.frameUrl || info.pageUrl, referrer: info.pageUrl, direct, title: tab ? tab.title : "" });
    }
  } catch {
    notifyNotRunning();
  }
});

function notifyNotRunning() {
  chrome.action.setBadgeText({ text: "OFF" });
  chrome.action.setBadgeBackgroundColor({ color: "#b3261e" });
  setTimeout(() => chrome.action.setBadgeText({ text: "" }), 4000);
}

// ---- catch normal browser downloads (like IDM) -----------------------
const skipOnce = new Set();

// Every file type is taken over (exe, zip, rar, iso, apk, pdf, mp4, mp3, images, txt ...),
// except web pages. Before cancelling the browser's download, the app checks it can really
// download the link; if not (one-time links, form/POST downloads, blocked sites) the browser keeps it.
chrome.downloads.onCreated.addListener(async item => {
  const { intercept = true } = await chrome.storage.local.get("intercept");
  if (!intercept) return;
  const url = item.finalUrl || item.url;
  if (!/^https?:/i.test(url)) return;                      // blob:/data: links only exist inside the browser
  if (skipOnce.has(url)) { skipOnce.delete(url); return; }
  if ((item.mime || "").toLowerCase().startsWith("text/html")) return;
  if (!(await appRunning())) return;                       // app closed -> let the browser download it

  const req = { url, referrer: item.referrer || "", cookie: await cookieHeader(url), ua: navigator.userAgent };
  let check = null;
  try { check = await api("/probe", req); } catch {}
  if (!check || !check.ok) return;                         // app can't get it -> browser keeps downloading
  if ((check.info.content_type || "").toLowerCase().startsWith("text/html")) return;  // got a web page, not a file

  try { await chrome.downloads.cancel(item.id); } catch {}
  try { await chrome.downloads.erase({ id: item.id }); } catch {}
  const name = (item.filename || "").split(/[\\/]/).pop();
  try {
    await api("/download", { ...req, filename: name, info: check.info });
  } catch {
    skipOnce.add(url);
    chrome.downloads.download({ url });                    // fall back to the browser
  }
});

// ---- messages from the video button and the popup --------------------
chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  (async () => {
    try {
      if (msg.type === "video") {
        await api("/video", { pageUrl: msg.pageUrl, referrer: msg.referrer, direct: msg.direct, title: msg.title });
        reply({ ok: true });
      } else if (msg.type === "status") {
        reply({ ok: await appRunning() });
      } else {
        reply({ ok: false });
      }
    } catch {
      reply({ ok: false });
    }
  })();
  return true;
});
