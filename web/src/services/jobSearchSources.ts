export type ProviderSearchSource = "cuhksz_career" | "linkedin" | "remoteok";
export type SearchSource = ProviderSearchSource | "boss";

export const PROVIDER_SEARCH_SOURCES: ProviderSearchSource[] = [
  "cuhksz_career",
  "linkedin",
  "remoteok"
];

export const SOURCE_LABELS: Record<string, string> = {
  boss: "BOSS",
  boss_zhipin: "BOSS",
  zhipin: "BOSS",
  cuhksz_career: "CUHKSZ Career",
  linkedin: "LinkedIn",
  remoteok: "RemoteOK",
  serper_web: "Web Search",
  browser_helper: "Browser Helper",
  browser_helper_demo: "Browser Helper Demo",
  live_search: "Live Search",
  local_mock: "Local Demo",
  mock: "Local Demo"
};

const PROVIDER_SEARCH_SOURCE_VALUES = new Set<ProviderSearchSource>(PROVIDER_SEARCH_SOURCES);

export function isProviderSearchSource(value: unknown): value is ProviderSearchSource {
  return PROVIDER_SEARCH_SOURCE_VALUES.has(value as ProviderSearchSource);
}

export function normalizeProviderSearchSources(values: unknown): ProviderSearchSource[] {
  if (!Array.isArray(values)) {
    return [];
  }
  return values.filter(isProviderSearchSource);
}

export function legacySelectedSearchSources(controls: unknown): string[] {
  if (!controls || typeof controls !== "object") {
    return [];
  }
  const values = (controls as { selectedSearchSources?: unknown }).selectedSearchSources;
  return Array.isArray(values) ? values.map((value) => String(value)) : [];
}

export function uniqueProviderSearchSources(values: ProviderSearchSource[]): ProviderSearchSource[] {
  const result: ProviderSearchSource[] = [];
  const seen = new Set<ProviderSearchSource>();
  for (const value of values) {
    if (seen.has(value)) {
      continue;
    }
    seen.add(value);
    result.push(value);
  }
  return result;
}

export function sameProviderSearchSources(
  left: ProviderSearchSource[],
  right: ProviderSearchSource[]
): boolean {
  const normalizedLeft = uniqueProviderSearchSources(left);
  const normalizedRight = uniqueProviderSearchSources(right);
  return (
    normalizedLeft.length === normalizedRight.length &&
    normalizedLeft.every((value, index) => value === normalizedRight[index])
  );
}

export function normalizeSourceKey(source: string | null | undefined): string {
  const normalized = (source ?? "").trim().toLowerCase();
  if (normalized === "boss_zhipin" || normalized === "zhipin") {
    return "boss";
  }
  return normalized;
}

export function uniqueSourceKeys(sources: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const items: string[] = [];
  for (const source of sources) {
    const normalized = normalizeSourceKey(source);
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    items.push(normalized);
  }
  return items;
}

export function sourcesFromProviderName(providerName: string | null | undefined): string[] {
  const normalized = (providerName ?? "").trim().toLowerCase();
  if (!normalized) {
    return [];
  }
  if (normalized.startsWith("browser_helper:")) {
    const suffix = normalized.slice("browser_helper:".length);
    return uniqueSourceKeys(
      suffix.split(",").map((source) => (source === "manual" ? "browser_helper" : source))
    );
  }
  if (normalized === "browser_helper") {
    return ["boss"];
  }
  if (normalized.startsWith("multi_source:")) {
    return uniqueSourceKeys(normalized.slice("multi_source:".length).split(","));
  }
  return uniqueSourceKeys([normalized]);
}

export function formatSourceName(source: string | null | undefined): string {
  const normalized = normalizeSourceKey(source);
  if (!normalized) {
    return "Unknown";
  }
  return SOURCE_LABELS[normalized] ?? normalized;
}

export function formatProviderName(providerName: string | null | undefined): string {
  const sources = sourcesFromProviderName(providerName);
  if (sources.length) {
    return sources.map(formatSourceName).join(" + ");
  }
  return providerName || "not set";
}

export function formatSearchSources(sources: Array<string | null | undefined>, fallback = "Not set"): string {
  const labels = uniqueSourceKeys(sources).map(formatSourceName);
  return labels.join(", ") || fallback;
}
