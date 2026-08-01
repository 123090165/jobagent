<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NCard,
  NCheckbox,
  NCollapse,
  NCollapseItem,
  NInput,
  NSelect,
  NTabPane,
  NTabs,
  NTag
} from "naive-ui";

import FlowPageHeader from "../components/FlowPageHeader.vue";
import { createChatConversation } from "../api/chat";
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
  JobSearchItem,
  JobSearchResult,
  JobSearchResultFeedback,
  JobSearchTraceStep
} from "../types/profileSession";

const BULK_LIMIT = 50;
const route = useRoute();
const router = useRouter();
const profileSessionStore = useProfileSessionStore();
const savedJobsStore = useSavedJobsStore();
const runId = computed(() => String(route.params.runId ?? ""));
const activeResultsView = ref<"ranked" | "pool">("ranked");
const selectionMode = ref(false);
const selectedResultIds = ref<string[]>([]);
const savedJobMessage = ref<string | null>(null);
const savingResultIds = ref<string[]>([]);
const locallySavedResultIds = ref<string[]>([]);
const resultFeedback = ref<Record<string, JobSearchResultFeedback>>({});
const feedbackTypes = ref<Record<string, JobSearchFeedbackType | null>>({});
const feedbackNotes = ref<Record<string, string>>({});
const savingFeedbackIds = ref<string[]>([]);
const openingAssistantResultIds = ref<string[]>([]);
const feedbackMessage = ref<string | null>(null);
const bulkSaving = ref(false);
const nowMs = ref(Date.now());
let elapsedTimer: number | null = null;

const feedbackOptions: Array<{ label: string; value: JobSearchFeedbackType }> = [
  { label: "Relevant", value: "relevant" },
  { label: "Not relevant", value: "irrelevant" },
  { label: "Duplicate", value: "duplicate" },
  { label: "Listing expired", value: "stale" },
  { label: "JD insufficient", value: "insufficient_jd" }
];

const run = computed(() => profileSessionStore.jobSearchRun);
const results = computed(() => run.value?.results ?? []);
const isRunning = computed(() => ["pending", "running"].includes(run.value?.status ?? ""));
const completedTraceCount = computed(
  () => profileSessionStore.jobSearchSteps.filter((step) => step.status === "completed").length
);
const runStatusLabel = computed(() => {
  if (!run.value) return "Loading run";
  if (run.value.status === "completed") return "Results ready";
  if (run.value.status === "failed") return "Run failed";
  return "Search running";
});
const runSelectedSources = computed(() => {
  if (!run.value) return [];
  const selected = [
    ...sourcesFromProviderName(run.value.search_provider),
    ...(run.value.selected_sources ?? [])
  ];
  if (run.value.search_mode === "local_mock" && selected.length === 0) selected.push("mock");
  return uniqueSourceKeys(selected);
});
const runProviderLabel = computed(() => {
  if (!run.value) return "Not set";
  return runSelectedSources.value.length
    ? runSelectedSources.value.map(formatSourceName).join(" + ")
    : formatProviderName(run.value.search_provider);
});
const resultSourceSummary = computed(() => {
  const counts = new Map<string, number>();
  for (const result of results.value) {
    const key = normalizeSourceKey(result.source_provider || result.source);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([source, count]) => `${formatSourceName(source)} ${count}`)
    .join(", ") || "No results yet";
});
const llmProviderFromTrace = computed(() => {
  const step = profileSessionStore.jobSearchSteps.find((item) => item.name === "Search planning");
  const provider = step?.details.llm_provider;
  return typeof provider === "string" && provider ? provider : null;
});
const llmAnalysisLabel = computed(() => {
  if (!run.value || run.value.search_mode === "local_mock") return "Deterministic local demo";
  if (!run.value.llm_enabled) return "Deterministic";
  return llmProviderFromTrace.value ? `LLM enabled - ${llmProviderFromTrace.value}` : "LLM enabled";
});
const clientElapsedLabel = computed(() => {
  if (
    profileSessionStore.jobSearchClientStartedAt === null
    || profileSessionStore.jobSearchClientRunId !== runId.value
  ) return null;
  const completedAt = ["completed", "failed"].includes(run.value?.status ?? "")
    ? new Date(run.value!.updated_at).getTime()
    : nowMs.value;
  return formatDurationMs(completedAt - profileSessionStore.jobSearchClientStartedAt);
});
const savedSearchResultIds = computed(() => {
  const ids = new Set(locallySavedResultIds.value);
  for (const job of savedJobsStore.jobs) {
    if (
      job.latest_analysis?.source_job_search_run_id === runId.value
      && job.latest_analysis.source_job_result_id
    ) {
      ids.add(job.latest_analysis.source_job_result_id);
    }
  }
  return ids;
});
const selectableResults = computed(() =>
  results.value.filter((result) => !savedSearchResultIds.value.has(result.job_result_id))
);
const allSelectableSelected = computed(() =>
  selectableResults.value.length > 0
  && selectableResults.value.slice(0, BULK_LIMIT)
    .every((result) => selectedResultIds.value.includes(result.job_result_id))
);

