<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NCard,
  NCheckbox,
  NCheckboxGroup,
  NInputNumber,
  NSelect,
  NSwitch,
  NTag
} from "naive-ui";

import FlowPageHeader from "../components/FlowPageHeader.vue";
import { fetchBossCandidates } from "../services/browserHelper";
import {
  BOSS_DEFAULT_JOB_TYPE,
  buildBossSearchQueries,
  formatBossEmptyResultMessage
} from "../services/bossSearchPlanning";
import { formatSearchSources } from "../services/jobSearchSources";
import { useProfileSessionStore } from "../stores/profileSession";
import type { JobSearchRun } from "../types/profileSession";
import { useBrowserHelperSession } from "../composables/useBrowserHelperSession";
import { useSearchPreviewControls } from "../composables/useSearchPreviewControls";

const route = useRoute();
const router = useRouter();
const profileSessionStore = useProfileSessionStore();
const sessionId = computed(() => String(route.params.sessionId ?? ""));
const {
  selectedProviderSearchSources,
  isBossSourceSelected,
  useLocalDemo,
  useLlmAnalysis,
  selectedLlmProvider,
  maxResults,
  isRestoringPreviewControls,
  selectedSearchSources,
  providerSearchSources,
  canStartSearch,
  effectiveMaxResults,
  effectiveAnalysisMode,
  effectiveLlmProvider,
  buildPayload,
  saveCurrentPreviewControls,
  restorePreviewControls,
  canReuseStoredPreview,
  providerSourcesForRun
} = useSearchPreviewControls(sessionId);
const isBossSearching = ref(false);
const nowMs = ref(Date.now());
let searchElapsedTimer: number | null = null;
const llmProviderOptions = [
  { label: "DeepSeek", value: "deepseek" },
  { label: "Ollama", value: "ollama" }
];
const isBossSelected = computed(() => isBossSourceSelected.value);
const bossSearchQueriesForPreview = computed(() => {
  return profileSessionStore.jobSearchPreview
    ? buildBossSearchQueries(profileSessionStore.jobSearchPreview)
    : [];
});
const usesBrowserHelper = computed(() => isBossSelected.value && !useLocalDemo.value);
const {
  browserHelperStatus,
  bossLoginStatus,
  isBrowserHelperChecking,
  isBossLoginChecking,
  browserHelperMessage,
  browserHelperStatusTag,
  bossLoginStatusTag,
  bossLoginStatusSummary,
  canCheckBossLogin,
  checkBrowserHelper,
  checkBossLogin,
  openBossLogin
} = useBrowserHelperSession(usesBrowserHelper);
const selectedSourceLabel = computed(() => {
  if (useLocalDemo.value) {
    return "Local demo";
  }
  return formatSearchSources(selectedSearchSources.value, "No source selected");
});
const backendProviderSourcesForRun = computed(() => {
  return providerSourcesForRun(profileSessionStore.jobSearchPreview);
});
const backendProviderSourceLabel = computed(() => {
  return formatSearchSources(backendProviderSourcesForRun.value, "BOSS only");
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
  if (effectiveAnalysisMode.value === "deterministic") {
    return "LLM analysis disabled.";
  }
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
  const selected = formatSearchSources(selectedSearchSources.value, "none");
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

const activeSearchElapsedLabel = computed(() => {
  if (
    !isBossSearching.value &&
    !profileSessionStore.isJobSearchCreating
  ) {
    return null;
  }
  const startedAt = profileSessionStore.jobSearchClientStartedAt;
  if (startedAt === null) {
    return null;
  }
  return formatDuration(nowMs.value - startedAt);
});

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

async function refreshPreview() {
  if (!profileSessionStore.session?.confirmed_profile_id) {
    return;
  }
  saveCurrentPreviewControls();
  await profileSessionStore.previewJobSearch(buildPayload());
}

onMounted(async () => {
  startSearchElapsedTicker();
  try {
    const restoredPreviewControls = await restorePreviewControls();
    const session = await profileSessionStore.loadSession(sessionId.value);
    if (session.confirmed_profile_id) {
      await profileSessionStore.loadConfirmedProfile(session.confirmed_profile_id);
    }
    await profileSessionStore.loadJobSearchRuns(sessionId.value);
    await profileSessionStore.loadLlmStatus(selectedLlmProvider.value);
    await profileSessionStore.loadJobSearchProviderStatus(providerStatusTarget.value);
    if (!restoredPreviewControls || !canReuseStoredPreview()) {
      await refreshPreview();
    }
  } catch {
    // Error state is rendered from the store.
  }
});

onUnmounted(() => {
  stopSearchElapsedTicker();
});

watch(selectedSearchSources, async () => {
  if (isRestoringPreviewControls.value) {
    return;
  }
  if (!usesBrowserHelper.value) {
    browserHelperMessage.value = null;
  }
  await refreshPreviewFromControls({ loadProviderStatus: true });
}, { deep: true });

watch(useLocalDemo, async (value) => {
  if (isRestoringPreviewControls.value) {
    return;
  }
  if (value) {
    useLlmAnalysis.value = false;
  }
  await refreshPreviewFromControls({ loadProviderStatus: true });
});

watch([useLlmAnalysis, selectedLlmProvider], async () => {
  if (isRestoringPreviewControls.value) {
    return;
  }
  await refreshPreviewFromControls({ loadLlmStatus: true });
});

watch(maxResults, async () => {
  if (isRestoringPreviewControls.value) {
    return;
  }
  await refreshPreviewFromControls();
});

async function refreshPreviewFromControls(
  options: { loadProviderStatus?: boolean; loadLlmStatus?: boolean } = {}
): Promise<void> {
  saveCurrentPreviewControls();
  try {
    if (options.loadProviderStatus) {
      await profileSessionStore.loadJobSearchProviderStatus(providerStatusTarget.value);
    }
    if (options.loadLlmStatus) {
      await profileSessionStore.loadLlmStatus(selectedLlmProvider.value);
    }
    await refreshPreview();
  } catch {
    // Error state is rendered from the store.
  }
}

function goBackToConfirmed() {
  void router.push({ name: "search-mission", params: { sessionId: sessionId.value } });
}

async function startJobSearch() {
  saveCurrentPreviewControls();
  profileSessionStore.beginJobSearchClientTiming();
  profileSessionStore.prepareNewJobSearch();
  if (usesBrowserHelper.value) {
    await startBrowserHelperJobSearch();
    return;
  }
  try {
    const run = await measureSearchStage("Backend start", () =>
      profileSessionStore.createJobSearch(buildPayload())
    );
    await router.push({ name: "job-search", params: { runId: run.job_search_run_id } });
  } catch {
    profileSessionStore.clearJobSearchClientTiming();
    // Error state is rendered from the store.
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
      await measureSearchStage("Helper check", checkBrowserHelper);
    }
    if (!browserHelperStatus.value?.installed) {
      browserHelperMessage.value = "Install and detect the Browser Helper before starting BOSS search.";
      profileSessionStore.clearJobSearchClientTiming();
      return;
    }
    await measureSearchStage("BOSS login check", checkBossLogin);
    if (!bossLoginStatus.value?.loggedIn) {
      browserHelperMessage.value = "BOSS login is required before starting this search.";
      profileSessionStore.clearJobSearchClientTiming();
      return;
    }

    const preview = profileSessionStore.jobSearchPreview;
    const bossQueries = buildBossSearchQueries(preview);
    const result = await measureSearchStage(
      "BOSS capture",
      () => fetchBossCandidates(
        preview.query,
        preview.locations[0] ?? null,
        effectiveMaxResults.value,
        bossQueries,
        BOSS_DEFAULT_JOB_TYPE
      )
    );
    if (!result.candidates.length) {
      browserHelperMessage.value = formatBossEmptyResultMessage(result);
      if (!selectedProviderSources.length) {
        profileSessionStore.clearJobSearchClientTiming();
        return;
      }
    }
    const run = await measureSearchStage("Backend import", () =>
      profileSessionStore.createBrowserHelperJobSearch({
        session_id: sessionId.value,
        query: preview.query,
        helper_version: result.version,
        platforms: ["boss"],
        selected_sources: selectedProviderSources,
        analysis_mode: effectiveAnalysisMode.value,
        llm_provider: effectiveLlmProvider.value,
        use_llm: effectiveLlmProvider.value === "deepseek",
        locations: preview.locations,
        target_roles: preview.target_roles,
        keywords: preview.keywords,
        max_results: effectiveMaxResults.value,
        candidates: result.candidates
      })
    );
    await router.push({ name: "job-search", params: { runId: run.job_search_run_id } });
  } catch (error) {
    browserHelperMessage.value = error instanceof Error ? error.message : "BOSS helper search failed.";
    profileSessionStore.clearJobSearchClientTiming();
  } finally {
    isBossSearching.value = false;
  }
}

async function measureSearchStage<T>(label: string, action: () => Promise<T>): Promise<T> {
  const startedAt = Date.now();
  try {
    return await action();
  } finally {
    profileSessionStore.addJobSearchClientStage({
      label,
      duration_ms: Date.now() - startedAt
    });
  }
}

function startSearchElapsedTicker(): void {
  stopSearchElapsedTicker();
  searchElapsedTimer = window.setInterval(() => {
    nowMs.value = Date.now();
  }, 1000);
}

function stopSearchElapsedTicker(): void {
  if (searchElapsedTimer !== null) {
    window.clearInterval(searchElapsedTimer);
    searchElapsedTimer = null;
  }
}

function formatDuration(milliseconds: number): string {
  const totalSeconds = Math.max(0, Math.round(milliseconds / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
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
      :active-step="1"
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
            <span class="job-search-setup-label">LLM Analysis</span>
            <n-switch v-model:value="useLlmAnalysis" :disabled="useLocalDemo" />
          </div>

          <div class="job-search-setup-row">
            <span class="job-search-setup-label">LLM Provider</span>
            <n-select
              v-model:value="selectedLlmProvider"
              :options="llmProviderOptions"
              :disabled="useLocalDemo || !useLlmAnalysis"
              size="small"
              class="job-search-provider-select"
            />
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
              <span>{{ effectiveAnalysisMode === "llm" ? selectedLlmProvider : "deterministic" }} / {{ llmStatusLabel }}</span>
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
          <p v-if="activeSearchElapsedLabel" class="flow-meta">
            Search elapsed: {{ activeSearchElapsedLabel }}
          </p>
          <div
            v-if="profileSessionStore.jobSearchClientStages.length"
            class="job-chip-row"
          >
            <n-tag
              v-for="stage in profileSessionStore.jobSearchClientStages"
              :key="`${stage.label}-${stage.duration_ms}`"
              size="small"
              round
            >
              {{ stage.label }} {{ formatDuration(stage.duration_ms) }}
            </n-tag>
          </div>
          <p v-if="usesBrowserHelper && browserHelperMessage" class="flow-meta">{{ browserHelperMessage }}</p>
        </div>
      </n-card>

      <n-card
        v-if="profileSessionStore.jobSearchPreview?.search_mission_id"
        title="Confirmed Search Mission"
        size="small"
        class="job-search-summary"
      >
        <div class="job-chip-row">
          <n-tag type="success" round>
            Revision {{ profileSessionStore.jobSearchPreview.search_mission_revision }}
          </n-tag>
          <n-tag
            v-for="role in profileSessionStore.jobSearchPreview.target_roles"
            :key="role"
            size="small"
            round
          >{{ role }}</n-tag>
        </div>
        <p>
          <strong>Hard Constraints:</strong>
          {{ profileSessionStore.jobSearchPreview.mission_constraints.join(", ") || "None" }}
        </p>
        <p>
          <strong>Excluded Roles:</strong>
          {{ profileSessionStore.jobSearchPreview.mission_excluded_roles.join(", ") || "None" }}
        </p>
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
