<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NCard,
  NCheckbox,
  NCheckboxGroup,
  NInputNumber,
  NSwitch,
  NTag
} from "naive-ui";

import FlowPageHeader from "../components/FlowPageHeader.vue";
import {
  checkBossLoginStatus,
  fetchBossCandidates,
  openBossLoginPage,
  pingBrowserHelper,
  type BossLoginStatus,
  type BrowserHelperStatus
} from "../services/browserHelper";
import {
  useProfileSessionStore,
  type JobSearchPreviewControls,
  type JobSearchPreviewProviderSource
} from "../stores/profileSession";
import type { CreateJobSearchRunPayload, JobSearchPreview, JobSearchRun } from "../types/profileSession";

type ProviderSearchSource = JobSearchPreviewProviderSource;
type SearchSource = ProviderSearchSource | "boss";

const SOURCE_LABELS: Record<SearchSource, string> = {
  cuhksz_career: "CUHKSZ Career",
  linkedin: "LinkedIn",
  remoteok: "RemoteOK",
  boss: "BOSS"
};

const BOSS_MAX_SEARCH_QUERY_ATTEMPTS = 6;
const BOSS_DEFAULT_JOB_TYPE = "intern";
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
const PROVIDER_SEARCH_SOURCE_VALUES = new Set<ProviderSearchSource>([
  "cuhksz_career",
  "linkedin",
  "remoteok"
]);

const route = useRoute();
const router = useRouter();
const profileSessionStore = useProfileSessionStore();
const sessionId = computed(() => String(route.params.sessionId ?? ""));
const selectedProviderSearchSources = ref<ProviderSearchSource[]>(["cuhksz_career"]);
const isBossSourceSelected = ref(false);
const useLocalDemo = ref(false);
const useLlm = ref(false);
const maxResults = ref<number | null>(10);
const browserHelperStatus = ref<BrowserHelperStatus | null>(null);
const bossLoginStatus = ref<BossLoginStatus | null>(null);
const isBrowserHelperChecking = ref(false);
const isBossLoginChecking = ref(false);
const isBossSearching = ref(false);
const isRestoringPreviewControls = ref(false);
const browserHelperMessage = ref<string | null>(null);
let bossLoginRefreshTimer: number | null = null;
const selectedLlmProvider = computed(() => (useLlm.value ? "deepseek" : "ollama"));
const canStartSearch = computed(() => useLocalDemo.value || selectedSearchSources.value.length > 0);
const effectiveMaxResults = computed(() => maxResults.value ?? 10);
const selectedSearchSources = computed<SearchSource[]>(() => [
  ...selectedProviderSearchSources.value,
  ...(isBossSourceSelected.value ? (["boss"] as const) : [])
]);
const providerSearchSources = computed<ProviderSearchSource[]>(() => {
  return [...selectedProviderSearchSources.value];
});
const isBossSelected = computed(() => isBossSourceSelected.value);
const bossSearchQueriesForPreview = computed(() => {
  return profileSessionStore.jobSearchPreview
    ? buildBossSearchQueries(profileSessionStore.jobSearchPreview)
    : [];
});
const usesBrowserHelper = computed(() => isBossSelected.value && !useLocalDemo.value);
const selectedSourceLabel = computed(() => {
  if (useLocalDemo.value) {
    return "Local demo";
  }
  return selectedSearchSources.value.map((source) => SOURCE_LABELS[source]).join(", ") || "No source selected";
});
const backendProviderSourcesForRun = computed(() => {
  return providerSourcesForRun(profileSessionStore.jobSearchPreview);
});
const backendProviderSourceLabel = computed(() => {
  return backendProviderSourcesForRun.value.map((source) => SOURCE_LABELS[source]).join(", ") || "BOSS only";
});
const previewStatusLabel = computed(() => {
  if (profileSessionStore.isJobSearchPreviewLoading) {
    return "Refreshing preview";
  }
  if (!profileSessionStore.jobSearchPreview) {
    return "Preview unavailable";
  }
  return "Preview ready";
});
const previewStatusTagType = computed(() => {
  if (profileSessionStore.isJobSearchPreviewLoading) {
    return "warning";
  }
  if (profileSessionStore.jobSearchPreview) {
    return "success";
  }
  return "default";
});

const latestResultRun = computed<JobSearchRun | null>(() => {
  return (
    profileSessionStore.jobSearchRuns.find(
      (run) => run.status === "completed" && run.results.length > 0
    ) ?? null
  );
});

const canSeeResult = computed(() => latestResultRun.value !== null);

