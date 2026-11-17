// Which edition of the extension this is.
// Full edition (GitHub download): works on every site.
// Chrome Web Store edition: build_store_extension.py replaces this file so the extension
// does nothing on the sites listed (store rules). Videos from those sites can still be
// downloaded with the FastDownloader desktop app itself.
self.FDL_EDITION = "full";
self.FDL_BLOCKED_HOSTS = [];

self.fdlBlocked = function (url) {
  try {
    const h = new URL(url).hostname.toLowerCase();
    return self.FDL_BLOCKED_HOSTS.some(b => h === b || h.endsWith("." + b));
  } catch (e) {
    return false;
  }
};