onMounted(async () => {
  startElapsedTicker();
  try {
    const loadedRun = await profileSessionStore.loadJobSearchRun(runId.value);
    if (!profileSessionStore.jobSearchSteps.length) {
      await profileSessionStore.loadJobSearchSteps(runId.value);
    }
    if (["pending", "running"].includes(loadedRun.status)) {
      await profileSessionStore.pollJobSearchRun(runId.value);
    }
    await Promise.allSettled([
      profileSessionStore.loadJobSearchItems(runId.value),
      loadResultFeedback()
    ]);
  } catch {
    // Store error state is rendered.
  }
  try {
    await savedJobsStore.loadJobs(false);
  } catch {
    // Saved-state detection must not block the results page.
  }
});

onUnmounted(() => {
  profileSessionStore.stopPollingJobSearchRun();
  stopElapsedTicker();
});

function goBack(name: "profile-confirmed" | "search-preview") {
  const sessionId = profileSessionStore.session?.session_id;
  void router.push(sessionId ? { name, params: { sessionId } } : { name: "home" });
}

function goToSearchPreview() {
  const sessionId = profileSessionStore.session?.session_id;
  void router.push(
    sessionId
      ? { name: "search-preview", params: { sessionId } }
      : { name: "home" }
  );
}

function isResultSaving(resultId: string) {
  return savingResultIds.value.includes(resultId);
}

function isResultSaved(resultId: string) {
  return savedSearchResultIds.value.has(resultId);
}

function savedJobForResult(resultId: string) {
  return savedJobsStore.jobs.find((job) =>
    job.latest_analysis?.source_job_search_run_id === runId.value
    && job.latest_analysis.source_job_result_id === resultId
  ) ?? null;
}

async function persistSearchResult(result: JobSearchResult) {
  const existing = savedJobForResult(result.job_result_id);
  if (existing) return existing;
  if (!run.value) throw new Error("Search run is unavailable.");
  savingResultIds.value = [...savingResultIds.value, result.job_result_id];
  try {
    const savedJob = await savedJobsStore.saveFromSearchResult({
      job_search_run_id: run.value.job_search_run_id,
      job_result_id: result.job_result_id,
      tags: ["search-result"]
    });
    if (!locallySavedResultIds.value.includes(result.job_result_id)) {
      locallySavedResultIds.value = [...locallySavedResultIds.value, result.job_result_id];
    }
    selectedResultIds.value = selectedResultIds.value.filter(
      (id) => id !== result.job_result_id
    );
    return savedJob;
  } finally {
    savingResultIds.value = savingResultIds.value.filter((id) => id !== result.job_result_id);
  }
}

async function saveSearchResult(result: JobSearchResult) {
  if (isResultSaving(result.job_result_id) || isResultSaved(result.job_result_id)) return;
  savedJobMessage.value = null;
  try {
    await persistSearchResult(result);
    savedJobMessage.value = `${result.title} saved to job library.`;
  } catch {
    savedJobMessage.value = savedJobsStore.error ?? `Failed to save ${result.title}.`;
  }
}

function toggleSelection(resultId: string, checked: boolean) {
  if (checked) {
    if (selectedResultIds.value.length >= BULK_LIMIT) {
      savedJobMessage.value = `Select up to ${BULK_LIMIT} results at a time.`;
      return;
    }
    selectedResultIds.value = [...selectedResultIds.value, resultId];
  } else {
    selectedResultIds.value = selectedResultIds.value.filter((id) => id !== resultId);
  }
}

function toggleSelectAll(checked: boolean) {
  selectedResultIds.value = checked
    ? selectableResults.value.slice(0, BULK_LIMIT).map((result) => result.job_result_id)
    : [];
}

