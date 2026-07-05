import type { JobSearchPreview } from "../types/profileSession";
import type { BossSearchResult } from "./browserHelper";

export const BOSS_MAX_SEARCH_QUERY_ATTEMPTS = 6;
export const BOSS_DEFAULT_JOB_TYPE = "intern";

const BOSS_BROAD_QUERY_FALLBACKS = [
  "\u7b97\u6cd5\u5b9e\u4e60",
  "AI\u7b97\u6cd5\u5b9e\u4e60",
  "\u4eba\u5de5\u667a\u80fd\u5b9e\u4e60"
];

const BOSS_ENGLISH_QUERY_REWRITES: Array<{ pattern: RegExp; queries: string[] }> = [
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

export function buildBossSearchQueries(preview: JobSearchPreview): string[] {
  const seedTerms = [
    ...preview.target_roles,
    preview.query,
    ...preview.recall_queries,
    ...preview.provider_queries.slice(0, 4),
    ...preview.keywords.slice(0, 12)
  ];
  const localizedQueries = seedTerms.flatMap(toBossSearchQueries);
  const queries = uniqueBossQueries(localizedQueries);
  return (queries.length ? queries : BOSS_BROAD_QUERY_FALLBACKS).slice(
    0,
    BOSS_MAX_SEARCH_QUERY_ATTEMPTS
  );
}

export function formatBossEmptyResultMessage(result: BossSearchResult): string {
  const diagnostics = result.diagnostics;
  const parts = result.warnings.length ? [...result.warnings] : ["BOSS helper returned no candidates."];
  if (result.attemptedQueries.length) {
    parts.push(`Tried BOSS queries: ${result.attemptedQueries.join(", ")}.`);
  }
  if (result.searchAttempts.length) {
    const attempts = result.searchAttempts
      .map((attempt) => `${attempt.query}: ${attempt.candidateCount}`)
      .join(", ");
    parts.push(`Attempt results: ${attempts}.`);
  }
  const loadedPage = result.pageTitle || result.pageUrl;
  if (loadedPage) {
    parts.push(`Loaded page: ${result.pageTitle ?? "untitled"}${result.pageUrl ? ` (${result.pageUrl})` : ""}.`);
  }
  if (diagnostics) {
    const cardCount = diagnostics.jobCardCount ?? 0;
    const validLinkCount = diagnostics.validJobDetailLinkCount ?? 0;
    const bodyLength = diagnostics.bodyTextLength ?? 0;
    parts.push(
      `DOM signals: ${cardCount} card candidates, ${validLinkCount} valid job links, ${bodyLength} text chars.`
    );
    if (diagnostics.loginLikelyRequired) {
      parts.push("The loaded BOSS page still looks like a login page.");
    }
    if (diagnostics.verificationLikelyRequired) {
      parts.push("The loaded BOSS page looks like it requires verification.");
    }
    if (diagnostics.noResultLikely) {
      parts.push("The loaded BOSS page looks like an empty-result page.");
    }
    if (diagnostics.readError) {
      parts.push(`Diagnostic read failed: ${diagnostics.readError}.`);
    }
    if (diagnostics.apiTransport || diagnostics.apiStatus || diagnostics.apiDetectedJobLikeCount !== undefined) {
      parts.push(
        `API diagnostics: ${diagnostics.apiTransport ?? "unknown"} status ${diagnostics.apiStatus ?? "unknown"}, job-like rows ${diagnostics.apiDetectedJobLikeCount ?? "unknown"}.`
      );
    }
    if (diagnostics.apiShape) {
      parts.push(`API shape: ${JSON.stringify(diagnostics.apiShape)}.`);
    }
  }
  if (result.tabKeptOpen) {
    parts.push("The BOSS tab was kept open for inspection.");
  }
  return parts.join(" ");
}

function toBossSearchQueries(value: string): string[] {
  const query = cleanBossQuery(value);
  if (!query) {
    return [];
  }
  if (containsCjk(query)) {
    return [query];
  }
  return BOSS_ENGLISH_QUERY_REWRITES.flatMap((rule) =>
    rule.pattern.test(query) ? rule.queries : []
  );
}

function uniqueBossQueries(values: string[]): string[] {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const query = cleanBossQuery(value);
    if (!query) {
      continue;
    }
    const key = query.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    result.push(query);
  }
  return result;
}

function cleanBossQuery(value: string): string {
  return String(value || "").replace(/\s+/g, " ").trim().slice(0, 80);
}

function containsCjk(value: string): boolean {
  return /[\u3400-\u9fff]/.test(value);
}
