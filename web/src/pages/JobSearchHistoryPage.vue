<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { NButton, NCard, NSelect, NTag } from "naive-ui";

import FlowPageHeader from "../components/FlowPageHeader.vue";
import { formatProviderName } from "../services/jobSearchSources";
import { useProfileSessionStore } from "../stores/profileSession";
import type { JobSearchRun } from "../types/profileSession";

const router = useRouter();
const store = useProfileSessionStore();
const statusFilter = ref("all");
const statusOptions = [
  { label: "All statuses", value: "all" },
  { label: "Active", value: "active" },
  { label: "Completed", value: "completed" },
  { label: "Failed", value: "failed" }
];

const visibleRuns = computed(() => {
  if (statusFilter.value === "all") return store.jobSearchRuns;
  if (statusFilter.value === "active") {
    return store.jobSearchRuns.filter((run) => ["pending", "running"].includes(run.status));
  }
  return store.jobSearchRuns.filter((run) => run.status === statusFilter.value);
});

onMounted(() => void refresh());

async function refresh() {
  try {
    await store.loadUserJobSearchRuns();
  } catch {
    // Store error is rendered below.
  }
}

function openRun(run: JobSearchRun) {
  void router.push({ name: "job-search", params: { runId: run.job_search_run_id } });
}

function searchAgain(run: JobSearchRun) {
  void router.push({ name: "search-preview", params: { sessionId: run.session_id } });
}

function statusType(status: JobSearchRun["status"]): "success" | "warning" | "error" | "info" {
  if (status === "completed") return "success";
  if (status === "failed") return "error";
  if (status === "running") return "info";
  return "warning";
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString();
}
</script>

<template>
  <section class="flow-page flow-page-wide">
    <FlowPageHeader
      eyebrow="Library"
      title="Search History"
      description="Reopen persisted searches and continue watching active runs."
      meta="User data"
      :active-step="4"
    />

    <div v-if="store.error" class="error-banner">{{ store.error }}</div>

    <div class="workspace-panel">
      <div class="panel-heading">
        <div>
          <h2>Search runs</h2>
          <p>{{ visibleRuns.length }} of {{ store.jobSearchRuns.length }} runs shown.</p>
        </div>
        <div class="flow-toolbar-secondary">
          <n-select v-model:value="statusFilter" :options="statusOptions" class="history-filter" />
          <n-button secondary :loading="store.isJobSearchLoading" @click="refresh">Refresh</n-button>
        </div>
      </div>
    </div>

    <div v-if="store.isJobSearchLoading && !store.jobSearchRuns.length" class="review-empty-state">
      <p class="flow-message">Loading search history...</p>
    </div>
    <div v-else-if="!visibleRuns.length" class="review-empty-state">
      <p class="flow-message">No search runs match this view.</p>
      <n-button type="primary" @click="router.push({ name: 'resume-profiles' })">Choose Profile</n-button>
    </div>
    <div v-else class="library-grid search-history-grid">
      <n-card v-for="run in visibleRuns" :key="run.job_search_run_id" size="small" class="library-card">
        <div class="job-card-header">
          <div>
            <h2 class="job-card-title">{{ run.query }}</h2>
            <p class="job-card-company">Updated {{ formatDate(run.updated_at) }}</p>
          </div>
          <n-tag :type="statusType(run.status)" round>{{ run.status }}</n-tag>
        </div>

        <div class="history-run-meta">
          <span><strong>Provider</strong> {{ formatProviderName(run.search_provider) }}</span>
          <span><strong>Results</strong> {{ run.results.length }}</span>
          <span><strong>Analysis</strong> {{ run.llm_enabled ? "LLM" : "Deterministic" }}</span>
        </div>
        <p v-if="run.error_message" class="history-run-error">{{ run.error_message }}</p>

        <div class="job-card-footer">
          <span>Created {{ formatDate(run.created_at) }}</span>
          <div class="flow-toolbar-secondary">
            <n-button size="small" secondary @click="searchAgain(run)">Search Again</n-button>
            <n-button size="small" type="primary" @click="openRun(run)">
              {{ ["pending", "running"].includes(run.status) ? "Watch Run" : "Open Run" }}
            </n-button>
          </div>
        </div>
      </n-card>
    </div>
  </section>
</template>
