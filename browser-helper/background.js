const HELPER_VERSION = "0.2.2";
const BOSS_PLATFORM = "boss";
const BOSS_HOME_URL = "https://www.zhipin.com/";
const BOSS_SEARCH_URL = "https://www.zhipin.com/web/geek/jobs";
const BOSS_SEARCH_API_PATH = "/wapi/zpgeek/search/joblist.json";
const BOSS_COOKIE_URL = "https://www.zhipin.com/";
const BOSS_MAX_QUERY_ATTEMPTS = 6;
const BOSS_PAGE_READY_TIMEOUT_MS = 12000;
const BOSS_PAGE_SIGNAL_INTERVAL_MS = 1000;
const BOSS_LOGIN_PROBE_QUERY = "ai";
const BOSS_LOGIN_PROBE_LOCATION = "shenzhen";
const BOSS_LOGIN_PROBE_TIMEOUT_MS = 12000;
const BOSS_BROAD_QUERY_FALLBACKS = [
  "\u7b97\u6cd5\u5b9e\u4e60",
  "AI\u7b97\u6cd5\u5b9e\u4e60",
  "\u4eba\u5de5\u667a\u80fd\u5b9e\u4e60"
];
const BOSS_ENGLISH_QUERY_REWRITES = [
  {
    pattern: /physiological signal|signal processing|ppg|ecg|biosignal|bio[- ]?signal/i,
    queries: ["\u751f\u7406\u4fe1\u53f7\u5904\u7406\u5b9e\u4e60", "\u4fe1\u53f7\u5904\u7406\u5b9e\u4e60"]
  },
  {
    pattern: /biomedical|medical|health|healthcare/i,
    queries: ["\u5065\u5eb7\u7b97\u6cd5\u5b9e\u4e60", "\u533b\u7597AI\u5b9e\u4e60"]
  },
  {
    pattern: /algorithm|machine learning|deep learning|artificial intelligence|\bai\b/i,
    queries: ["AI\u7b97\u6cd5\u5b9e\u4e60", "\u7b97\u6cd5\u5b9e\u4e60", "\u4eba\u5de5\u667a\u80fd\u5b9e\u4e60"]
  },
  {
    pattern: /data science|data analysis|data analyst|analytics/i,
    queries: ["\u6570\u636e\u5206\u6790\u5b9e\u4e60", "\u6570\u636e\u7b97\u6cd5\u5b9e\u4e60"]
  },
  {
    pattern: /backend|back[- ]?end|server[- ]?side/i,
    queries: ["\u540e\u7aef\u5f00\u53d1\u5b9e\u4e60", "\u8f6f\u4ef6\u5f00\u53d1\u5b9e\u4e60"]
  },
  {
    pattern: /frontend|front[- ]?end|web developer/i,
    queries: ["\u524d\u7aef\u5f00\u53d1\u5b9e\u4e60", "\u8f6f\u4ef6\u5f00\u53d1\u5b9e\u4e60"]
  },
  {
    pattern: /product manager|product/i,
    queries: ["\u4ea7\u54c1\u5b9e\u4e60", "\u4ea7\u54c1\u7ecf\u7406\u5b9e\u4e60"]
  },
  {
    pattern: /marketing|brand|growth|consumer insight|market research/i,
    queries: ["\u5e02\u573a\u8425\u9500\u5b9e\u4e60", "\u54c1\u724c\u8425\u9500\u5b9e\u4e60"]
  },
  {
    pattern: /finance|investment|quant/i,
    queries: ["\u91d1\u878d\u5b9e\u4e60", "\u91cf\u5316\u5b9e\u4e60"]
  }
];
const BOSS_AUTH_COOKIE_NAMES = [
  "wt2",
  "wbg",
  "zp_stoken",
  "__zp_stoken__",
  "zp_token",
  "boss_login_mode"
];
const BOSS_DEFAULT_JOB_TYPE_CODE = "1902";
const BOSS_JOB_TYPE_CODES = new Map([
  ["1901", "1901"],
  ["full_time", "1901"],
  ["full-time", "1901"],
  ["fulltime", "1901"],
  ["full", "1901"],
  ["regular", "1901"],
  ["\u5168\u804c", "1901"],
  ["\u6b63\u5f0f", "1901"],
  ["1902", "1902"],
  ["intern", "1902"],
  ["internship", "1902"],
  ["internship_only", "1902"],
  ["\u5b9e\u4e60", "1902"],
  ["\u5b9e\u4e60\u751f", "1902"]
]);

