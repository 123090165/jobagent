<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NInput, NSelect, NTag } from "naive-ui";

import FlowPageHeader from "../components/FlowPageHeader.vue";
import {
  listJobSearchResultFeedback,
  saveJobSearchResultFeedback
} from "../api/profileSessions";
import {
  formatProviderName,
  formatSourceName,
  normalizeSourceKey,
  sourcesFromProviderName,
  uniqueSourceKeys
} from "../services/jobSearchSources";
import { useProfileSessionStore } from "../stores/profileSession";
import { useSavedJobsStore } from "../stores/savedJobs";
import type {
  JobSearchFeedbackType,
  JobSearchResult,
  JobSearchResultFeedback,
  JobSearchTraceStep
} from "../types/profileSession";

const route = useRoute();
const router = useRouter();
const profileSessionStore = useProfileSessionStore();
const savedJobsStore = useSavedJobsStore();
const runId = computed(() => String(route.params.runId ?? ""));
const jobBriefHint = ref<string | null>(null);
const savedJobMessage = ref<string | null>(null);
const savingResultIds = ref<string[]>([]);
const locallySavedResultIds = ref<string[]>([]);
const resultFeedback = ref<Record<string, JobSearchResultFeedback>>({});
const feedbackTypes = ref<Record<string, JobSearchFeedbackType | null>>({});
const feedbackNotes = ref<Record<string, string>>({});
const savingFeedbackIds = ref<string[]>([]);
const feedbackMessage = ref<string | null>(null);
const nowMs = ref(Date.now());
let elapsedTimer: number | null = null;
const feedbackOptions: Array<{ label: string; value: JobSearchFeedbackType }> = [
  { label: "Relevant", value: "relevant" },
  { label: "Not relevant", value: "irrelevant" },
  { label: "Duplicate", value: "duplicate" },
  { label: "Listing expired", value: "stale" },
  { label: "JD insufficient", value: "insufficient_jd" }
];

const isRunning = computed(() =>
  ["pending", "running"].includes(profileSessionStore.jobSearchRun?.status ?? "")
);
const completedTraceCount = computed(
  () => profileSessionStore.jobSearchSteps.filter((step) => step.status === "completed").length
);
const resultCount = computed(() => profileSessionStore.jobSearchRun?.results.length ?? 0);
const runStatusLabel = computed(() => {
  const status = profileSessionStore.jobSearchRun?.status;
  if (!status) {
    return "Loading run";
  }
  if (status === "completed") {
    return "Results ready";
  }
  if (status === "failed") {
    return "Run failed";
  }
  return "Search running";
});
const runSelectedSources = computed(() => {
  const run = profileSessionStore.jobSearchRun;
  if (!run) {
    return [];
  }
  const selected = [
    ...sourcesFromProviderName(run.search_provider),
    ...(run.selected_sources ?? [])
  ];
  if (run.search_mode === "local_mock" && selected.length === 0) {
    selected.push("mock");
  }
  return uniqueSourceKeys(selected);
});
const runProviderLabel = computed(() => {
  const run = profileSessionStore.jobSearchRun;
  if (!run) {
    return "Not set";
  }
  if (runSelectedSources.value.length) {
    return runSelectedSources.value.map(formatSourceName).join(" + ");
  }
  return formatProviderName(run.search_provider);
});
const selectedSourceSummary = computed(() => {
  return runSelectedSources.value.map(formatSourceName).join(", ") || "Not set";
});
const resultSourceCounts = computed(() => {
  const counts = new Map<string, number>();
  for (const result of profileSessionStore.jobSearchRun?.results ?? []) {
    const key = normalizeSourceKey(result.source_provider || result.source);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()].map(([source, count]) => ({
    source,
    label: formatSourceName(source),
    count
  }));
});
const resultSourceSummary = computed(() => {
  return resultSourceCounts.value.map((item) => `${item.label} ${item.count}`).join(", ") || "No results yet";
});
const llmProviderFromTrace = computed(() => {
  const planningStep = profileSessionStore.jobSearchSteps.find((step) => step.name === "Search planning");
  const provider = planningStep?.details.llm_provider;
  return typeof provider === "string" && provider.length > 0 ? provider : null;
});
const llmAnalysisLabel = computed(() => {
  const run = profileSessionStore.jobSearchRun;
  if (!run || run.search_mode === "local_mock") {
    return "Deterministic local demo";
  }
  if (!run.llm_enabled) {
    return "Deterministic";
  }
  return llmProviderFromTrace.value
    ? `LLM enabled - ${llmProviderFromTrace.value}`
    : "LLM enabled";
});
const clientElapsedLabel = computed(() => {
  const startedAt = profileSessionStore.jobSearchClientStartedAt;
  const clientRunId = profileSessionStore.jobSearchClientRunId;
  if (startedAt === null || clientRunId !== runId.value) {
    return null;
  }
  const run = profileSessionStore.jobSearchRun;
  const completedAt = run?.status === "completed" || run?.status === "failed"
    ? new Date(run.updated_at).getTime()
    : nowMs.value;
  return formatDurationMs(completedAt - startedAt);
});
const clientStageEntries = computed(() => {
  if (profileSessionStore.jobSearchClientRunId !== runId.value) {
    return [];
  }
  return profileSessionStore.jobSearchClientStages;
});
const savedSearchResultIds = computed(() => {
  const ids = new Set<string>();
  for (const job of savedJobsStore.jobs) {
    const analysis = job.latest_analysis;
    if (
      analysis?.source_job_search_run_id === runId.value &&
      analysis.source_job_result_id
    ) {
      ids.add(analysis.source_job_result_id);
    }
  }
  for (const resultId of locallySavedResultIds.value) {
    ids.add(resultId);
  }
  return ids;
});

