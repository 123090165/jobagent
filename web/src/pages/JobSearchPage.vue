<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NTag } from "naive-ui";

import FlowPageHeader from "../components/FlowPageHeader.vue";
import {
  formatProviderName,
  formatSourceName,
  normalizeSourceKey,
  sourcesFromProviderName,
  uniqueSourceKeys
} from "../services/jobSearchSources";
import { useProfileSessionStore } from "../stores/profileSession";
import { useSavedJobsStore } from "../stores/savedJobs";
import type { JobSearchResult } from "../types/profileSession";

const route = useRoute();
const router = useRouter();
const profileSessionStore = useProfileSessionStore();
const savedJobsStore = useSavedJobsStore();
const runId = computed(() => String(route.params.runId ?? ""));
const jobBriefHint = ref<string | null>(null);
const savedJobMessage = ref<string | null>(null);
const savingResultIds = ref<string[]>([]);
const locallySavedResultIds = ref<string[]>([]);

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
          <strong>LLM Provider:</strong>
          {{
            profileSessionStore.jobSearchRun.search_mode === "local_mock"
              ? "Local demo"
              : profileSessionStore.jobSearchRun.search_mode === "browser_helper"
                ? "Browser helper"
              : profileSessionStore.jobSearchRun.llm_enabled
                ? "DeepSeek API"
                : "Local Ollama"
          }}
        </p>
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
                <n-tag :type="statusTagType(step.status)" round>{{ step.status }}</n-tag>
                <n-tag size="small" round>{{ step.mode }}</n-tag>
              </div>
            </div>
            <p>{{ step.summary }}</p>
            <p v-if="step.fallback_reason"><strong>Fallback:</strong> {{ step.fallback_reason }}</p>
            <div v-if="Object.keys(step.details).length" class="job-card-section">
              <strong>Trace Details</strong>
              <ul class="review-list">
                <li v-for="[key, value] in Object.entries(step.details)" :key="key">
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
        </n-card>
      </div>
    </div>
  </section>
</template>