const BOSS_CITY_CODES = new Map([
  ["beijing", "101010100"],
  ["北京", "101010100"],
  ["shanghai", "101020100"],
  ["上海", "101020100"],
  ["guangzhou", "101280100"],
  ["广州", "101280100"],
  ["shenzhen", "101280600"],
  ["深圳", "101280600"],
  ["hangzhou", "101210100"],
  ["杭州", "101210100"],
  ["nanjing", "101190100"],
  ["南京", "101190100"],
  ["suzhou", "101190400"],
  ["苏州", "101190400"],
  ["chengdu", "101270100"],
  ["成都", "101270100"],
  ["wuhan", "101200100"],
  ["武汉", "101200100"],
  ["xian", "101110100"],
  ["xi'an", "101110100"],
  ["西安", "101110100"],
  ["tianjin", "101030100"],
  ["天津", "101030100"],
  ["chongqing", "101040100"],
  ["重庆", "101040100"]
]);

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
          capabilities: ["ping", "checkBossLogin", "openBossLogin", "searchBoss"]
        });
        return;
      }

      if (message.action === "checkBossLogin") {
        sendResponse({ ok: true, ...(await buildBossLoginStatus()) });
        return;
      }

      if (message.action === "openBossLogin") {
        const tab = await chrome.tabs.create({ url: BOSS_HOME_URL, active: true });
        sendResponse({
          ok: true,
          platform: BOSS_PLATFORM,
          loginUrl: BOSS_HOME_URL,
          tabId: tab.id
        });
        return;
      }

      if (message.action === "openLogin") {
        const platform = String(message.platform || "").trim();
        if (platform !== BOSS_PLATFORM) {
          sendResponse({ ok: false, error: `unsupported platform: ${platform}` });
          return;
        }
        const tab = await chrome.tabs.create({ url: BOSS_HOME_URL, active: true });
        sendResponse({
          ok: true,
          platform: BOSS_PLATFORM,
          loginUrl: BOSS_HOME_URL,
          tabId: tab.id
        });
        return;
      }

      if (message.action === "searchBoss") {
        const loginStatus = await buildBossLoginStatus();
        if (!loginStatus.loggedIn) {
          sendResponse({
            ok: false,
            platform: BOSS_PLATFORM,
            loginRequired: true,
            loginUrl: BOSS_HOME_URL,
            error: "BOSS login is required before searching."
          });
          return;
        }

        const queries = normalizeBossSearchQueries(message.queries, message.query);
        if (!queries.length) {
          sendResponse({ ok: false, error: "missing BOSS search query" });
          return;
        }

        const limit = clampInteger(message.limit, 1, 30, 10);
        const location = String(message.location || "").trim();
        const jobType = String(message.jobType || "").trim();
        const result = await searchBossJobs({ queries, location, jobType, limit });
        sendResponse({
          ok: true,
          version: HELPER_VERSION,
          platform: BOSS_PLATFORM,
          platforms: [BOSS_PLATFORM],
          ...result
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

async function buildBossLoginStatus() {
  const cookies = await getBossCookies();
  const cookieNames = new Set(cookies.filter((cookie) => cookie.value).map((cookie) => cookie.name));
  const matchedAuthCookies = BOSS_AUTH_COOKIE_NAMES.filter((name) => cookieNames.has(name));
  const missingAuthCookies = BOSS_AUTH_COOKIE_NAMES.filter((name) => !cookieNames.has(name));
  const cookieLoggedIn = matchedAuthCookies.length > 0;
  const verification = cookies.length
    ? await probeBossLoginSession()
    : {
        verified: true,
        loggedIn: false,
        status: "no_cookies",
        reason: "No BOSS cookies are visible to the helper."
      };
  return {
    platform: BOSS_PLATFORM,
    loggedIn: verification.loggedIn,
    loginUrl: BOSS_HOME_URL,
    cookieCount: cookies.length,
    cookieLoggedIn,
    matchedAuthCookies,
    missingAuthCookies,
    sessionVerified: verification.verified,
    verificationStatus: verification.status,
    verificationReason: verification.reason,
    probeUrl: verification.probeUrl || null,
    probePageTitle: verification.pageTitle || null,
    probeBodyTextLength: verification.bodyTextLength || 0,
    probeJobCardCount: verification.jobCardCount || 0,
    probeValidJobDetailLinkCount: verification.validJobDetailLinkCount || 0,
    loginLikelyRequired: Boolean(verification.loginLikelyRequired),
    verificationLikelyRequired: Boolean(verification.verificationLikelyRequired)
  };
}

async function probeBossLoginSession() {
  const probeUrl = buildBossSearchUrl(
    BOSS_LOGIN_PROBE_QUERY,
    BOSS_LOGIN_PROBE_LOCATION,
    BOSS_DEFAULT_JOB_TYPE_CODE
  );
  let tab = null;
  try {
    tab = await chrome.tabs.create({ url: probeUrl, active: false });
    await waitTabComplete(tab.id, 15000);
    await sleep(1000);
    const signals = await waitForBossPageSignals(tab.id, BOSS_LOGIN_PROBE_TIMEOUT_MS);
    return interpretBossLoginProbe(signals, probeUrl);
  } catch (error) {
    return {
      verified: false,
      loggedIn: false,
      status: "probe_error",
      reason: `BOSS login probe failed: ${String(error)}`,
      probeUrl
    };
  } finally {
    if (tab?.id) {
      try {
        await chrome.tabs.remove(tab.id);
      } catch (_error) {
        // The user may close the probe tab before the helper does.
      }
    }
  }
}

function interpretBossLoginProbe(signals, probeUrl) {
  if (!signals) {
    return {
      verified: false,
      loggedIn: false,
      status: "probe_no_signal",
      reason: "BOSS login probe returned no page signals.",
      probeUrl
    };
  }
  const base = {
    verified: true,
    probeUrl: signals.pageUrl || probeUrl,
    pageTitle: signals.pageTitle || null,
    bodyTextLength: signals.bodyTextLength || 0,
    jobCardCount: signals.jobCardCount || 0,
    validJobDetailLinkCount: signals.validJobDetailLinkCount || 0,
    loginLikelyRequired: Boolean(signals.loginLikelyRequired),
    verificationLikelyRequired: Boolean(signals.verificationLikelyRequired)
  };
  if (signals.verificationLikelyRequired) {
    return {
      ...base,
      loggedIn: false,
      status: "verification_required",
      reason: "BOSS probe page requires security verification."
    };
  }
  if (signals.loginLikelyRequired) {
    return {
      ...base,
      loggedIn: false,
      status: "login_required",
      reason: "BOSS probe page requires login."
    };
  }
  if (signals.jobCardCount > 0 || signals.validJobDetailLinkCount > 0) {
    return {
      ...base,
      loggedIn: true,
      status: "valid",
      reason: "BOSS probe page exposed job cards or job detail links."
    };
  }
  if (signals.noResultLikely && signals.bodyTextLength > 0) {
    return {
      ...base,
      loggedIn: true,
      status: "valid_empty_result",
      reason: "BOSS probe page loaded an empty-result state without login or verification prompts."
    };
  }
  return {
    ...base,
    loggedIn: false,
    status: "probe_inconclusive",
    reason: "BOSS probe page did not expose login prompts or job results."
  };
}

async function getBossCookies() {
  const cookieGroups = await Promise.all([
    chrome.cookies.getAll({ url: BOSS_COOKIE_URL }),
    chrome.cookies.getAll({ domain: "zhipin.com" })
  ]);
  const seen = new Set();
  const result = [];
  for (const cookie of cookieGroups.flat()) {
    const key = `${cookie.storeId}:${cookie.domain}:${cookie.path}:${cookie.name}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    result.push(cookie);
  }
  return result;
}

function normalizeBossSearchQueries(rawQueries, rawQuery) {
  const hasQueryList = Array.isArray(rawQueries) && rawQueries.length > 0;
  const values = hasQueryList ? rawQueries : [rawQuery];
  const queries = uniqueStrings(values.flatMap(toBossSearchQueries))
    .map((value) => value.slice(0, 80))
    .filter(Boolean)
    .slice(0, BOSS_MAX_QUERY_ATTEMPTS);
  return queries.length ? queries : BOSS_BROAD_QUERY_FALLBACKS.slice(0, BOSS_MAX_QUERY_ATTEMPTS);
}

function toBossSearchQueries(value) {
  const query = cleanText(value).slice(0, 80);
  if (!query) {
    return [];
  }
  if (containsCjk(query)) {
    return [query];
  }
  const rewritten = BOSS_ENGLISH_QUERY_REWRITES.flatMap((rule) =>
    rule.pattern.test(query) ? rule.queries : []
  );
  return rewritten;
}

function containsCjk(value) {
  return /[\u3400-\u9fff]/.test(String(value || ""));
}

async function searchBossJobs({ queries, location, jobType, limit }) {
  const cityCode = resolveBossCityCode(location);
  const jobTypeCode = resolveBossJobTypeCode(jobType);
  const directAttempts = [];
  const directWarnings = [];
  for (const query of queries) {
    const searchUrl = buildBossSearchUrl(query, location, jobTypeCode);
    const apiUrl = buildBossSearchApiUrl(query, cityCode, jobTypeCode, limit);
    const apiResult = await fetchBossJobsFromWorkerApi({
      query,
      requestedLocation: location,
      limit,
      searchUrl,
      apiUrl
    });
    directAttempts.push(buildBossSearchAttempt(query, apiResult));
    directWarnings.push(...(apiResult.warnings || []));
    if (apiResult.candidates.length) {
      return {
        ...apiResult,
        attemptedQueries: queries,
        searchAttempts: directAttempts,
        successfulQuery: query
      };
    }
  }

  const firstSearchUrl = buildBossSearchUrl(queries[0], location, jobTypeCode);
  const tab = await chrome.tabs.create({ url: firstSearchUrl, active: false });
  let shouldCloseTab = true;
  const tabAttempts = [];
  let lastResult = null;
  try {
    for (const query of queries) {
      const result = await searchBossJobsInTab(tab.id, {
        query,
        requestedLocation: location,
        limit,
        cityCode,
        jobTypeCode
      });
      lastResult = result;
      tabAttempts.push(buildBossSearchAttempt(query, result));
      if (result.candidates.length) {
        return {
          ...result,
          warnings: uniqueStrings([...directWarnings, ...(result.warnings || [])]),
          attemptedQueries: queries,
          searchAttempts: [...directAttempts, ...tabAttempts],
          successfulQuery: query
        };
      }
    }

    const result = lastResult || {
      searchUrl: firstSearchUrl,
      candidates: [],
      warnings: ["BOSS search returned no result."]
    };
    result.tabId = tab.id;
    result.tabKeptOpen = false;
    result.attemptedQueries = queries;
    result.searchAttempts = [...directAttempts, ...tabAttempts];
    result.warnings = uniqueStrings([
      ...directWarnings,
      ...(result.warnings || []),
      "BOSS fallback tab was closed because no valid job candidates were parsed."
    ]);
    return result;
  } finally {
    if (shouldCloseTab) {
      try {
        await chrome.tabs.remove(tab.id);
      } catch (_error) {
        // The user may close the tab before extraction completes.
      }
    }
  }
}

async function searchBossJobsInTab(tabId, { query, requestedLocation, limit, cityCode, jobTypeCode }) {
  const searchUrl = buildBossSearchUrl(query, requestedLocation, jobTypeCode);
  const apiUrl = buildBossSearchApiUrl(query, cityCode, jobTypeCode, limit);
  await chrome.tabs.update(tabId, { url: searchUrl, active: false });
  await waitTabComplete(tabId, 15000);
  await sleep(1000);

  const apiResult = await fetchBossJobsFromPageApi(tabId, {
    query,
    requestedLocation,
    limit,
    searchUrl,
    apiUrl
  });
  if (apiResult.candidates.length) {
    return apiResult;
  }

  const readinessSignals = await waitForBossPageSignals(tabId, BOSS_PAGE_READY_TIMEOUT_MS);
  const [extraction] = await chrome.scripting.executeScript({
    target: { tabId },
    func: extractBossJobsFromPage,
    args: [{ query, requestedLocation, limit, searchUrl }]
  });
  const result = extraction?.result || {
    searchUrl,
    candidates: [],
    warnings: ["BOSS page extraction returned no result."]
  };
  result.warnings = uniqueStrings([
    ...(apiResult.warnings || []),
    ...(result.warnings || [])
  ]);
  result.diagnostics = result.diagnostics || readinessSignals || null;
  return result;
}

function buildBossSearchAttempt(query, result) {
  const diagnostics = result.diagnostics || null;
  return {
    query,
    candidateCount: Array.isArray(result.candidates) ? result.candidates.length : 0,
    searchUrl: result.searchUrl || null,
    pageUrl: result.pageUrl || null,
    pageTitle: result.pageTitle || null,
    warnings: result.warnings || [],
    diagnostics: diagnostics
      ? {
          jobCardCount: diagnostics.jobCardCount || 0,
          validJobDetailLinkCount: diagnostics.validJobDetailLinkCount || 0,
          noResultLikely: Boolean(diagnostics.noResultLikely),
          loginLikelyRequired: Boolean(diagnostics.loginLikelyRequired),
          verificationLikelyRequired: Boolean(diagnostics.verificationLikelyRequired),
          apiStatus: diagnostics.apiStatus || null,
          apiShape: diagnostics.apiShape || null
        }
      : null
  };
}

function buildBossSearchUrl(query, location, jobTypeCode = BOSS_DEFAULT_JOB_TYPE_CODE) {
  const url = new URL(BOSS_SEARCH_URL);
  url.searchParams.set("query", query);
  const cityCode = resolveBossCityCode(location);
  if (cityCode) {
    url.searchParams.set("city", cityCode);
  }
  url.searchParams.set("jobType", resolveBossJobTypeCode(jobTypeCode));
  return url.toString();
}

function buildBossSearchApiUrl(query, cityCode, jobTypeCode, limit) {
  const url = new URL(BOSS_SEARCH_API_PATH, BOSS_HOME_URL);
  url.searchParams.set("scene", "1");
  url.searchParams.set("query", query);
  const resolvedJobTypeCode = resolveBossJobTypeCode(jobTypeCode);
  const resolvedLimit = clampInteger(limit, 1, 30, 10);
  if (cityCode) {
    url.searchParams.set("city", cityCode);
  }
  for (const name of [
    "experience",
    "payType",
    "partTime",
    "degree",
    "industry",
    "scale",
    "stage",
    "position",
    "salary",
    "multiBusinessDistrict",
    "multiSubway"
  ]) {
    url.searchParams.set(name, "");
  }
  url.searchParams.set("jobType", resolvedJobTypeCode);
  url.searchParams.set("page", "1");
  url.searchParams.set("pageSize", String(resolvedLimit));
  return url.toString();
}

function resolveBossJobTypeCode(jobType) {
  const normalized = String(jobType || "").trim().toLowerCase();
  if (!normalized) {
    return BOSS_DEFAULT_JOB_TYPE_CODE;
  }
  return BOSS_JOB_TYPE_CODES.get(normalized) || BOSS_DEFAULT_JOB_TYPE_CODE;
}

function resolveBossCityCode(location) {
  const normalized = String(location || "").trim().toLowerCase();
  if (!normalized) {
    return "";
  }
  for (const [label, code] of BOSS_CITY_CODES.entries()) {
    if (normalized.includes(label.toLowerCase())) {
      return code;
    }
  }
  return "";
}

function waitTabComplete(tabId, timeoutMs) {
  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) {
        return;
      }
      done = true;
      chrome.tabs.onUpdated.removeListener(listener);
      resolve();
    };
    function listener(id, info) {
      if (id === tabId && info.status === "complete") {
        finish();
      }
    }
    chrome.tabs.onUpdated.addListener(listener);
    setTimeout(finish, timeoutMs);
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function clampInteger(value, min, max, fallback) {
  const parsed = Number.parseInt(String(value), 10);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(min, Math.min(max, parsed));
}

async function fetchBossJobsFromWorkerApi({ query, requestedLocation, limit, searchUrl, apiUrl }) {
  try {
    const response = await fetch(apiUrl, {
      method: "GET",
      credentials: "include",
      headers: {
        accept: "application/json, text/plain, */*",
        "x-requested-with": "XMLHttpRequest"
      }
    });
    const text = await response.text();
    const data = parseJsonOrNull(text);
    if (!response.ok || !data) {
      return {
        searchUrl,
        candidates: [],
        warnings: [
          `BOSS worker joblist API did not return usable JSON for "${query}" (status ${response.status || "unknown"}).`
        ],
        diagnostics: {
          apiTransport: "extension_worker",
          apiStatus: response.status || null,
          apiContentType: response.headers.get("content-type"),
          apiPreview: text.slice(0, 500)
        }
      };
    }
    const candidates = parseBossApiCandidates(data, {
      query,
      requestedLocation,
      limit,
      searchUrl
    });
    return {
      searchUrl,
      pageUrl: null,
      pageTitle: null,
      warnings: candidates.length
        ? []
        : [`BOSS worker joblist API returned JSON but no valid job candidates were parsed for "${query}".`],
      diagnostics: candidates.length
        ? null
        : buildBossApiDiagnostics(data, {
            transport: "extension_worker",
            status: response.status,
            contentType: response.headers.get("content-type"),
            textPreview: text
          }),
      candidates
    };
  } catch (error) {
    return {
      searchUrl,
      candidates: [],
      warnings: [`BOSS worker joblist API fetch failed for "${query}": ${String(error)}`],
      diagnostics: {
        apiTransport: "extension_worker",
        readError: String(error)
      }
    };
  }
}

async function fetchBossJobsFromPageApi(tabId, { query, requestedLocation, limit, searchUrl, apiUrl }) {
  try {
    const [apiFetch] = await chrome.scripting.executeScript({
      target: { tabId },
      world: "MAIN",
      func: fetchBossJobListFromPage,
      args: [{ apiUrl }]
    });
    const response = apiFetch?.result;
    if (!response) {
      return {
        searchUrl,
        candidates: [],
        warnings: ["BOSS joblist API returned no response."]
      };
    }
    if (!response.ok || !response.data) {
      return {
        searchUrl,
        candidates: [],
        warnings: [
          `BOSS joblist API did not return usable JSON (status ${response.status || "unknown"}).`
        ],
        diagnostics: {
          apiTransport: "page_context",
          apiStatus: response.status || null,
          apiContentType: response.contentType || null,
          apiPreview: response.textPreview || null
        }
      };
    }
    const candidates = parseBossApiCandidates(response.data, {
      query,
      requestedLocation,
      limit,
      searchUrl
    });
    return {
      searchUrl,
      pageUrl: response.pageUrl || null,
      pageTitle: response.pageTitle || null,
      warnings: candidates.length
        ? []
        : [`BOSS joblist API returned JSON but no valid job candidates were parsed for "${query}".`],
      diagnostics: candidates.length
        ? null
        : buildBossApiDiagnostics(response.data, {
            transport: "page_context",
            status: response.status,
            contentType: response.contentType,
            textPreview: response.textPreview
          }),
      candidates
    };
  } catch (error) {
    return {
      searchUrl,
      candidates: [],
      warnings: [`BOSS joblist API fetch failed: ${String(error)}`]
    };
  }
}

function parseJsonOrNull(text) {
  try {
    return text ? JSON.parse(text) : null;
  } catch (_error) {
    return null;
  }
}

function buildBossApiDiagnostics(data, { transport, status, contentType, textPreview }) {
  const jobs = findBossJobList(data);
  return {
    apiTransport: transport,
    apiStatus: status || null,
    apiContentType: contentType || null,
    apiPreview: String(textPreview || "").slice(0, 500),
    apiShape: summarizeObjectShape(data),
    apiDetectedJobLikeCount: jobs.length
  };
}

function summarizeObjectShape(value) {
  if (!value || typeof value !== "object") {
    return typeof value;
  }
  const summary = {
    topLevelKeys: Object.keys(value).slice(0, 20)
  };
  if (value.zpData && typeof value.zpData === "object") {
    summary.zpDataKeys = Object.keys(value.zpData).slice(0, 20);
  }
  if (value.data && typeof value.data === "object") {
    summary.dataKeys = Object.keys(value.data).slice(0, 20);
  }
  return summary;
}

async function waitForBossPageSignals(tabId, timeoutMs) {
  const startedAt = Date.now();
  let latestSignals = null;
  while (Date.now() - startedAt < timeoutMs) {
    latestSignals = await readBossPageSignals(tabId);
    if (
      latestSignals &&
      (latestSignals.jobCardCount > 0 ||
        latestSignals.validJobDetailLinkCount > 0 ||
        latestSignals.loginLikelyRequired ||
        latestSignals.verificationLikelyRequired ||
        latestSignals.noResultLikely)
    ) {
      return latestSignals;
    }
    await sleep(BOSS_PAGE_SIGNAL_INTERVAL_MS);
  }
  return latestSignals;
}

async function readBossPageSignals(tabId) {
  try {
    const [signals] = await chrome.scripting.executeScript({
      target: { tabId },
      func: collectBossPageSignals
    });
    return signals?.result || null;
  } catch (error) {
    return {
      pageUrl: null,
      pageTitle: null,
      readyState: null,
      bodyTextLength: 0,
      jobCardCount: 0,
      jobDetailLinkCount: 0,
      validJobDetailLinkCount: 0,
      loginLikelyRequired: false,
      verificationLikelyRequired: false,
      noResultLikely: false,
      readError: String(error)
    };
  }
}

function fetchBossJobListFromPage({ apiUrl }) {
  return fetch(apiUrl, {
    method: "GET",
    credentials: "include",
    headers: {
      accept: "application/json, text/plain, */*",
      "x-requested-with": "XMLHttpRequest"
    }
  }).then(async (response) => {
    const text = await response.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch (_error) {
      data = null;
    }
    return {
      ok: response.ok,
      status: response.status,
      url: response.url,
      contentType: response.headers.get("content-type"),
      data,
      textPreview: text.slice(0, 500),
      pageUrl: window.location.href,
      pageTitle: document.title
    };
  });
}

function parseBossApiCandidates(data, { query, requestedLocation, limit, searchUrl }) {
  const jobs = findBossJobList(data);
  return jobs
    .map((job, index) => parseBossApiCandidate(job, index + 1, { query, requestedLocation, searchUrl }))
    .filter((candidate) => candidate.title && candidate.source_url)
    .slice(0, Math.max(1, limit));
}

function findBossJobList(data) {
  const directCandidates = [
    data?.zpData?.jobList,
    data?.zpData?.jobs,
    data?.data?.jobList,
    data?.data?.jobs,
    data?.data?.list,
    data?.jobList,
    data?.jobs
  ];
  for (const candidate of directCandidates) {
    if (Array.isArray(candidate) && candidate.some(isBossJobLike)) {
      return candidate.filter(isPlainObject);
    }
  }

  const queue = [data];
  const seen = new Set();
  while (queue.length) {
    const item = queue.shift();
    if (!item || typeof item !== "object" || seen.has(item)) {
      continue;
    }
    seen.add(item);
    if (Array.isArray(item)) {
      if (item.some(isBossJobLike)) {
        return item.filter(isPlainObject);
      }
      queue.push(...item);
      continue;
    }
    queue.push(...Object.values(item));
  }
  return [];
}

function parseBossApiCandidate(job, rank, { query, requestedLocation, searchUrl }) {
  const title = firstNonEmpty([
    job.jobName,
    job.jobTitle,
    job.title,
    job.positionName,
    job.position
  ]);
  const company = firstNonEmpty([
    job.brandName,
    job.companyName,
    job.companyShortName,
    job.encryptBrandName,
    job.company?.brandName,
    job.company?.name
  ]);
  const locationParts = uniqueStrings([
    job.cityName,
    job.areaDistrict,
    job.businessDistrict,
    job.locationName,
    job.address
  ]);
  const labelParts = uniqueStrings([
    job.salaryDesc,
    job.jobExperience,
    job.jobDegree,
    job.brandIndustry,
    job.brandScaleName,
    job.stageName,
    job.bossName,
    job.bossTitle,
    ...toStringArray(job.jobLabels),
    ...toStringArray(job.skills),
    ...toStringArray(job.welfareList)
  ]);
  const snippet = uniqueStrings([...labelParts, ...locationParts]).join(" | ");
  const sourceUrl = buildBossJobDetailUrl(job) || validBossJobDetailUrl(firstNonEmpty([
    job.jobUrl,
    job.url,
    job.href,
    job.linkUrl
  ]));
  return {
    title,
    company: company || null,
    location: locationParts.join(" ") || requestedLocation || null,
    source_url: sourceUrl,
    source_provider: "boss_zhipin",
    snippet: snippet || `${title} ${company}`.trim() || `BOSS search result for ${query}`,
    raw_description: snippet || JSON.stringify(job).slice(0, 3000),
    discovery_query: query,
    discovery_rank: rank,
    detail_status: "boss_search_api",
    provider_warnings: [
      "Collected by JobAgent Browser Helper from the user's local BOSS browser session."
    ]
  };
}

function buildBossJobDetailUrl(job) {
  const encryptJobId = firstNonEmpty([job.encryptJobId, job.encryptId, job.jobId]);
  if (!encryptJobId) {
    return null;
  }
  const url = new URL(`/job_detail/${encryptJobId}.html`, BOSS_HOME_URL);
  const lid = firstNonEmpty([job.lid, job.listId]);
  const securityId = firstNonEmpty([job.securityId]);
  if (lid) {
    url.searchParams.set("lid", lid);
  }
  if (securityId) {
    url.searchParams.set("securityId", securityId);
  }
  return url.toString();
}

function isBossJobLike(item) {
  return (
    isPlainObject(item) &&
    Boolean(
      item.jobName ||
        item.jobTitle ||
        item.positionName ||
        item.encryptJobId ||
        item.securityId ||
        item.salaryDesc
    )
  );
}

function isPlainObject(value) {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function firstNonEmpty(values) {
  for (const value of values) {
    const normalized = cleanText(value);
    if (normalized) {
      return normalized;
    }
  }
  return "";
}

function toStringArray(value) {
  if (!Array.isArray(value)) {
    return value ? [value] : [];
  }
  return value.map((item) => {
    if (typeof item === "string") {
      return item;
    }
    if (item && typeof item === "object") {
      return item.name || item.label || item.value || "";
    }
    return String(item || "");
  });
}

function validBossJobDetailUrl(href) {
  if (!href) {
    return null;
  }
  try {
    const url = new URL(href, BOSS_HOME_URL);
    if (!/\/job_detail\/[^/?#]+/.test(url.pathname)) {
      return null;
    }
    return url.toString();
  } catch (_error) {
    return null;
  }
}

function collectBossPageSignals() {
  const bodyText = document.body ? document.body.innerText || "" : "";
  const jobCardSelectors = [
    ".job-card-wrapper",
    ".job-card-box",
    ".job-card-body",
    ".search-job-result li",
    ".job-list-container li",
    ".job-list-wrapper li",
    ".job-list-box li",
    ".job-primary",
    "[data-jobid]",
    "[ka^='search_list_']"
  ];
  const jobDetailLinks = Array.from(document.querySelectorAll('a[href*="/job_detail/"]'));
  const validJobDetailLinks = jobDetailLinks.filter((link) => {
    try {
      const url = new URL(link.getAttribute("href") || "", window.location.origin);
      return /\/job_detail\/[^/?#]+/.test(url.pathname);
    } catch (_error) {
      return false;
    }
  });
  return {
    pageUrl: window.location.href,
    pageTitle: document.title,
    readyState: document.readyState,
    bodyTextLength: bodyText.length,
    jobCardCount: jobCardSelectors.reduce(
      (count, selector) => count + document.querySelectorAll(selector).length,
      0
    ),
    jobDetailLinkCount: jobDetailLinks.length,
    validJobDetailLinkCount: validJobDetailLinks.length,
    loginLikelyRequired: /登录后|请登录|扫码登录/.test(bodyText),
    verificationLikelyRequired: /验证码|安全验证|身份验证|请完成验证/.test(bodyText),
    noResultLikely: /暂无|没有找到|未找到|无相关职位|换个关键词|换一个关键词/.test(bodyText),
    bodyPreview: bodyText.replace(/\s+/g, " ").trim().slice(0, 300)
  };
}

function extractBossJobsFromPage({ query, requestedLocation, limit, searchUrl }) {
  const warnings = [];
  const bodyText = document.body ? document.body.innerText || "" : "";
  const loginLikelyRequired =
    /登录后|请登录|扫码登录|验证码|安全验证|身份验证|请完成验证/.test(bodyText);
  if (loginLikelyRequired) {
    warnings.push("BOSS page appears to require login or verification.");
  }

  const cardSelectors = [
    ".job-card-wrapper",
    ".job-card-box",
    ".job-card-body",
    ".search-job-result li",
    ".job-list-container li",
    ".job-list-wrapper li",
    ".job-list-box li",
    ".job-primary",
    "[data-jobid]",
    "[ka^='search_list_']"
  ];
  const cardsFromSelectors = cardSelectors.flatMap((selector) => Array.from(document.querySelectorAll(selector)));
  const cardsFromLinks = Array.from(document.querySelectorAll('a[href*="/job_detail/"]'))
    .map((link) => link.closest(".job-card-wrapper, .job-card-box, .job-card-body, .job-primary, li, [data-jobid]"))
    .filter(Boolean);
  const cards = uniqueElements([...cardsFromSelectors, ...cardsFromLinks]);
  let candidates = cards.map((card, index) => parseBossJobCard(card, index + 1, query));

  if (!candidates.length) {
    candidates = parseBossJobLinks(query);
  }

  candidates = candidates
    .filter((candidate) => candidate.title && candidate.source_url)
    .slice(0, Math.max(1, limit));

  if (!candidates.length) {
    warnings.push("No BOSS job cards were parsed from the loaded page.");
  }

  return {
    searchUrl,
    pageUrl: window.location.href,
    pageTitle: document.title,
    loginLikelyRequired,
    diagnostics: collectSignals(),
    warnings,
    candidates: candidates.map((candidate, index) => ({
      ...candidate,
      discovery_rank: index + 1,
      provider_warnings: [
        ...(candidate.provider_warnings || []),
        ...warnings,
        "Collected by JobAgent Browser Helper from the user's local BOSS browser session."
      ]
    }))
  };

  function parseBossJobCard(card, rank, discoveryQuery) {
    const link = card.querySelector('a[href*="/job_detail/"], a[href*="/job_detail"], a[href*="/wapi/zpgeek/job/detail"]');
    const title = firstText(card, [
      ".job-name",
      ".job-title",
      ".job-card-left a",
      "[class*='job-name']",
      "[class*='job-title']",
      ".name",
      "a[href*='/job_detail/']"
    ]);
    const company = firstText(card, [
      ".company-name",
      ".company-text h3 a",
      ".company-text .name",
      "[class*='company-name']",
      ".company-info .name",
      ".boss-name"
    ]);
    const area = firstText(card, [".job-area", ".job-location", "[class*='job-area']", "[class*='location']", ".area"]);
    const salary = firstText(card, [".salary", "[class*='salary']", ".red"]);
    const tags = texts(card, [
      ".tag-list li",
      ".tag-list span",
      ".job-card-footer li",
      ".job-card-footer span",
      ".info-desc"
    ]);
    const sourceUrl = absoluteJobDetailUrl(link && link.getAttribute("href"));
    const cardLines = textLines(card.innerText).slice(0, 14);
    const snippetParts = [salary, ...tags, ...cardLines].filter(Boolean);
    const snippet = uniqueStrings(snippetParts).join(" | ").slice(0, 1200);
    return {
      title: title || (link ? cleanText(link.innerText) : ""),
      company: company || null,
      location: area || requestedLocation || null,
      source_url: sourceUrl,
      source_provider: "boss_zhipin",
      snippet: snippet || cleanText(card.innerText).slice(0, 1200),
      raw_description: snippet || cleanText(card.innerText).slice(0, 3000),
      discovery_query: discoveryQuery,
      discovery_rank: rank,
      detail_status: "boss_search_list_dom",
      provider_warnings: []
    };
  }

  function parseBossJobLinks(discoveryQuery) {
    return uniqueElements(Array.from(document.querySelectorAll('a[href*="/job_detail/"]')))
      .map((link, index) => {
        const text = cleanText(link.innerText || link.textContent || "");
        return {
          title: text || "BOSS job",
          company: null,
          location: requestedLocation || null,
          source_url: absoluteJobDetailUrl(link.getAttribute("href")),
          source_provider: "boss_zhipin",
          snippet: text || `BOSS search result for ${discoveryQuery}`,
          raw_description: text || `BOSS search result for ${discoveryQuery}`,
          discovery_query: discoveryQuery,
          discovery_rank: index + 1,
          detail_status: "boss_search_link_dom",
          provider_warnings: ["Parsed from BOSS job detail links because card selectors did not match."]
        };
      });
  }

  function firstText(root, selectors) {
    for (const selector of selectors) {
      const element = root.querySelector(selector);
      const text = element ? cleanText(element.innerText || element.textContent || "") : "";
      if (text) {
        return text;
      }
    }
    return "";
  }

  function texts(root, selectors) {
    return uniqueStrings(
      selectors.flatMap((selector) =>
        Array.from(root.querySelectorAll(selector)).map((element) =>
          cleanText(element.innerText || element.textContent || "")
        )
      )
    );
  }

  function absoluteUrl(href) {
    if (!href) {
      return null;
    }
    try {
      return new URL(href, window.location.origin).toString();
    } catch (_error) {
      return null;
    }
  }

  function absoluteJobDetailUrl(href) {
    const url = absoluteUrl(href);
    if (!url) {
      return null;
    }
    try {
      const parsed = new URL(url);
      if (!/\/job_detail\/[^/?#]+/.test(parsed.pathname)) {
        return null;
      }
      return parsed.toString();
    } catch (_error) {
      return null;
    }
  }

  function collectSignals() {
    const jobDetailLinks = Array.from(document.querySelectorAll('a[href*="/job_detail/"]'));
    const validJobDetailLinks = jobDetailLinks.filter((link) => absoluteJobDetailUrl(link.getAttribute("href")));
    return {
      pageUrl: window.location.href,
      pageTitle: document.title,
      readyState: document.readyState,
      bodyTextLength: bodyText.length,
      jobCardCount: cards.length,
      jobDetailLinkCount: jobDetailLinks.length,
      validJobDetailLinkCount: validJobDetailLinks.length,
      loginLikelyRequired,
      verificationLikelyRequired: /验证码|安全验证|身份验证|请完成验证/.test(bodyText),
      noResultLikely: /暂无|没有找到|未找到|无相关职位|换个关键词|换一个关键词/.test(bodyText),
      bodyPreview: bodyText.replace(/\s+/g, " ").trim().slice(0, 300)
    };
  }

  function uniqueElements(elements) {
    return Array.from(new Set(elements.filter(Boolean)));
  }

  function uniqueStrings(values) {
    const result = [];
    const seen = new Set();
    for (const value of values) {
      const item = cleanText(value);
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

  function textLines(value) {
    return uniqueStrings(String(value || "").split(/\n+/));
  }

  function cleanText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }
}

function uniqueStrings(values) {
  const result = [];
  const seen = new Set();
  for (const value of values) {
    const item = cleanText(value);
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

function cleanText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}
