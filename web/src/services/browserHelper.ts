import type { BrowserHelperJobCandidate } from "../types/profileSession";

interface HelperResponseBase {
  id: string;
  ok: boolean;
  error?: string;
  version?: string;
}

export interface BrowserHelperStatus {
  installed: boolean;
  version: string | null;
  capabilities: string[];
  error: string | null;
}

interface PingResponse extends HelperResponseBase {
  capabilities?: string[];
}

interface BossLoginResponse extends HelperResponseBase {
  platform?: "boss";
  loggedIn?: boolean;
  loginUrl?: string;
  cookieCount?: number;
  cookieLoggedIn?: boolean;
  matchedAuthCookies?: string[];
  missingAuthCookies?: string[];
  sessionVerified?: boolean;
  verificationStatus?: string;
  verificationReason?: string | null;
  probeUrl?: string | null;
  probePageTitle?: string | null;
  probeBodyTextLength?: number;
  probeJobCardCount?: number;
  probeValidJobDetailLinkCount?: number;
  loginLikelyRequired?: boolean;
  verificationLikelyRequired?: boolean;
}

interface OpenBossLoginResponse extends HelperResponseBase {
  platform?: "boss";
  loginUrl?: string;
  tabId?: number;
}

interface BossSearchResponse extends HelperResponseBase {
  platform?: "boss";
  platforms?: string[];
  attemptedQueries?: string[];
  successfulQuery?: string;
  searchAttempts?: BossSearchAttempt[];
  searchUrl?: string;
  pageUrl?: string;
  pageTitle?: string;
  tabId?: number;
  tabKeptOpen?: boolean;
  loginRequired?: boolean;
  loginLikelyRequired?: boolean;
  warnings?: string[];
  diagnostics?: BossSearchDiagnostics | null;
  candidates?: BrowserHelperJobCandidate[];
}

export interface BossLoginStatus {
  platform: "boss";
  loggedIn: boolean;
  loginUrl: string;
  cookieCount: number;
  cookieLoggedIn: boolean;
  matchedAuthCookies: string[];
  missingAuthCookies: string[];
  sessionVerified: boolean;
  verificationStatus: string;
  verificationReason: string | null;
  probeUrl: string | null;
  probePageTitle: string | null;
  probeBodyTextLength: number;
  probeJobCardCount: number;
  probeValidJobDetailLinkCount: number;
  loginLikelyRequired: boolean;
  verificationLikelyRequired: boolean;
}

export interface BossSearchResult {
  version: string | null;
  platforms: string[];
  attemptedQueries: string[];
  successfulQuery: string | null;
  searchAttempts: BossSearchAttempt[];
  searchUrl: string | null;
  pageUrl: string | null;
  pageTitle: string | null;
  tabId: number | null;
  tabKeptOpen: boolean;
  warnings: string[];
  diagnostics: BossSearchDiagnostics | null;
  candidates: BrowserHelperJobCandidate[];
}

const DEFAULT_RESPONSE_TIMEOUT_MS = 3000;
const BOSS_LOGIN_RESPONSE_TIMEOUT_MS = 8000;
const BOSS_SEARCH_RESPONSE_TIMEOUT_MS = 90000;
const BOSS_AUTOMATION_DISABLED_MESSAGE =
  "BOSS automated search and login probing are disabled. Open a BOSS job detail page manually, then use the JobAgent extension Side Panel to analyze the current page.";

export interface BossSearchDiagnostics {
  apiTransport?: string | null;
  pageUrl?: string | null;
  pageTitle?: string | null;
  readyState?: string | null;
  bodyTextLength?: number;
  jobCardCount?: number;
  jobDetailLinkCount?: number;
  validJobDetailLinkCount?: number;
  loginLikelyRequired?: boolean;
  verificationLikelyRequired?: boolean;
  noResultLikely?: boolean;
  readError?: string;
  apiStatus?: number | null;
  apiContentType?: string | null;
  apiPreview?: string | null;
  apiShape?: unknown;
  apiDetectedJobLikeCount?: number;
}

export interface BossSearchAttempt {
  query: string;
  candidateCount: number;
  searchUrl?: string | null;
  pageUrl?: string | null;
  pageTitle?: string | null;
  warnings?: string[];
  diagnostics?: BossSearchDiagnostics | null;
}

export async function pingBrowserHelper(): Promise<BrowserHelperStatus> {
  try {
    const response = await sendHelperRequest<PingResponse>({ action: "ping" });
    if (!response.ok) {
      return {
        installed: false,
        version: null,
        capabilities: [],
        error: response.error ?? "Browser helper unavailable."
      };
    }
    return {
      installed: true,
      version: response.version ?? null,
      capabilities: response.capabilities ?? [],
      error: null
    };
  } catch (error) {
    return {
      installed: false,
      version: null,
      capabilities: [],
      error: error instanceof Error ? error.message : "Browser helper unavailable."
    };
  }
}

export async function checkBossLoginStatus(): Promise<BossLoginStatus> {
  throw new Error(BOSS_AUTOMATION_DISABLED_MESSAGE);
}

export async function openBossLoginPage(): Promise<void> {
  const response = await sendHelperRequest<OpenBossLoginResponse>(
    {
      action: "openBossLogin"
    },
    {
      timeoutMs: BOSS_LOGIN_RESPONSE_TIMEOUT_MS,
      timeoutMessage: "Opening the BOSS login page timed out. Confirm the Browser Helper is enabled on this page."
    }
  );
  if (!response.ok) {
    throw new Error(response.error ?? "Failed to open BOSS login page.");
  }
}

export async function fetchBossCandidates(
  query: string,
  location: string | null,
  limit: number,
  queries: string[] = [],
  jobType = "intern"
): Promise<BossSearchResult> {
  void query;
  void location;
  void limit;
  void queries;
  void jobType;
  throw new Error(BOSS_AUTOMATION_DISABLED_MESSAGE);
}

interface HelperRequestOptions {
  timeoutMs?: number;
  timeoutMessage?: string;
}

function sendHelperRequest<T extends HelperResponseBase>(
  payload: Record<string, unknown>,
  options: HelperRequestOptions = {}
): Promise<T> {
  const id = `jobagent-helper-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const timeoutMs = options.timeoutMs ?? DEFAULT_RESPONSE_TIMEOUT_MS;
  const timeoutMessage = options.timeoutMessage ?? "Browser helper not detected.";
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      window.removeEventListener("message", onMessage);
      reject(new Error(timeoutMessage));
    }, timeoutMs);

    function onMessage(event: MessageEvent) {
      if (event.source !== window) {
        return;
      }
      const data = event.data as { __jobagentHelper?: boolean; response?: T };
      if (!data || data.__jobagentHelper !== true || !data.response) {
        return;
      }
      if (data.response.id !== id) {
        return;
      }
      window.clearTimeout(timeout);
      window.removeEventListener("message", onMessage);
      resolve(data.response);
    }

    window.addEventListener("message", onMessage);
    window.postMessage(
      {
        __jobagentHelper: true,
        request: {
          id,
          ...payload
        }
      },
      "*"
    );
  });
}
