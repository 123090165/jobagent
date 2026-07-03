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

interface DemoSearchResponse extends HelperResponseBase {
  platforms?: string[];
  candidates?: BrowserHelperJobCandidate[];
}

export interface BrowserHelperDemoResult {
  version: string | null;
  platforms: string[];
  candidates: BrowserHelperJobCandidate[];
}

const RESPONSE_TIMEOUT_MS = 3000;

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

export async function fetchBrowserHelperDemoCandidates(
  query: string
): Promise<BrowserHelperDemoResult> {
  const response = await sendHelperRequest<DemoSearchResponse>({
    action: "searchDemo",
    query
  });
  if (!response.ok) {
    throw new Error(response.error ?? "Browser helper demo search failed.");
  }
  return {
    version: response.version ?? null,
    platforms: response.platforms ?? ["demo"],
    candidates: response.candidates ?? []
  };
}

function sendHelperRequest<T extends HelperResponseBase>(
  payload: Record<string, unknown>
): Promise<T> {
  const id = `jobagent-helper-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      window.removeEventListener("message", onMessage);
      reject(new Error("Browser helper not detected."));
    }, RESPONSE_TIMEOUT_MS);

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
