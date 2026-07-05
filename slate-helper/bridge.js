// Slate 登录助手 — content script bridge (runs on the Slate app pages only).
//
// Relays window.postMessage <-> chrome.runtime so the page never needs to know the
// extension id. The page posts {__slate:true, req:{id, action, ...}}; we forward to
// the background and post back {__slate:true, res:{id, ...}}.

// Announce presence as soon as we load (the app also pings to be sure).
window.postMessage({ __slate: true, type: "EXT_READY", version: "0.4.2" }, "*");

window.addEventListener("message", (ev) => {
  if (ev.source !== window) return;
  const d = ev.data;
  if (!d || d.__slate !== true || !d.req) return;
  let replied = false;
  try {
    chrome.runtime.sendMessage(d.req, (resp) => {
      // chrome.runtime.lastError fires if the worker is asleep/gone; report a failure.
      const err = chrome.runtime.lastError;
      replied = true;
      window.postMessage(
        { __slate: true, res: { id: d.req.id, ...(resp || { ok: false, error: err && err.message }) } },
        "*"
      );
    });
  } catch (e) {
    if (!replied) {
      window.postMessage({ __slate: true, res: { id: d.req.id, ok: false, error: String(e) } }, "*");
    }
  }
});
