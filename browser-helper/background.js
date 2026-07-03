const HELPER_VERSION = "0.1.0";

const LOGIN_URLS = {
  boss: "https://www.zhipin.com/",
  liepin: "https://www.liepin.com/"
};

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  (async () => {
    try {
      if (!message || !message.action) {
        sendResponse({ ok: false, error: "missing action" });
        return;
      }

      if (message.action === "ping") {
        sendResponse({
          ok: true,
          version: HELPER_VERSION,
          capabilities: ["ping", "openLogin", "searchDemo"]
        });
        return;
      }

      if (message.action === "openLogin") {
        const platform = String(message.platform || "").trim();
        const loginUrl = LOGIN_URLS[platform];
        if (!loginUrl) {
          sendResponse({ ok: false, error: `unsupported platform: ${platform}` });
          return;
        }
        const tab = await chrome.tabs.create({ url: loginUrl, active: true });
        sendResponse({ ok: true, platform, tabId: tab.id });
        return;
      }

      if (message.action === "searchDemo") {
        const query = String(message.query || "JobAgent browser helper").trim();
        sendResponse({
          ok: true,
          version: HELPER_VERSION,
          platforms: ["demo"],
          candidates: buildDemoCandidates(query)
        });
        return;
      }

      sendResponse({ ok: false, error: `unknown action: ${message.action}` });
    } catch (error) {
      sendResponse({ ok: false, error: String(error) });
    }
  })();
  return true;
});

function buildDemoCandidates(query) {
  const normalizedQuery = query || "JobAgent browser helper";
  return [
    {
      title: `${normalizedQuery} Browser Helper Candidate`,
      company: "JobAgent Helper Demo",
      location: "Remote",
      source_url: "https://jobs.example.com/jobagent-helper/demo",
      source_provider: "browser_helper_demo",
      snippet: "Demo candidate collected through the JobAgent Browser Helper bridge.",
      raw_description:
        "Demo candidate collected through the JobAgent Browser Helper bridge. Python, FastAPI, search workflows, and candidate ranking.",
      detail_status: "browser_helper_payload",
      provider_warnings: ["Demo payload; not fetched from a live recruiting platform."]
    }
  ];
}