async function saveSelected() {
  const selected = results.value
    .filter((result) => selectedResultIds.value.includes(result.job_result_id))
    .filter((result) => !isResultSaved(result.job_result_id))
    .slice(0, BULK_LIMIT);
  if (!selected.length || bulkSaving.value) return;
  bulkSaving.value = true;
  savedJobMessage.value = null;
  let successes = 0;
  for (const result of selected) {
    try {
      await persistSearchResult(result);
      successes += 1;
    } catch {
      // Keep failed results selected so the user can retry them.
    }
  }
  const failures = selected.length - successes;
  savedJobMessage.value = failures
    ? `Saved ${successes} of ${selected.length} selected jobs; ${failures} failed. You can retry the remaining selection.`
    : `Saved all ${successes} selected jobs.`;
  bulkSaving.value = false;
}

async function askAssistantAboutResult(result: JobSearchResult) {
  if (!run.value || openingAssistantResultIds.value.includes(result.job_result_id)) return;
  openingAssistantResultIds.value = [...openingAssistantResultIds.value, result.job_result_id];
  try {
    const conversation = await createChatConversation({
      title: `Discuss ${result.title}`.slice(0, 120),
      data_scope: {
        resume_profile_id: run.value.resume_profile_id,
        job_search_result_refs: [{
          job_search_run_id: run.value.job_search_run_id,
          job_result_id: result.job_result_id
        }]
      }
    });
    await router.push({ name: "assistant", query: { conversation: conversation.conversation_id } });
  } catch {
    savedJobMessage.value = `Could not open an assistant conversation for ${result.title}.`;
  } finally {
    openingAssistantResultIds.value = openingAssistantResultIds.value.filter(
      (id) => id !== result.job_result_id
    );
  }
}

async function generateBriefForResult(result: JobSearchResult) {
  if (isResultSaving(result.job_result_id)) return;
  savedJobMessage.value = null;
  try {
    const savedJob = savedJobForResult(result.job_result_id) ?? await persistSearchResult(result);
    await savedJobsStore.generateBrief(savedJob.saved_job_id);
    await router.push({ name: "saved-job-detail", params: { savedJobId: savedJob.saved_job_id } });
  } catch {
    savedJobMessage.value = savedJobsStore.error ?? "Failed to generate the Job Brief.";
  }
}