const llmStatusLabel = computed(() => {
  if (profileSessionStore.isLlmStatusLoading) {
    return "Checking LLM provider...";
  }
  if (!profileSessionStore.llmStatus) {
    return "LLM status unavailable.";
  }
  const { provider, configured, model, reason } = profileSessionStore.llmStatus;
  if (configured) {
    return `${provider}${model ? ` - ${model}` : ""}`;
  }
  return `${provider} unavailable${reason ? ` - ${reason}` : ""}`;
});

const providerStatusLabel = computed(() => {
  if (useLocalDemo.value) {
    return "Local demo provider ready";
  }
  const selected = selectedSearchSources.value.map((source) => SOURCE_LABELS[source]).join(", ") || "none";
  const status = profileSessionStore.jobSearchProviderStatus;
  if (!status) {
    return `Selected sources: ${selected}`;
  }
  if (status.provider === "browser_helper") {
    return `Selected sources: ${selected}${status.reason ? ` - ${status.reason}` : ""}`;
  }
  if (status.provider === "multi_source") {
    if (status.configured) {
      return `Selected sources: ${selected}${status.reason ? ` - ${status.reason}` : ""}`;
    }
    return `Provider unavailable${status.reason ? ` - ${status.reason}` : ""}`;
  }
  if (status.provider === "mock") {
    return "Local demo provider ready";
  }
  if (status.provider === "serper_web") {
    if (status.configured) {
      return `Web search ready${status.search_url ? ` - ${status.search_url}` : ""}`;
    }
    return `Web search unavailable${status.reason ? ` - ${status.reason}` : ""}`;
  }
  if (status.configured) {
    return `CUHKSZ Career ready${status.search_url ? ` - ${status.search_url}` : ""}`;
  }
  return `CUHKSZ Career unavailable${status.reason ? ` - ${status.reason}` : ""}`;
});

const browserHelperStatusTag = computed(() => {
  if (!browserHelperStatus.value) {
    return "Not checked";
  }
  return browserHelperStatus.value.installed ? "Detected" : "Not detected";
});

const bossLoginStatusTag = computed(() => {
  if (!bossLoginStatus.value) {
    return "Not checked";
  }
  return bossLoginStatus.value.loggedIn ? "Logged in" : "Login required";
});

const bossLoginStatusSummary = computed(() => {
  if (!bossLoginStatus.value) {
    return "Check after detecting helper";
  }
  return formatBossLoginStatusSummary(bossLoginStatus.value);
});

const canCheckBossLogin = computed(() => Boolean(browserHelperStatus.value?.installed));

const providerStatusTarget = computed<"mock" | "browser_helper" | "multi_source">(() => {
  if (useLocalDemo.value) {
    return "mock";
  }
  if (usesBrowserHelper.value && providerSearchSources.value.length === 0) {
    return "browser_helper";
  }
  return "multi_source";
});

const canStartUnifiedSearch = computed(() => {
  return Boolean(
    profileSessionStore.jobSearchPreview &&
      canStartSearch.value &&
      !profileSessionStore.isJobSearchPreviewLoading
  );
});

function buildPayload(): CreateJobSearchRunPayload {
  const selectedProviderSources = providerSearchSources.value;
  return {
    session_id: sessionId.value,
    search_mode: useLocalDemo.value ? "local_mock" : "live_search",
    search_provider: useLocalDemo.value
      ? "mock"
      : usesBrowserHelper.value && selectedProviderSources.length === 0
        ? "browser_helper"
        : "multi_source",
    selected_sources: useLocalDemo.value ? [] : selectedProviderSources,
    use_llm: useLocalDemo.value ? false : useLlm.value,
    max_results: effectiveMaxResults.value
  };
}

function saveCurrentPreviewControls(): void {
  const controls: JobSearchPreviewControls = {
    sessionId: sessionId.value,
    selectedProviderSearchSources: normalizeProviderSearchSources(selectedProviderSearchSources.value),
    isBossSourceSelected: isBossSourceSelected.value,
    useLocalDemo: useLocalDemo.value,
    useLlm: useLocalDemo.value ? false : useLlm.value,
    maxResults: maxResults.value
  };
  profileSessionStore.saveJobSearchPreviewControls(controls);
}

