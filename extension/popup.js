// Donation details (same as the app)
const PAYPAL_URL = "https://www.paypal.com/donate/?business=saidimwangi054%40gmail.com&no_recurring=0&item_name=Support+FastDownloader&currency_code=USD";
const USDT_ADDRESS = "0x536dd935af551de218b7461d74ab12b42489363f";
const NETS = {
  bep20: "Network: <b>BNB Smart Chain (BEP20)</b> · lowest fees",
  erc20: "Network: <b>Ethereum (ERC20)</b> · higher fees",
};

const $ = id => document.getElementById(id);

// ---- connection status ----------------------------------------------
chrome.runtime.sendMessage({ type: "status" }, res => {
  const ok = !!(res && res.ok);
  $("status").className = "pill " + (ok ? "on" : "off");
  $("statusText").textContent = ok ? "Connected" : "Offline";
  $("offline").hidden = ok;
  $("vid").disabled = !ok;
});

// ---- catch downloads toggle -----------------------------------------
chrome.storage.local.get("intercept").then(v => { $("ic").checked = v.intercept !== false; });
$("ic").addEventListener("change", () => chrome.storage.local.set({ intercept: $("ic").checked }));

// ---- video on this page ---------------------------------------------
function toast(text, err) {
  const t = $("toast");
  t.textContent = text;
  t.className = "toast show" + (err ? " err" : "");
}
$("vid").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  chrome.runtime.sendMessage({ type: "video", pageUrl: tab.url, referrer: tab.url, title: tab.title }, res => {
    if (res && res.ok) toast("✓ Choose your quality in the FastDownloader window");
    else toast("Couldn't reach the app – is FastDownloader open?", true);
  });
});

// ---- support --------------------------------------------------------
document.querySelectorAll(".tab").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(x => x.classList.toggle("active", x === b));
  $("pane-pp").hidden = b.dataset.tab !== "pp";
  $("pane-usdt").hidden = b.dataset.tab !== "usdt";
}));
document.querySelectorAll(".net").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll(".net").forEach(x => x.classList.toggle("active", x === b));
  $("netinfo").innerHTML = NETS[b.dataset.net];
}));
$("netinfo").innerHTML = NETS.bep20;
$("addr").textContent = USDT_ADDRESS;
$("paypal").addEventListener("click", () => chrome.tabs.create({ url: PAYPAL_URL }));
$("copy").addEventListener("click", async () => {
  await navigator.clipboard.writeText(USDT_ADDRESS);
  const c = $("copy");
  c.classList.add("done");
  c.querySelector("span").textContent = "Copied";
  setTimeout(() => { c.classList.remove("done"); c.querySelector("span").textContent = "Copy"; }, 1800);
});