async function loadResultFeedback() {
  const response = await listJobSearchResultFeedback(runId.value);
  const next: Record<string, JobSearchResultFeedback> = {};
  for (const item of response.items) {
    next[item.job_result_id] = item;
    feedbackTypes.value[item.job_result_id] = item.feedback_type;
    feedbackNotes.value[item.job_result_id] = item.note ?? "";
  }
  resultFeedback.value = next;
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

function candidatePreview(item: JobSearchItem) {
  return item.candidate.snippet || item.candidate.raw_description || "No description available.";
}

function statusTagType(status: string) {
  if (status === "completed" || status === "final") return "success";
  if (status === "failed" || status === "filtered") return "error";
  if (status === "running" || status === "analyzed") return "warning";
  return "default";
}

function formatTraceDetail(value: unknown) {
  return Array.isArray(value) || (value && typeof value === "object")
    ? JSON.stringify(value)
    : String(value ?? "");
}

function startElapsedTicker() {
  stopElapsedTicker();
  elapsedTimer = window.setInterval(() => { nowMs.value = Date.now(); }, 1000);
}

function stopElapsedTicker() {
  if (elapsedTimer !== null) window.clearInterval(elapsedTimer);
  elapsedTimer = null;
}

function stepElapsedMs(step: JobSearchTraceStep) {
  if (step.duration_ms !== null) return step.duration_ms;
  return step.status === "running" && step.started_at
    ? nowMs.value - new Date(step.started_at).getTime()
    : null;
}

function formatDurationMs(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "not started";
  const milliseconds = Math.max(0, value);
  if (milliseconds < 1000) return `${Math.round(milliseconds)}ms`;
  const seconds = milliseconds / 1000;
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)}s`;
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

function traceTimingEntries(step: JobSearchTraceStep): Array<[string, string]> {
  const timings = step.details.timings_ms;
  if (!timings || Array.isArray(timings) || typeof timings !== "object") return [];
  return Object.entries(timings)
    .filter(([, value]) => typeof value === "number")
    .map(([key, value]) => [key.replace(/_/g, " "), formatDurationMs(value as number)]);
}

function visibleTraceDetails(step: JobSearchTraceStep): Array<[string, unknown]> {
  const hidden = new Set(["timings_ms", "candidate_runs", "query_stats"]);
  return Object.entries(step.details).filter(([key]) => !hidden.has(key));
}
</script>

<template>
  <section class="flow-page flow-page-wide">
    <FlowPageHeader
      title="Job Search Run"
      description="Review ranked matches first, then inspect the broader persisted candidate pool."
      :meta="`Run ${runId}`"
      :active-step="2"
    />

    <div v-if="profileSessionStore.error" class="error-banner">{{ profileSessionStore.error }}</div>
    <div v-if="profileSessionStore.isJobSearchLoading && !run" class="review-empty-state">
      <p class="flow-message">Loading job search run...</p>
    </div>
    <div v-else-if="!run" class="review-empty-state">
      <p class="flow-message">This job search run could not be loaded.</p>
      <n-button type="primary" @click="goBack('profile-confirmed')">Back to Confirmed Profile</n-button>
    </div>

    <div v-else class="job-search-layout">
      <div class="workspace-panel job-run-overview">
        <div class="panel-heading">
          <div>
            <h2>{{ runStatusLabel }}</h2>
            <p>
              {{ results.length }} ranked results · {{ profileSessionStore.jobSearchItemTotal }} candidates ·
              {{ completedTraceCount }}/{{ profileSessionStore.jobSearchSteps.length }} steps complete
            </p>
          </div>
          <n-tag :type="statusTagType(run.status)" round>{{ run.status }}</n-tag>
        </div>
        <div class="job-run-meta">
          <span><strong>Provider Key:</strong> {{ run.search_provider || "Not set" }}</span>
          <span><strong>Selected Sources:</strong> {{ runProviderLabel }}</span>
          <span><strong>Result Sources:</strong> {{ resultSourceSummary }}</span>
          <span><strong>Analysis:</strong> {{ llmAnalysisLabel }}</span>
          <span v-if="clientElapsedLabel"><strong>Elapsed:</strong> {{ clientElapsedLabel }}</span>
        </div>
        <p class="job-run-query"><strong>Query:</strong> {{ run.query }}</p>
        <div class="flow-toolbar">
          <n-button secondary @click="goBack('profile-confirmed')">Confirmed Profile</n-button>
          <n-button secondary @click="goToSearchPreview">Back to Search Preview</n-button>
        </div>
      </div>

      <n-collapse class="run-diagnostics">
        <n-collapse-item name="diagnostics">
          <template #header>
            <div class="diagnostics-header">
              <strong>Run diagnostics</strong>
              <span>{{ completedTraceCount }}/{{ profileSessionStore.jobSearchSteps.length }} steps</span>
            </div>
          </template>
          <p v-if="isRunning" class="flow-message">Searching and analyzing jobs...</p>
          <div class="trace-timeline">
            <div v-for="step in profileSessionStore.jobSearchSteps" :key="step.step_id" class="trace-step">
              <div class="trace-step-header">
                <strong>{{ step.step_index }}. {{ step.name }}</strong>
                <div class="trace-step-tags">
                  <n-tag size="small">{{ formatDurationMs(stepElapsedMs(step)) }}</n-tag>
                  <n-tag :type="statusTagType(step.status)" size="small">{{ step.status }}</n-tag>
                  <n-tag size="small">{{ step.mode }}</n-tag>
                </div>
              </div>
              <p>{{ step.summary }}</p>
              <p v-if="step.fallback_reason"><strong>Fallback:</strong> {{ step.fallback_reason }}</p>
              <div v-if="traceTimingEntries(step).length" class="job-chip-row">
                <n-tag v-for="[key, value] in traceTimingEntries(step)" :key="key" size="small">
                  {{ key }} {{ value }}
                </n-tag>
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
                <strong>Warnings:</strong> {{ step.quality_warnings.join(" · ") }}
              </p>
            </div>
          </div>
        </n-collapse-item>
      </n-collapse>

      <p v-if="savedJobMessage" class="flow-meta library-message">{{ savedJobMessage }}</p>
      <p v-if="feedbackMessage" class="flow-meta library-message">{{ feedbackMessage }}</p>

      <n-tabs v-model:value="activeResultsView" type="segment" animated>
        <n-tab-pane name="ranked" :tab="`Ranked results (${results.length})`">
          <div class="result-view-toolbar">
            <div class="flow-toolbar-secondary">
              <n-button size="small" secondary @click="selectionMode = !selectionMode">
                {{ selectionMode ? "Exit selection" : "Select jobs" }}
              </n-button>
              <n-checkbox
                v-if="selectionMode"
                :checked="allSelectableSelected"
                :disabled="!selectableResults.length"
                @update:checked="toggleSelectAll"
              >
                Select available (max {{ BULK_LIMIT }})
              </n-checkbox>
            </div>
            <n-button
              v-if="selectionMode"
              type="primary"
              size="small"
              :loading="bulkSaving"
              :disabled="!selectedResultIds.length"
              @click="saveSelected"
            >
              Save selected ({{ selectedResultIds.length }})
            </n-button>
          </div>

          <div v-if="run.status === 'failed'" class="review-empty-state">
            <p class="flow-message">{{ run.error_message || "The provider run failed." }}</p>
          </div>
          <div v-else-if="run.status === 'completed' && !results.length" class="review-empty-state">
            <p class="flow-message">No ranked results were produced. Check the candidate pool.</p>
          </div>

          <div class="job-card-grid compact-job-grid">
            <n-card v-for="result in results" :key="result.job_result_id" size="small" class="job-card compact-job-card">
              <div class="job-card-header">
                <div class="selectable-job-title">
                  <n-checkbox
                    v-if="selectionMode"
                    :checked="selectedResultIds.includes(result.job_result_id)"
                    :disabled="isResultSaved(result.job_result_id)"
                    @update:checked="toggleSelection(result.job_result_id, $event)"
                  />
                  <div>
                    <h2 class="job-card-title">{{ result.title }}</h2>
                    <p class="job-card-company">{{ result.company }} · {{ result.location }}</p>
                  </div>
                </div>
                <div class="trace-step-tags">
                  <n-tag type="success" round>{{ result.match_score }}</n-tag>
                  <n-tag size="small" round>{{ result.confidence_label }}</n-tag>
                </div>
              </div>

              <p class="job-source-line">
                {{ formatSourceName(result.source_provider || result.source) }}
                <template v-if="result.source_url">
                  · <a :href="result.source_url" target="_blank" rel="noreferrer">Open listing</a>
                </template>
              </p>
              <p class="job-card-description job-card-preview">{{ result.raw_snippet || result.description }}</p>
              <div v-if="result.match_reasons.length || result.risks.length" class="compact-fit-summary">
                <p v-if="result.match_reasons.length"><strong>Why it fits:</strong> {{ result.match_reasons.slice(0, 2).join(" · ") }}</p>
                <p v-else><strong>Top risk:</strong> {{ result.risks[0] }}</p>
              </div>
              <div class="job-card-footer">
                <span>{{ result.recommended_action }}</span>
                <div class="flow-toolbar-secondary">
                  <n-button size="small" secondary :loading="openingAssistantResultIds.includes(result.job_result_id)" @click="askAssistantAboutResult(result)">
                    Ask Assistant
                  </n-button>
                  <n-button size="small" type="primary" :loading="isResultSaving(result.job_result_id)" :disabled="isResultSaved(result.job_result_id)" @click="saveSearchResult(result)">
                    {{ isResultSaved(result.job_result_id) ? "Saved" : "Save Job" }}
                  </n-button>
                  <n-button tertiary size="small" :loading="isResultSaving(result.job_result_id)" @click="generateBriefForResult(result)">
                    {{ isResultSaved(result.job_result_id) ? "Generate Brief" : "Save & Brief" }}
                  </n-button>
                </div>
              </div>

              <n-collapse class="job-detail-disclosure">
                <n-collapse-item title="Full details" :name="result.job_result_id">
                  <div class="job-card-section">
                    <strong>Full job description</strong>
                    <p class="job-full-description">{{ result.description }}</p>
                  </div>
                  <div v-if="result.matched_keywords.length" class="job-card-section">
                    <strong>Matched keywords</strong>
                    <div class="job-chip-row">
                      <n-tag v-for="keyword in result.matched_keywords" :key="keyword" size="small">{{ keyword }}</n-tag>
                    </div>
                  </div>
                  <div v-if="result.job_requirements.length" class="job-card-section">
                    <strong>Requirements</strong>
                    <ul class="review-list">
                      <li v-for="requirement in result.job_requirements" :key="`${requirement.category}-${requirement.name}`">
                        {{ requirement.name }} ({{ requirement.necessity }})
                        <template v-if="requirement.evidence_quote"> — {{ requirement.evidence_quote }}</template>
                      </li>
                    </ul>
                  </div>
                  <div v-if="result.evidence_quotes.length" class="job-card-section">
                    <strong>Evidence</strong>
                    <ul class="review-list"><li v-for="quote in result.evidence_quotes" :key="quote">{{ quote }}</li></ul>
                  </div>
                  <div v-if="result.unknowns.length" class="job-card-section">
                    <strong>Needs confirmation</strong>
                    <ul class="review-list"><li v-for="unknown in result.unknowns" :key="unknown">{{ unknown }}</li></ul>
                  </div>
                  <div v-if="result.risks.length" class="job-card-section">
                    <strong>Risks</strong>
                    <ul class="review-list"><li v-for="risk in result.risks" :key="risk">{{ risk }}</li></ul>
                  </div>
                  <div v-if="Object.keys(result.score_breakdown).length" class="job-card-section">
                    <strong>Score Breakdown</strong>
                    <div class="job-chip-row">
                      <n-tag v-for="[label, score] in Object.entries(result.score_breakdown)" :key="label" size="small">
                        {{ label }} {{ score }}
                      </n-tag>
                    </div>
                  </div>
                  <div class="job-card-section result-feedback-editor">
                    <strong>Result feedback</strong>
                    <div class="result-feedback-controls">
                      <n-select v-model:value="feedbackTypes[result.job_result_id]" :options="feedbackOptions" placeholder="Choose feedback" size="small" />
                      <n-input v-model:value="feedbackNotes[result.job_result_id]" placeholder="Optional note" maxlength="500" size="small" />
                      <n-button size="small" secondary :disabled="!feedbackTypes[result.job_result_id]" :loading="savingFeedbackIds.includes(result.job_result_id)" @click="submitResultFeedback(result)">
                        {{ resultFeedback[result.job_result_id] ? "Update Feedback" : "Save Feedback" }}
                      </n-button>
                    </div>
                  </div>
                </n-collapse-item>
              </n-collapse>
            </n-card>
          </div>
        </n-tab-pane>

        <n-tab-pane name="pool" :tab="`Candidate pool (${profileSessionStore.jobSearchItemTotal})`">
          <div v-if="profileSessionStore.isJobSearchItemsLoading" class="review-empty-state">
            <p class="flow-message">Loading persisted candidates...</p>
          </div>
          <div v-else-if="profileSessionStore.jobSearchItemsError" class="error-banner">
            {{ profileSessionStore.jobSearchItemsError }}
          </div>
          <div v-else-if="!profileSessionStore.jobSearchItems.length" class="review-empty-state">
            <p class="flow-message">No persisted candidate pool is available for this run.</p>
          </div>
          <div v-else class="candidate-pool-list">
            <n-card v-for="item in profileSessionStore.jobSearchItems" :key="item.job_search_item_id" size="small" class="candidate-pool-card">
              <div class="job-card-header">
                <div>
                  <h2 class="job-card-title">#{{ item.rank }} {{ item.candidate.title }}</h2>
                  <p class="job-card-company">{{ item.candidate.company || "Unknown company" }} · {{ item.candidate.location || "Location not set" }}</p>
                </div>
                <n-tag :type="statusTagType(item.stage)" size="small" round>{{ item.stage }}</n-tag>
              </div>
              <p class="job-source-line">
                {{ formatSourceName(item.candidate.source_provider) }}
                <template v-if="item.candidate.source_url">
                  · <a :href="item.candidate.source_url" target="_blank" rel="noreferrer">Open listing</a>
                </template>
              </p>
              <p class="job-card-description job-card-preview">{{ candidatePreview(item) }}</p>
              <n-collapse class="job-detail-disclosure">
                <n-collapse-item title="Inspect candidate" :name="item.job_search_item_id">
                  <p v-if="item.candidate.raw_description" class="job-full-description">{{ item.candidate.raw_description }}</p>
                  <p><strong>Discovery query:</strong> {{ item.candidate.discovery_query || "Not recorded" }}</p>
                  <p><strong>Discovery rank:</strong> {{ item.candidate.discovery_rank ?? "Not recorded" }}</p>
                  <p><strong>Detail status:</strong> {{ item.candidate.detail_status || "Not recorded" }}</p>
                  <p v-if="item.candidate.provider_warnings.length">
                    <strong>Provider warnings:</strong> {{ item.candidate.provider_warnings.join(" · ") }}
                  </p>
                  <p class="flow-meta">
                    {{ item.result ? "This candidate is available in Ranked results." : "Unscored candidates can be inspected, but cannot be saved yet." }}
                  </p>
                </n-collapse-item>
              </n-collapse>
            </n-card>
          </div>
        </n-tab-pane>
      </n-tabs>
    </div>
  </section>
</template>
