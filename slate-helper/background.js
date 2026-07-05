// Slate 登录助手 — background service worker.
//
// Two privileged things this does:
//   1. open a normal login tab for the user to log in to a platform
//   2. read session cookies (incl. HttpOnly) for the platform and hand them
//      to the Slate web app
// Cookies are returned to the page that asked; the extension never sends
// them anywhere itself.
//
// Outbound API fetches to the platforms (Boss / Liepin) go through this
// service worker so they bypass the page's CORS — combined with the
// declarativeNetRequest rules in dnr-rules.json that rewrite
// Origin/Referer for Liepin's API, the platforms accept these requests
// as legitimate.

// 天眼查 only SSR's the search results (companyList in __NEXT_DATA__) for a real
// document NAVIGATION — a background XHR fetch just returns the homepage skeleton. So
// for tianyancha we open a hidden background tab, let it load, read the embedded
// __NEXT_DATA__ script, and close the tab. Requires the "scripting" permission.
function waitTabComplete(tabId, timeoutMs) {
  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      chrome.tabs.onUpdated.removeListener(listener);
      resolve();
    };
    function listener(id, info) { if (id === tabId && info.status === "complete") finish(); }
    chrome.tabs.onUpdated.addListener(listener);
    setTimeout(finish, timeoutMs);
  });
}

async function fetchViaTab(url) {
  const tab = await chrome.tabs.create({ url, active: false });
  try {
    await waitTabComplete(tab.id, 15000);
    const res = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const el = document.getElementById("__NEXT_DATA__");
        return el
          ? '<script id="__NEXT_DATA__" type="application/json">' + el.textContent + "</script>"
          : "";
      },
    });
    return (res && res[0] && res[0].result) || "";
  } finally {
    try { await chrome.tabs.remove(tab.id); } catch (e) { /* ignore */ }
  }
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    try {
      if (!msg || !msg.action) {
        sendResponse({ ok: false, error: "no action" });
        return;
      }

      if (msg.action === "ping") {
        sendResponse({ ok: true, version: "0.4.1" });
        return;
      }

      if (msg.action === "open") {
        // Open the platform login page in a normal foreground tab.
        const tab = await chrome.tabs.create({ url: msg.loginUrl, active: true });
        sendResponse({ ok: true, tabId: tab.id });
        return;
      }

      if (msg.action === "fetch") {
        // 天眼查 needs a real navigation (see fetchViaTab) — XHR returns only the shell.
        let host = "";
        try { host = new URL(msg.url).hostname; } catch (e) { /* ignore */ }
        if (/(^|\.)tianyancha\.com$/.test(host)) {
          const body = await fetchViaTab(msg.url);
          sendResponse({ ok: true, status: body ? 200 : 0, body });
          return;
        }
        const headers = Object.assign({}, msg.headers || {});

        // Liepin's API enforces XSRF: the X-Xsrf-Token header must equal the
        // XSRF-TOKEN cookie. credentials:include sends the cookie, but the
        // header has to be set explicitly.
        try {
          const u = new URL(msg.url);
          if (/\.liepin\.com$/.test(u.hostname) && !headers["X-Xsrf-Token"]) {
            const ck = await chrome.cookies.get({ url: msg.url, name: "XSRF-TOKEN" });
            if (ck && ck.value) headers["X-Xsrf-Token"] = ck.value;
          }
        } catch (e) { /* ignore */ }

        const init = {
          method: msg.method || "GET",
          credentials: "include",
          headers,
        };
        if (msg.body && init.method !== "GET" && init.method !== "HEAD") {
          init.body = msg.body;
        }
        const r = await fetch(msg.url, init);
        const body = await r.text();
        sendResponse({ ok: true, status: r.status, body });
        return;
      }

      if (msg.action === "capture") {
        // Read every cookie under the platform domain (and subdomains).
        const cookies = await chrome.cookies.getAll({ domain: msg.domain });
        const cookieStr = cookies
          .filter((c) => c.value)
          .map((c) => `${c.name}=${c.value}`)
          .join("; ");
        const names = new Set(cookies.filter((c) => c.value).map((c) => c.name));
        const authCookies = Array.isArray(msg.authCookies) ? msg.authCookies : [];
        const loggedIn = authCookies.length
          ? authCookies.some((n) => names.has(n))
          : cookies.length > 0;
        sendResponse({ ok: true, cookie: cookieStr, loggedIn, count: cookies.length });
        return;
      }

      sendResponse({ ok: false, error: "unknown action: " + msg.action });
    } catch (e) {
      sendResponse({ ok: false, error: String(e) });
    }
  })();
  return true; // keep the message channel open for the async sendResponse
});