onMounted(async () => {
  startElapsedTicker();
  jobBriefHint.value = null;
  savedJobMessage.value = null;
  try {
    const run = await profileSessionStore.loadJobSearchRun(runId.value);
    if (!profileSessionStore.jobSearchSteps.length) {
      await profileSessionStore.loadJobSearchSteps(runId.value);
    }
    if (run.status === "pending" || run.status === "running") {
      await profileSessionStore.pollJobSearchRun(runId.value);
    }
    await loadResultFeedback();
  } catch {
    // Error state is rendered from the store.
  }

  try {
    await savedJobsStore.loadJobs(false);
  } catch {
    // Saved job loading should not block viewing the run.
  }
});

onUnmounted(() => {
  profileSessionStore.stopPollingJobSearchRun();
  stopElapsedTicker();
});

function goBackToConfirmed() {
  const sessionId = profileSessionStore.session?.session_id;
  if (!sessionId) {
    void router.push({ name: "home" });
    return;
  }
  void router.push({ name: "profile-confirmed", params: { sessionId } });
}

function goBackToSearchPreview() {
  const sessionId = profileSessionStore.session?.session_id;
  if (!sessionId) {
    void router.push({ name: "home" });
    return;
  }
  void router.push({ name: "search-preview", params: { sessionId } });
}

function showJobBriefHint() {
  jobBriefHint.value = "Job Brief is postponed until search recall and ranking are reliable.";
}

function isResultSaving(resultId: string) {
  return savingResultIds.value.includes(resultId);
}

function isResultSaved(resultId: string) {
  return savedSearchResultIds.value.has(resultId);
}

async function saveSearchResult(result: JobSearchResult) {
  const run = profileSessionStore.jobSearchRun;
  if (!run || isResultSaving(result.job_result_id) || isResultSaved(result.job_result_id)) {
    return;
  }

  savedJobMessage.value = null;
  savingResultIds.value = [...savingResultIds.value, result.job_result_id];
  try {
    await savedJobsStore.saveFromSearchResult({
      job_search_run_id: run.job_search_run_id,
      job_result_id: result.job_result_id,
      tags: ["search-result"],
      status: "saved"
    });
    if (!locallySavedResultIds.value.includes(result.job_result_id)) {
      locallySavedResultIds.value = [...locallySavedResultIds.value, result.job_result_id];
    }
    savedJobMessage.value = `${result.title} saved to job library.`;
  } catch {
    savedJobMessage.value = savedJobsStore.error ?? "Failed to save this result.";
  } finally {
    savingResultIds.value = savingResultIds.value.filter((id) => id !== result.job_result_id);
  }
}