async function restorePreviewControls(): Promise<boolean> {
  const controls = profileSessionStore.jobSearchPreviewControls;
  if (!controls || controls.sessionId !== sessionId.value) {
    return false;
  }
  isRestoringPreviewControls.value = true;
  try {
    const legacySources = legacySelectedSearchSources(controls);
    selectedProviderSearchSources.value = normalizeProviderSearchSources(
      controls.selectedProviderSearchSources ?? legacySources
    );
    isBossSourceSelected.value = Boolean(
      controls.isBossSourceSelected || legacySources.includes("boss")
    );
    useLocalDemo.value = controls.useLocalDemo;
    useLlm.value = controls.useLocalDemo ? false : controls.useLlm;
    maxResults.value = controls.maxResults;
    await nextTick();
    return true;
  } finally {
    isRestoringPreviewControls.value = false;
  }
}

function canReuseStoredPreview(): boolean {
  const preview = profileSessionStore.jobSearchPreview;
  if (!preview || preview.session_id !== sessionId.value) {
    return false;
  }
  const payload = buildPayload();
  return (
    preview.search_mode === payload.search_mode &&
    preview.search_provider === expectedStoredPreviewProvider(payload) &&
    preview.llm_enabled === Boolean(payload.use_llm) &&
    sameProviderSearchSources(
      normalizeProviderSearchSources(preview.selected_sources ?? []),
      payload.selected_sources ?? []
    )
  );
}

function expectedStoredPreviewProvider(payload: CreateJobSearchRunPayload): string | null {
  if (payload.search_mode === "local_mock") {
    return "mock";
  }
  const selectedSources = normalizeProviderSearchSources(payload.selected_sources ?? []);
  if (selectedSources.length === 1) {
    return selectedSources[0];
  }
  if (selectedSources.length > 1) {
    return `multi_source:${selectedSources.join(",")}`;
  }
  return payload.search_provider ?? null;
}

function providerSourcesForRun(preview: JobSearchPreview | null): ProviderSearchSource[] {
  const previewSources = normalizeProviderSearchSources(preview?.selected_sources ?? []);
  const savedSources = normalizeProviderSearchSources(
    profileSessionStore.jobSearchPreviewControls?.selectedProviderSearchSources ??
      legacySelectedSearchSources(profileSessionStore.jobSearchPreviewControls)
  );
  return uniqueProviderSearchSources([
    ...providerSearchSources.value,
    ...previewSources,
    ...savedSources
  ]);
}

function normalizeProviderSearchSources(values: unknown): ProviderSearchSource[] {
  if (!Array.isArray(values)) {
    return [];
  }
  return values.filter((value): value is ProviderSearchSource =>
    PROVIDER_SEARCH_SOURCE_VALUES.has(value as ProviderSearchSource)
  );
}

function legacySelectedSearchSources(controls: unknown): string[] {
  if (!controls || typeof controls !== "object") {
    return [];
  }
  const values = (controls as { selectedSearchSources?: unknown }).selectedSearchSources;
  return Array.isArray(values) ? values.map((value) => String(value)) : [];
}

