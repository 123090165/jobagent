const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";
const STORAGE_KEYS = ["backendUrl", "sessionId", "useLlm"];

const backendUrlInput = document.getElementById("backendUrl");
const sessionIdInput = document.getElementById("sessionId");
const useLlmInput = document.getElementById("useLlm");
const analyzeButton = document.getElementById("analyzeButton");
const statusNode = document.getElementById("status");
const captureNode = document.getElementById("capture");
const reportNode = document.getElementById("report");
const warningsNode = document.getElementById("warnings");

init();

async function init() {
  const stored = await chrome.storage.local.get(STORAGE_KEYS);
  backendUrlInput.value = stored.backendUrl || DEFAULT_BACKEND_URL;
  sessionIdInput.value = stored.sessionId || "";
  useLlmInput.checked = Boolean(stored.useLlm);

  analyzeButton.addEventListener("click", analyzeCurrentJob);
  backendUrlInput.addEventListener("change", saveSettings);
  sessionIdInput.addEventListener("change", saveSettings);
  useLlmInput.addEventListener("change", saveSettings);
}

async function saveSettings() {
  await chrome.storage.local.set({
    backendUrl: backendUrlInput.value.trim() || DEFAULT_BACKEND_URL,
    sessionId: sessionIdInput.value.trim(),
    useLlm: useLlmInput.checked
  });
}

async function analyzeCurrentJob() {
  await saveSettings();
  clearResults();
  setBusy(true);
  setStatus("Capturing the current page...");
  let temporaryOrigin = null;
  try {
    temporaryOrigin = await ensureCurrentPagePermission();
    const response = await chrome.runtime.sendMessage({
      action: "analyzeCurrentJob",
      backendUrl: backendUrlInput.value.trim() || DEFAULT_BACKEND_URL,
      sessionId: sessionIdInput.value.trim(),
      useLlm: useLlmInput.checked
    });
    if (!response?.ok) {
      renderFailure(response);
      return;
    }
    renderSuccess(response);
  } catch (error) {
    setStatus(`Extension request failed: ${String(error)}`, true);
  } finally {
    if (temporaryOrigin) {
      await revokeTemporaryPermission(temporaryOrigin);
    }
    setBusy(false);
  }
}

async function ensureCurrentPagePermission() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const tabUrl = String(tab?.url || "");
  const origin = optionalOriginForTabUrl(tabUrl);
  if (!origin) {
    return null;
  }
  const hasPermission = await chrome.permissions.contains({ origins: [origin] });
  if (hasPermission) {
    return origin;
  }
  const granted = await chrome.permissions.request({ origins: [origin] });
  if (!granted) {
    throw new Error("Permission to read the current BOSS job detail page was not granted.");
  }
  return origin;
}

async function revokeTemporaryPermission(origin) {
  try {
    await chrome.permissions.remove({ origins: [origin] });
  } catch (_error) {
    // Permission cleanup is best-effort; the next capture still requests explicitly.
  }
}

function optionalOriginForTabUrl(value) {
  let parsed = null;
  try {
    parsed = new URL(value);
  } catch (_error) {
    return null;
  }
  if (!isBossJobDetailUrl(parsed)) {
    return null;
  }
  return "https://www.zhipin.com/*";
}

function isBossJobDetailUrl(url) {
  return url.protocol === "https:" &&
    url.hostname.toLowerCase() === "www.zhipin.com" &&
    /^\/job_detail\/[^/?#]+(?:\.html)?\/?$/i.test(url.pathname);
}

function renderSuccess(response) {
  const analysis = response.analysis;
  const capture = analysis?.capture || response.capture;
  const report = analysis?.report;
  setStatus("Analysis complete.");
  renderCapture(capture);
  if (report) {
    reportNode.classList.remove("hidden");
    reportNode.innerHTML = "";
    reportNode.append(
      heading("Match report"),
      div("score", String(report.overall_score ?? 0)),
      paragraph(report.recommendation || "No recommendation returned.", "meta"),
      list("Matched strengths", report.matched_strengths || []),
      list("Critical gaps", report.critical_gaps || []),
      list("Resume actions", report.resume_actions || [])
    );
  }
  renderWarnings(analysis?.warnings || response.capture?.warnings || []);
}

function renderFailure(response) {
  const message = response?.error || "Analysis failed.";
  const prefix = response?.errorType ? `${response.errorType}: ` : "";
  setStatus(`${prefix}${message}`, true);
  if (response?.capture) {
    renderCapture(response.capture);
    renderWarnings(response.capture.warnings || []);
  }
}

function renderCapture(capture) {
  if (!capture) {
    return;
  }
  captureNode.classList.remove("hidden");
  captureNode.innerHTML = "";
  captureNode.append(
    heading(capture.title || capture.page_title || "Captured page"),
    paragraph(capture.source_url || "", "meta"),
    paragraph(`Source: ${capture.source || "unknown"}`, "meta"),
    paragraph(`Company: ${capture.company || "Unknown"}`, "meta"),
    paragraph(`Location: ${capture.location || "Unknown"}`, "meta"),
    paragraph(capture.jd_text_preview || capture.jd_text || "", "preview")
  );
}

function renderWarnings(warnings) {
  const values = uniqueStrings(warnings || []);
  if (!values.length) {
    warningsNode.classList.add("hidden");
    warningsNode.innerHTML = "";
    return;
  }
  warningsNode.classList.remove("hidden");
  warningsNode.innerHTML = "";
  warningsNode.append(heading("Warnings"), list(null, values));
}

function list(title, values) {
  const fragment = document.createDocumentFragment();
  if (title) {
    fragment.append(paragraph(title, "meta"));
  }
  const ul = document.createElement("ul");
  ul.className = "list";
  const items = uniqueStrings(values);
  if (!items.length) {
    const li = document.createElement("li");
    li.textContent = "None returned.";
    ul.append(li);
  } else {
    for (const value of items) {
      const li = document.createElement("li");
      li.textContent = value;
      ul.append(li);
    }
  }
  fragment.append(ul);
  return fragment;
}

function heading(text) {
  const node = document.createElement("h2");
  node.className = "title";
  node.textContent = text;
  return node;
}

function paragraph(text, className) {
  const node = document.createElement("p");
  node.className = className;
  node.textContent = text;
  return node;
}

function div(className, text) {
  const node = document.createElement("div");
  node.className = className;
  node.textContent = text;
  return node;
}

function setStatus(text, isError = false) {
  statusNode.textContent = text;
  statusNode.classList.toggle("error", isError);
}

function setBusy(isBusy) {
  analyzeButton.disabled = isBusy;
  analyzeButton.textContent = isBusy ? "Analyzing..." : "Analyze current job";
}

function clearResults() {
  for (const node of [captureNode, reportNode, warningsNode]) {
    node.classList.add("hidden");
    node.innerHTML = "";
  }
}

function uniqueStrings(values) {
  const result = [];
  const seen = new Set();
  for (const value of values || []) {
    const item = String(value || "").trim();
    if (!item) {
      continue;
    }
    const key = item.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    result.push(item);
  }
  return result;
}