async function loadResultFeedback() {
  try {
    const response = await listJobSearchResultFeedback(runId.value);
    const next: Record<string, JobSearchResultFeedback> = {};
    for (const item of response.items) {
      next[item.job_result_id] = item;
      feedbackTypes.value[item.job_result_id] = item.feedback_type;
      feedbackNotes.value[item.job_result_id] = item.note ?? "";
    }
    resultFeedback.value = next;
  } catch {
    // Feedback loading should not block viewing search results.
  }
}

async function submitResultFeedback(result: JobSearchResult) {
  const feedbackType = feedbackTypes.value[result.job_result_id];
  if (!feedbackType || savingFeedbackIds.value.includes(result.job_result_id)) return;
  feedbackMessage.value = null;
  savingFeedbackIds.value = [...savingFeedbackIds.value, result.job_result_id];
  try {
    const saved = await saveJobSearchResultFeedback(runId.value, result.job_result_id, {
      feedback_type: feedbackType,
      note: feedbackNotes.value[result.job_result_id]?.trim() || null
    });
    resultFeedback.value = { ...resultFeedback.value, [result.job_result_id]: saved };
    feedbackMessage.value = `Feedback saved for ${result.title}.`;
  } catch {
    feedbackMessage.value = `Failed to save feedback for ${result.title}.`;
  } finally {
    savingFeedbackIds.value = savingFeedbackIds.value.filter(
      (id) => id !== result.job_result_id
    );
  }
}

function statusTagType(status: string) {
  if (status === "completed") return "success";
  if (status === "failed") return "error";
  if (status === "running") return "warning";
  return "default";
}

function formatTraceDetail(value: unknown) {
  if (Array.isArray(value) || (value && typeof value === "object")) {
    return JSON.stringify(value);
  }
  return String(value ?? "");
}

function startElapsedTicker(): void {
  stopElapsedTicker();
  elapsedTimer = window.setInterval(() => {
    nowMs.value = Date.now();
  }, 1000);
}

function stopElapsedTicker(): void {
  if (elapsedTimer !== null) {
    window.clearInterval(elapsedTimer);
    elapsedTimer = null;
  }
}

function stepElapsedMs(step: JobSearchTraceStep): number | null {
  if (step.duration_ms !== null) {
    return step.duration_ms;
  }
  if (step.status === "running" && step.started_at) {
    return nowMs.value - new Date(step.started_at).getTime();
  }
  return null;
}