function uniqueProviderSearchSources(values: ProviderSearchSource[]): ProviderSearchSource[] {
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

function sameProviderSearchSources(left: ProviderSearchSource[], right: ProviderSearchSource[]): boolean {
  const normalizedLeft = uniqueProviderSearchSources(left);
  const normalizedRight = uniqueProviderSearchSources(right);
  return (
    normalizedLeft.length === normalizedRight.length &&
    normalizedLeft.every((value, index) => value === normalizedRight[index])
  );
}

async function refreshPreview() {
  if (!profileSessionStore.session?.confirmed_profile_id) {
    return;
  }
  saveCurrentPreviewControls();
  await profileSessionStore.previewJobSearch(buildPayload());
}

onMounted(async () => {
  try {
    const restoredPreviewControls = await restorePreviewControls();
    const session = await profileSessionStore.loadSession(sessionId.value);
    if (session.confirmed_profile_id) {
      await profileSessionStore.loadConfirmedProfile(session.confirmed_profile_id);
    }
    await profileSessionStore.loadJobSearchRuns(sessionId.value);
    await profileSessionStore.loadLlmStatus(useLlm.value);
    await profileSessionStore.loadJobSearchProviderStatus(providerStatusTarget.value);
    if (!restoredPreviewControls || !canReuseStoredPreview()) {
      await refreshPreview();
    }
  } catch {
    // Error state is rendered from the store.
  }
});

onUnmounted(() => {
  stopBossLoginAutoRefresh();
});

watch(selectedSearchSources, async () => {
  if (isRestoringPreviewControls.value) {
    return;
  }
  saveCurrentPreviewControls();
  if (!usesBrowserHelper.value) {
    browserHelperMessage.value = null;
  }
  try {
    await profileSessionStore.loadJobSearchProviderStatus(providerStatusTarget.value);
    await refreshPreview();
  } catch {
    // Error state is rendered from the store.
  }
}, { deep: true });

watch(useLocalDemo, async (value) => {
  if (isRestoringPreviewControls.value) {
    return;
  }
  if (value) {
    useLlm.value = false;
  }
  saveCurrentPreviewControls();
  try {
    await profileSessionStore.loadJobSearchProviderStatus(providerStatusTarget.value);
    await refreshPreview();
  } catch {
    // Error state is rendered from the store.
  }
});

watch(useLlm, async (value) => {
  if (isRestoringPreviewControls.value) {
    return;
  }
  saveCurrentPreviewControls();
  try {
    await profileSessionStore.loadLlmStatus(value);
    await refreshPreview();
  } catch {
    // Error state is rendered from the store.
  }
});

watch(maxResults, async () => {
  if (isRestoringPreviewControls.value) {
    return;
  }
  saveCurrentPreviewControls();
  try {
    await refreshPreview();
  } catch {
    // Error state is rendered from the store.
  }
});

function goBackToConfirmed() {
  void router.push({ name: "profile-confirmed", params: { sessionId: sessionId.value } });
}

async function startJobSearch() {
  saveCurrentPreviewControls();
  profileSessionStore.prepareNewJobSearch();
  if (usesBrowserHelper.value) {
    await startBrowserHelperJobSearch();
    return;
  }
  try {
    const run = await profileSessionStore.createJobSearch(buildPayload());
    await router.push({ name: "job-search", params: { runId: run.job_search_run_id } });
  } catch {
    // Error state is rendered from the store.
  }
}

async function checkBrowserHelper() {
  isBrowserHelperChecking.value = true;
  browserHelperMessage.value = null;
  try {
    browserHelperStatus.value = await pingBrowserHelper();
    browserHelperMessage.value = browserHelperStatus.value.error;
    if (browserHelperStatus.value.installed) {
      await checkBossLogin();
    } else {
      bossLoginStatus.value = null;
    }
  } finally {
    isBrowserHelperChecking.value = false;
  }
}

async function checkBossLogin() {
  if (!browserHelperStatus.value?.installed) {
    browserHelperMessage.value = "Install and detect the Browser Helper first.";
    return;
  }
  isBossLoginChecking.value = true;
  browserHelperMessage.value = null;
  try {
    bossLoginStatus.value = await checkBossLoginStatus();
    browserHelperMessage.value = formatBossLoginStatusMessage(bossLoginStatus.value);
    if (bossLoginStatus.value.loggedIn) {
      stopBossLoginAutoRefresh();
    }
  } catch (error) {
    browserHelperMessage.value = error instanceof Error ? error.message : "BOSS login status check failed.";
  } finally {
    isBossLoginChecking.value = false;
  }
}

async function openBossLogin() {
  if (!browserHelperStatus.value?.installed) {
    browserHelperMessage.value = "Install and detect the Browser Helper first.";
    return;
  }
  try {
    await openBossLoginPage();
    bossLoginStatus.value = null;
    browserHelperMessage.value = "BOSS login page opened. Login status will refresh automatically.";
    startBossLoginAutoRefresh();
  } catch (error) {
    browserHelperMessage.value = error instanceof Error ? error.message : "Failed to open BOSS login page.";
  }
}

async function startBrowserHelperJobSearch() {
  if (!profileSessionStore.jobSearchPreview) {
    return;
  }
  const selectedProviderSources = providerSourcesForRun(profileSessionStore.jobSearchPreview);
  isBossSearching.value = true;
  browserHelperMessage.value = null;
  try {
    if (!browserHelperStatus.value?.installed) {
      await checkBrowserHelper();
    }
    if (!browserHelperStatus.value?.installed) {
      browserHelperMessage.value = "Install and detect the Browser Helper before starting BOSS search.";
      return;
    }
    await checkBossLogin();
    if (!bossLoginStatus.value?.loggedIn) {
      browserHelperMessage.value = "BOSS login is required before starting this search.";
      return;
    }

    const preview = profileSessionStore.jobSearchPreview;
    const bossQueries = buildBossSearchQueries(preview);
    const result = await fetchBossCandidates(
      preview.query,
      preview.locations[0] ?? null,
      effectiveMaxResults.value,
      bossQueries,
      BOSS_DEFAULT_JOB_TYPE
    );
    if (!result.candidates.length) {
      browserHelperMessage.value = formatBossEmptyResultMessage(result);
      if (!selectedProviderSources.length) {
        return;
      }
    }
    const run = await profileSessionStore.createBrowserHelperJobSearch({
      session_id: sessionId.value,
      query: preview.query,
      helper_version: result.version,
      platforms: ["boss"],
      selected_sources: selectedProviderSources,
      use_llm: useLlm.value,
      locations: preview.locations,
      target_roles: preview.target_roles,
      keywords: preview.keywords,
      max_results: effectiveMaxResults.value,
      candidates: result.candidates
    });
    await router.push({ name: "job-search", params: { runId: run.job_search_run_id } });
  } catch (error) {
    browserHelperMessage.value = error instanceof Error ? error.message : "BOSS helper search failed.";
  } finally {
    isBossSearching.value = false;
  }
}

function startBossLoginAutoRefresh(): void {
  stopBossLoginAutoRefresh();
  let attempts = 0;
  const poll = async () => {
    attempts += 1;
    if (!usesBrowserHelper.value || !browserHelperStatus.value?.installed) {
      stopBossLoginAutoRefresh();
      return;
    }
    await checkBossLogin();
    if (bossLoginStatus.value?.loggedIn || attempts >= 24) {
      if (!bossLoginStatus.value?.loggedIn && attempts >= 24) {
        browserHelperMessage.value = "BOSS login was not verified after automatic refresh. Use Check BOSS Login after completing login or verification.";
      }
      stopBossLoginAutoRefresh();
      return;
    }
    bossLoginRefreshTimer = window.setTimeout(() => {
      void poll();
    }, 5000);
  };
  bossLoginRefreshTimer = window.setTimeout(() => {
    void poll();
  }, 3000);
}

function stopBossLoginAutoRefresh(): void {
  if (bossLoginRefreshTimer !== null) {
    window.clearTimeout(bossLoginRefreshTimer);
    bossLoginRefreshTimer = null;
  }
}

function formatBossLoginStatusMessage(status: BossLoginStatus): string {
  if (status.loggedIn) {
    return "BOSS login verified by a live page probe.";
  }
  if (status.cookieLoggedIn) {
    return `BOSS cookies exist but the live session is not usable: ${status.verificationReason ?? status.verificationStatus}.`;
  }
  return status.verificationReason ?? "BOSS login is required before helper search.";
}

function formatBossLoginStatusSummary(status: BossLoginStatus): string {
  const cookieSummary = `${status.cookieCount} cookies, ${status.matchedAuthCookies.length} auth-like`;
  const probeSummary = `${status.probeJobCardCount} cards, ${status.probeValidJobDetailLinkCount} valid links`;
  if (status.loggedIn) {
    return `Verified session - ${cookieSummary}; probe ${probeSummary}`;
  }
  if (status.cookieLoggedIn) {
    return `Cookies present but not verified - ${status.verificationStatus}; probe ${probeSummary}`;
  }
  return `Not logged in - ${cookieSummary}; ${status.verificationStatus}`;
}

function buildBossSearchQueries(preview: JobSearchPreview): string[] {
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

function toBossSearchQueries(value: string): string[] {
  const query = cleanBossQuery(value);
  if (!query) {
    return [];
  }
  if (containsCjk(query)) {
    return [query];
  }
  const rewritten = BOSS_ENGLISH_QUERY_REWRITES.flatMap((rule) =>
    rule.pattern.test(query) ? rule.queries : []
  );
  if (rewritten.length) {
    return rewritten;
  }
  return [];
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

function formatBossEmptyResultMessage(result: Awaited<ReturnType<typeof fetchBossCandidates>>): string {
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

function seeResult() {
  if (!latestResultRun.value) {
    return;
  }
  void router.push({ name: "job-search", params: { runId: latestResultRun.value.job_search_run_id } });
}
</script>

<template>
  <section class="flow-page">
    <FlowPageHeader
      title="Search Preview"
      description="Confirm retrieval sources, query scope, and analysis mode before creating a job search run."
      :meta="`Session ${sessionId}`"
      :active-step="4"
    />

    <div v-if="profileSessionStore.error" class="error-banner">
      {{ profileSessionStore.error }}
    </div>

    <div class="confirmed-layout">
      <div class="workspace-panel">
        <div class="panel-heading">
          <div>
            <h2>Search controls</h2>
            <p>{{ selectedSourceLabel }}</p>
          </div>
          <n-tag :type="previewStatusTagType" round>{{ previewStatusLabel }}</n-tag>
        </div>

        <div class="flow-toolbar">
          <n-button secondary @click="goBackToConfirmed">Back to Confirmed Profile</n-button>
          <div class="flow-toolbar-secondary">
            <n-button
              secondary
              :loading="profileSessionStore.isJobSearchPreviewLoading"
              :disabled="!canStartSearch"
              @click="refreshPreview"
            >
              Refresh Preview
            </n-button>
            <n-button
              secondary
              :disabled="!canSeeResult || profileSessionStore.isJobSearchCreating || isBossSearching"
              @click="seeResult"
            >
              See Result
            </n-button>
            <n-button
              type="primary"
              :disabled="!canStartUnifiedSearch"
              :loading="profileSessionStore.isJobSearchCreating || isBossSearching"
              @click="startJobSearch"
            >
              Start Job Search
            </n-button>
          </div>
        </div>
      </div>

      <n-card title="Search Setup" size="small" class="job-search-setup-card">
        <div class="job-search-setup">
          <div class="job-search-setup-row">
            <span class="job-search-setup-label">Recruiting Websites</span>
            <n-checkbox-group v-model:value="selectedProviderSearchSources" :disabled="useLocalDemo">
              <n-checkbox value="cuhksz_career">CUHKSZ Career</n-checkbox>
              <n-checkbox value="linkedin">LinkedIn</n-checkbox>
              <n-checkbox value="remoteok">RemoteOK</n-checkbox>
            </n-checkbox-group>
            <n-checkbox v-model:checked="isBossSourceSelected" :disabled="useLocalDemo">
              BOSS
            </n-checkbox>
          </div>

          <div class="job-search-setup-row">
            <span class="job-search-setup-label">Use Local Demo</span>
            <n-switch v-model:value="useLocalDemo" />
          </div>

          <div class="job-search-setup-row">
            <span class="job-search-setup-label">Use DeepSeek API for analysis</span>
            <n-switch v-model:value="useLlm" :disabled="useLocalDemo" />
          </div>

          <div class="job-search-setup-row">
            <span class="job-search-setup-label">Result Limit</span>
            <n-input-number
              v-model:value="maxResults"
              :min="1"
              :max="50"
              :step="1"
              size="small"
            />
          </div>

          <div class="job-search-setup-row">
            <span class="job-search-setup-label">Provider Status</span>
            <div class="job-search-status-copy">
              <n-tag
                :type="profileSessionStore.jobSearchProviderStatus?.configured ? 'success' : 'warning'"
                round
              >
                {{ profileSessionStore.jobSearchProviderStatus?.configured ? "Configured" : "Fallback Ready" }}
              </n-tag>
              <span>{{ providerStatusLabel }}</span>
            </div>
          </div>

          <div class="job-search-setup-row">
            <span class="job-search-setup-label">LLM Status</span>
            <div class="job-search-status-copy">
              <n-tag
                :type="profileSessionStore.llmStatus?.configured ? 'success' : 'warning'"
                round
              >
                {{ profileSessionStore.llmStatus?.configured ? "Configured" : "Fallback Ready" }}
              </n-tag>
              <span>{{ selectedLlmProvider }} / {{ llmStatusLabel }}</span>
            </div>
          </div>

          <div v-if="usesBrowserHelper" class="job-search-setup-row">
            <span class="job-search-setup-label">Helper Status</span>
            <div class="job-search-status-copy">
              <n-tag
                :type="browserHelperStatus?.installed ? 'success' : 'warning'"
                round
              >
                {{ browserHelperStatusTag }}
              </n-tag>
              <span>
                {{ browserHelperStatus?.version ? `v${browserHelperStatus.version}` : "Chrome/Edge only" }}
              </span>
            </div>
          </div>
          <div v-if="usesBrowserHelper" class="job-search-setup-row">
            <span class="job-search-setup-label">BOSS Login</span>
            <div class="job-search-status-copy">
              <n-tag
                :type="bossLoginStatus?.loggedIn ? 'success' : 'warning'"
                round
              >
                {{ bossLoginStatusTag }}
              </n-tag>
              <span>
                {{ bossLoginStatusSummary }}
              </span>
            </div>
          </div>
          <div v-if="usesBrowserHelper" class="flow-toolbar compact">
            <n-button
              secondary
              :loading="isBrowserHelperChecking"
              @click="checkBrowserHelper"
            >
              Check Helper
            </n-button>
            <n-button
              secondary
              :disabled="!canCheckBossLogin"
              :loading="isBossLoginChecking"
              @click="checkBossLogin"
            >
              Check BOSS Login
            </n-button>
            <n-button
              secondary
              :disabled="!canCheckBossLogin"
              @click="openBossLogin"
            >
              Open BOSS Login
            </n-button>
          </div>
          <p v-if="usesBrowserHelper && browserHelperMessage" class="flow-meta">{{ browserHelperMessage }}</p>
        </div>
      </n-card>

      <div
        v-if="profileSessionStore.isJobSearchPreviewLoading && !profileSessionStore.jobSearchPreview"
        class="review-empty-state"
      >
        <p class="flow-message">Loading search preview...</p>
      </div>

      <template v-else-if="profileSessionStore.jobSearchPreview">
        <div class="metric-grid">
          <div class="metric-card">
            <span>Provider requests</span>
            <strong>{{ profileSessionStore.jobSearchPreview.estimated_provider_requests }}</strong>
          </div>
          <div class="metric-card">
            <span>Candidate cap</span>
            <strong>{{ profileSessionStore.jobSearchPreview.estimated_candidate_pool_size }}</strong>
          </div>
          <div class="metric-card">
            <span>LLM requests</span>
            <strong>{{ profileSessionStore.jobSearchPreview.estimated_total_llm_requests }}</strong>
          </div>
          <div class="metric-card">
            <span>Sources</span>
            <strong>{{ useLocalDemo ? 1 : selectedSearchSources.length }}</strong>
          </div>
        </div>

        <n-card title="Provider Queries" size="small" class="job-search-summary">
          <div class="job-status-row">
            <n-tag round>{{ profileSessionStore.jobSearchPreview.planning_mode }}</n-tag>
            <n-tag round>{{ profileSessionStore.jobSearchPreview.search_source_kind }}</n-tag>
            <span>
              Query: {{ profileSessionStore.jobSearchPreview.query }}
            </span>
          </div>
          <p>
            <strong>Selected Sources:</strong>
            {{ selectedSourceLabel }}
          </p>
          <p v-if="isBossSelected">
            <strong>Backend Sources:</strong>
            {{ backendProviderSourceLabel }}
          </p>
          <p v-if="isBossSelected && bossSearchQueriesForPreview.length">
            <strong>BOSS Queries:</strong>
            {{ bossSearchQueriesForPreview.join(", ") }}
          </p>
          <ul class="review-list">
            <li
              v-for="query in profileSessionStore.jobSearchPreview.provider_queries"
              :key="query"
            >
              {{ query }}
            </li>
          </ul>
          <p v-if="profileSessionStore.jobSearchPreview.fallback_reason">
            <strong>Fallback:</strong> {{ profileSessionStore.jobSearchPreview.fallback_reason }}
          </p>
          <p v-if="profileSessionStore.jobSearchPreview.quality_warnings.length">
            <strong>Warnings:</strong>
            {{ profileSessionStore.jobSearchPreview.quality_warnings.join(" - ") }}
          </p>
        </n-card>

        <n-card title="Recall And Ranking Plan" size="small" class="job-search-summary">
          <div class="confirmed-grid">
            <div>
              <strong>Recall Queries</strong>
              <ul class="review-list">
                <li
                  v-for="query in profileSessionStore.jobSearchPreview.recall_queries"
                  :key="query"
                >
                  {{ query }}
                </li>
              </ul>
            </div>
            <div>
              <strong>Ranking Signals</strong>
              <div class="job-chip-row">
                <n-tag
                  v-for="signal in profileSessionStore.jobSearchPreview.ranking_signals"
                  :key="signal"
                  size="small"
                  round
                >
                  {{ signal }}
                </n-tag>
              </div>
            </div>
          </div>
          <ul
            v-if="profileSessionStore.jobSearchPreview.search_source_notes.length"
            class="review-list"
          >
            <li
              v-for="note in profileSessionStore.jobSearchPreview.search_source_notes"
              :key="note"
            >
              {{ note }}
            </li>
          </ul>
        </n-card>

        <n-card
          v-if="profileSessionStore.jobSearchPreview.search_intent"
          title="Search Intent"
          size="small"
          class="job-search-summary"
        >
          <div class="confirmed-grid">
            <div>
              <strong>Role Titles</strong>
              <div class="job-chip-row">
                <n-tag
                  v-for="item in profileSessionStore.jobSearchPreview.search_intent.role_titles"
                  :key="item"
                  size="small"
                  round
                >
                  {{ item }}
                </n-tag>
              </div>
            </div>
            <div>
              <strong>Role Families</strong>
              <div class="job-chip-row">
                <n-tag
                  v-for="item in profileSessionStore.jobSearchPreview.search_intent.role_families"
                  :key="item"
                  size="small"
                  round
                >
                  {{ item }}
                </n-tag>
              </div>
            </div>
            <div>
              <strong>Industry Domains</strong>
              <div class="job-chip-row">
                <n-tag
                  v-for="item in profileSessionStore.jobSearchPreview.search_intent.industry_domains"
                  :key="item"
                  size="small"
                  round
                >
                  {{ item }}
                </n-tag>
              </div>
            </div>
            <div>
              <strong>Evidence Skills</strong>
              <div class="job-chip-row">
                <n-tag
                  v-for="item in profileSessionStore.jobSearchPreview.search_intent.evidence_skills"
                  :key="item"
                  size="small"
                  round
                >
                  {{ item }}
                </n-tag>
              </div>
            </div>
            <div>
              <strong>Generic Tools</strong>
              <div class="job-chip-row">
                <n-tag
                  v-for="item in profileSessionStore.jobSearchPreview.search_intent.generic_tools"
                  :key="item"
                  size="small"
                  round
                >
                  {{ item }}
                </n-tag>
              </div>
            </div>
            <div>
              <strong>Constraints</strong>
              <p>{{ profileSessionStore.jobSearchPreview.search_intent.constraints.join(", ") || "None" }}</p>
            </div>
          </div>
        </n-card>

        <n-card title="Query Budget" size="small" class="job-search-summary">
          <div class="confirmed-grid">
            <div>
              <strong>Provider query groups</strong>
              <p>{{ profileSessionStore.jobSearchPreview.provider_query_count }}</p>
            </div>
            <div>
              <strong>Estimated provider requests</strong>
              <p>{{ profileSessionStore.jobSearchPreview.estimated_provider_requests }}</p>
            </div>
            <div>
              <strong>Candidate pool cap</strong>
              <p>{{ profileSessionStore.jobSearchPreview.estimated_candidate_pool_size }}</p>
            </div>
            <div>
              <strong>Estimated LLM requests</strong>
              <p>{{ profileSessionStore.jobSearchPreview.estimated_total_llm_requests }}</p>
            </div>
          </div>
          <p class="flow-meta">
            Planning {{ profileSessionStore.jobSearchPreview.estimated_llm_planning_requests }},
            filtering {{ profileSessionStore.jobSearchPreview.estimated_llm_filtering_requests }},
            JD analysis {{ profileSessionStore.jobSearchPreview.estimated_llm_analysis_requests }}
          </p>
          <ul
            v-if="profileSessionStore.jobSearchPreview.query_strategy_notes.length"
            class="review-list"
          >
            <li
              v-for="note in profileSessionStore.jobSearchPreview.query_strategy_notes"
              :key="note"
            >
              {{ note }}
            </li>
          </ul>
        </n-card>

        <div class="confirmed-grid">
          <n-card title="Provider Search Terms" size="small">
            <div class="job-chip-row">
              <n-tag
                v-for="term in profileSessionStore.jobSearchPreview.provider_search_terms"
                :key="term"
                size="small"
                round
              >
                {{ term }}
              </n-tag>
              <span
                v-if="!profileSessionStore.jobSearchPreview.provider_search_terms.length"
                class="flow-meta"
              >
                Not used for this provider.
              </span>
            </div>
          </n-card>

          <n-card title="Provider Search URLs" size="small">
            <ul class="review-list">
              <li
                v-for="url in profileSessionStore.jobSearchPreview.provider_search_urls"
                :key="url"
              >
                <a :href="url" target="_blank" rel="noreferrer">{{ url }}</a>
              </li>
            </ul>
            <p
              v-if="!profileSessionStore.jobSearchPreview.provider_search_urls.length"
              class="flow-meta"
            >
              Not used for this provider.
            </p>
          </n-card>

          <n-card title="Target Roles" size="small">
            <ul class="review-list">
              <li
                v-for="role in profileSessionStore.jobSearchPreview.target_roles"
                :key="role"
              >
                {{ role }}
              </li>
            </ul>
          </n-card>

          <n-card title="Search Signal Terms" size="small">
            <div class="job-chip-row">
              <n-tag
                v-for="term in profileSessionStore.jobSearchPreview.search_signal_terms"
                :key="term"
                size="small"
                round
              >
                {{ term }}
              </n-tag>
            </div>
          </n-card>

          <n-card title="Locations" size="small">
            <p>
              {{ profileSessionStore.jobSearchPreview.locations.join(", ") || "Not set" }}
            </p>
          </n-card>

          <n-card title="Excluded Signals" size="small">
            <p>
              {{ profileSessionStore.jobSearchPreview.excluded_signals.join(", ") || "None" }}
            </p>
          </n-card>
        </div>
      </template>
    </div>
  </section>
</template>