function formatDurationMs(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "not started";
  }
  const milliseconds = Math.max(0, value);
  if (milliseconds < 1000) {
    return `${Math.round(milliseconds)}ms`;
  }
  const seconds = milliseconds / 1000;
  if (seconds < 60) {
    return `${seconds.toFixed(seconds < 10 ? 1 : 0)}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return `${minutes}m ${remainingSeconds}s`;
}

function traceTimingEntries(step: JobSearchTraceStep): Array<[string, string]> {
  const timings = step.details.timings_ms;
  if (!timings || Array.isArray(timings) || typeof timings !== "object") {
    return [];
  }
  return Object.entries(timings)
    .filter(([, value]) => typeof value === "number")
    .map(([key, value]) => [formatTimingLabel(key), formatDurationMs(value as number)]);
}

function visibleTraceDetails(step: JobSearchTraceStep): Array<[string, unknown]> {
  const hiddenKeys = new Set([
    "timings_ms",
    "candidate_runs",
    "payload_stats",
    "provider_queries",
    "recall_queries",
    "ranking_signals",
    "query_stats",
    "source_attempts",
    "selected_indexes"
  ]);
  return Object.entries(step.details).filter(([key]) => !hiddenKeys.has(key));
}

function providerQueryRuns(step: JobSearchTraceStep): Array<Record<string, unknown>> {
  const runs = step.details.query_stats;
  if (!Array.isArray(runs)) {
    return [];
  }
  return runs
    .filter((item): item is Record<string, unknown> => item !== null && typeof item === "object")
    .filter((item) => typeof item.duration_ms === "number")
    .slice(0, 6);
}

function slowCandidateRuns(step: JobSearchTraceStep): Array<Record<string, unknown>> {
  const runs = step.details.candidate_runs;
  if (!Array.isArray(runs)) {
    return [];
  }
  return [...runs]
    .filter((item): item is Record<string, unknown> => item !== null && typeof item === "object")
    .sort((left, right) => Number(right.duration_ms ?? 0) - Number(left.duration_ms ?? 0))
    .slice(0, 3);
}

function formatTimingLabel(key: string): string {
  const labels: Record<string, string> = {
    intent_extraction: "Intent",
    plan_assembly: "Plan",
    deterministic_ranking: "Local rank",
    prompt_build: "Prompt",
    llm_request: "LLM request",
    response_validation: "Validation",
    total_candidate_work: "Candidate work",
    min_candidate: "Min candidate",
    max_candidate: "Max candidate",
    average_candidate: "Avg candidate",
    total: "Total"
  };
  return labels[key] ?? key.replace(/_/g, " ");
}

function formatQueryLabel(value: unknown): string {
  const text = String(value ?? "").trim();
  if (text.length <= 64) {
    return text || "query";
  }
  return `${text.slice(0, 63)}...`;
}
</script>

<template>
  <section class="flow-page">
    <FlowPageHeader
      title="Job Search Run"
      description="Follow retrieval and analysis steps, then review ranked job cards."
      :meta="`Run ${runId}`"
      :active-step="4"
    />

    <div v-if="profileSessionStore.error" class="error-banner">
      {{ profileSessionStore.error }}
    </div>

    <div
      v-if="profileSessionStore.isJobSearchLoading && !profileSessionStore.jobSearchRun"
      class="review-empty-state"
    >
      <p class="flow-message">Loading job search run...</p>
    </div>

    <div v-else-if="!profileSessionStore.jobSearchRun" class="review-empty-state">
      <p class="flow-message">
        This job search run could not be loaded. Return to the confirmed profile and start a new search.
      </p>
      <n-button type="primary" @click="goBackToConfirmed">Back to Confirmed Profile</n-button>
    </div>

    <div v-else class="job-search-layout">
      <div class="workspace-panel">
        <div class="panel-heading">
          <div>
            <h2>{{ runStatusLabel }}</h2>
            <p>
              {{ resultCount }} results, {{ completedTraceCount }}/{{ profileSessionStore.jobSearchSteps.length }} trace steps complete.
            </p>
          </div>
          <n-tag :type="statusTagType(profileSessionStore.jobSearchRun.status)" round>
            {{ profileSessionStore.jobSearchRun.status }}
          </n-tag>
        </div>

        <div class="flow-toolbar">
          <n-button secondary @click="goBackToConfirmed">Back to Confirmed Profile</n-button>
          <n-button secondary @click="goBackToSearchPreview">Back to Search Preview</n-button>
        </div>
      </div>

      <n-card title="Run Status" size="small" class="job-search-summary">
        <div class="job-status-row">
          <n-tag :type="statusTagType(profileSessionStore.jobSearchRun.status)" round>
            {{ profileSessionStore.jobSearchRun.status }}
          </n-tag>
          <span>
            Mode: {{ profileSessionStore.jobSearchRun.search_mode }} - Provider:
            {{ runProviderLabel }}
          </span>
        </div>
        <p>
          <strong>Provider Key:</strong>
          {{ profileSessionStore.jobSearchRun.search_provider || "not set" }}
        </p>
        <p><strong>Selected Sources:</strong> {{ selectedSourceSummary }}</p>
        <p><strong>Result Sources:</strong> {{ resultSourceSummary }}</p>
        <p><strong>Query:</strong> {{ profileSessionStore.jobSearchRun.query }}</p>
        <p>
          <strong>Target Roles:</strong>
          {{ profileSessionStore.jobSearchRun.target_roles.join(", ") || "Not set" }}
        </p>
        <p>
          <strong>Keywords:</strong>
          {{ profileSessionStore.jobSearchRun.keywords.join(", ") || "Not set" }}
        </p>
        <p>
          <strong>Locations:</strong>
          {{ profileSessionStore.jobSearchRun.locations.join(", ") || "Not set" }}
        </p>
        <p>
          <strong>Analysis:</strong>
          {{ llmAnalysisLabel }}
        </p>
        <p v-if="clientElapsedLabel">
          <strong>Client Elapsed:</strong>
          {{ clientElapsedLabel }}
        </p>
        <div v-if="clientStageEntries.length" class="job-card-section">
          <strong>Client Stages</strong>
          <div class="job-chip-row">
            <n-tag
              v-for="stage in clientStageEntries"
              :key="`${stage.label}-${stage.duration_ms}`"
              size="small"
              round
            >
              {{ stage.label }} {{ formatDurationMs(stage.duration_ms) }}
            </n-tag>
          </div>
        </div>
        <p v-if="profileSessionStore.jobSearchRun.error_message">
          <strong>Error:</strong> {{ profileSessionStore.jobSearchRun.error_message }}
        </p>
      </n-card>

      <n-card title="Trace Timeline" size="small">
        <p v-if="isRunning" class="flow-message">Searching and analyzing jobs...</p>
        <div class="trace-timeline">
          <div
            v-for="step in profileSessionStore.jobSearchSteps"
            :key="step.step_id"
            class="trace-step"
          >
            <div class="trace-step-header">
              <strong>{{ step.step_index }}. {{ step.name }}</strong>
              <div class="trace-step-tags">
                <n-tag size="small" round>{{ formatDurationMs(stepElapsedMs(step)) }}</n-tag>
                <n-tag :type="statusTagType(step.status)" round>{{ step.status }}</n-tag>
                <n-tag size="small" round>{{ step.mode }}</n-tag>
              </div>
            </div>
            <p>{{ step.summary }}</p>
            <p v-if="step.fallback_reason"><strong>Fallback:</strong> {{ step.fallback_reason }}</p>
            <div v-if="traceTimingEntries(step).length" class="job-card-section">
              <strong>Timings</strong>
              <div class="job-chip-row">
                <n-tag
                  v-for="[key, value] in traceTimingEntries(step)"
                  :key="key"
                  size="small"
                  round
                >
                  {{ key }} {{ value }}
                </n-tag>
              </div>
            </div>
            <div v-if="providerQueryRuns(step).length" class="job-card-section">
              <strong>Provider Calls</strong>
              <ul class="review-list">
                <li v-for="queryRun in providerQueryRuns(step)" :key="`${queryRun.query}-${queryRun.location}`">
                  {{ formatQueryLabel(queryRun.query) }} -
                  {{ queryRun.returned_count ?? 0 }} returned /
                  {{ queryRun.new_candidate_count ?? 0 }} new -
                  {{ formatDurationMs(Number(queryRun.duration_ms ?? 0)) }}
                </li>
              </ul>
            </div>
            <div v-if="slowCandidateRuns(step).length" class="job-card-section">
              <strong>Slowest Candidates</strong>
              <ul class="review-list">
                <li v-for="candidate in slowCandidateRuns(step)" :key="String(candidate.candidate_index)">
                  #{{ candidate.candidate_index }} {{ candidate.title || "Untitled" }} -
                  {{ formatDurationMs(Number(candidate.duration_ms ?? 0)) }}
                  <template v-if="candidate.fallback_reason">
                    - fallback {{ candidate.fallback_reason }}
                  </template>
                </li>
              </ul>
            </div>
            <div v-if="visibleTraceDetails(step).length" class="job-card-section">
              <strong>Trace Details</strong>
              <ul class="review-list">
                <li v-for="[key, value] in visibleTraceDetails(step)" :key="key">
                  {{ key }}: {{ formatTraceDetail(value) }}
                </li>
              </ul>
            </div>
            <p v-if="step.quality_warnings.length">
              <strong>Warnings:</strong> {{ step.quality_warnings.join(" - ") }}
            </p>
          </div>
        </div>
      </n-card>

      <p v-if="jobBriefHint" class="flow-meta">{{ jobBriefHint }}</p>
      <p v-if="savedJobMessage" class="flow-meta">{{ savedJobMessage }}</p>
      <p v-if="feedbackMessage" class="flow-meta">{{ feedbackMessage }}</p>

      <div
        v-if="profileSessionStore.jobSearchRun.status === 'failed'"
        class="review-empty-state"
      >
        <p class="flow-message">
          {{ profileSessionStore.jobSearchRun.error_message || "The provider run failed." }}
        </p>
      </div>

      <div v-if="profileSessionStore.jobSearchRun.status === 'completed'" class="job-card-grid">
        <n-card
          v-for="result in profileSessionStore.jobSearchRun.results"
          :key="result.job_result_id"
          size="small"
          class="job-card"
        >
          <div class="job-card-header">
            <div>
              <h2 class="job-card-title">{{ result.title }}</h2>
              <p class="job-card-company">{{ result.company }} - {{ result.location }}</p>
            </div>
            <div class="trace-step-tags">
              <n-tag type="success" round>{{ result.match_score }}</n-tag>
              <n-tag size="small" round>{{ result.confidence_label }}</n-tag>
            </div>
          </div>

          <p class="job-card-description">{{ result.description }}</p>

          <div class="job-card-section">
            <strong>Source</strong>
            <p>
              {{ formatSourceName(result.source_provider || result.source) }}
              <template v-if="result.source_url">
                -
                <a :href="result.source_url" target="_blank" rel="noreferrer">Open listing</a>
              </template>
            </p>
          </div>

          <div class="job-card-section">
            <strong>Analysis</strong>
            <p>{{ result.analysis_mode }} - {{ result.confidence_label }}</p>
          </div>

          <div class="job-card-section">
            <strong>Matched Keywords</strong>
            <div class="job-chip-row">
              <n-tag v-for="keyword in result.matched_keywords" :key="keyword" size="small" round>
                {{ keyword }}
              </n-tag>
            </div>
          </div>

          <div v-if="Object.keys(result.score_breakdown).length" class="job-card-section">
            <strong>Score Breakdown</strong>
            <div class="job-chip-row">
              <n-tag
                v-for="entry in Object.entries(result.score_breakdown)"
                :key="entry[0]"
                size="small"
                round
              >
                {{ entry[0] }} {{ entry[1] }}
              </n-tag>
            </div>
          </div>

          <div class="job-card-section">
            <strong>Match Reasons</strong>
            <ul class="review-list">
              <li v-for="reason in result.match_reasons" :key="reason">{{ reason }}</li>
            </ul>
          </div>

          <div v-if="result.evidence_quotes.length" class="job-card-section">
            <strong>Evidence</strong>
            <ul class="review-list">
              <li v-for="quote in result.evidence_quotes" :key="quote">{{ quote }}</li>
            </ul>
          </div>

          <div class="job-card-section">
            <strong>Risks</strong>
            <ul class="review-list">
              <li v-for="risk in result.risks" :key="risk">{{ risk }}</li>
            </ul>
          </div>

          <div class="job-card-footer">
            <span>{{ result.recommended_action }}</span>
            <div class="flow-toolbar-secondary">
              <n-button
                size="small"
                type="primary"
                :loading="isResultSaving(result.job_result_id)"
                :disabled="isResultSaved(result.job_result_id)"
                @click="saveSearchResult(result)"
              >
                {{ isResultSaved(result.job_result_id) ? "Saved" : "Save Job" }}
              </n-button>
              <n-button tertiary size="small" @click="showJobBriefHint">
                Generate Job Brief
              </n-button>
            </div>
          </div>

          <div class="job-card-section result-feedback-editor">
            <strong>Result Feedback</strong>
            <div class="result-feedback-controls">
              <n-select
                v-model:value="feedbackTypes[result.job_result_id]"
                :options="feedbackOptions"
                placeholder="Choose feedback"
                size="small"
              />
              <n-input
                v-model:value="feedbackNotes[result.job_result_id]"
                placeholder="Optional note"
                maxlength="500"
                size="small"
              />
              <n-button
                size="small"
                secondary
                :disabled="!feedbackTypes[result.job_result_id]"
                :loading="savingFeedbackIds.includes(result.job_result_id)"
                @click="submitResultFeedback(result)"
              >
                {{ resultFeedback[result.job_result_id] ? "Update Feedback" : "Save Feedback" }}
              </n-button>
            </div>
          </div>
        </n-card>
      </div>
    </div>
  </section>
</template>
