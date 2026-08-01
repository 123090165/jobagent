<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { NButton, NCheckbox, NDropdown, NInput, NSwitch, NTag } from "naive-ui";

import FlowPageHeader from "../components/FlowPageHeader.vue";
import { useSavedJobsStore } from "../stores/savedJobs";
import type { SavedJob } from "../types/savedJob";

const store = useSavedJobsStore();
const router = useRouter();
const includeArchived = ref(false);
const query = ref("");
const actionMessage = ref<string | null>(null);
const selectionMode = ref(false);
const selectedJobIds = ref<string[]>([]);
const isBulkSaving = ref(false);
const BULK_LIMIT = 50;

const rowActions = [
  { label: "Archive", key: "archive" },
  { label: "Delete permanently", key: "delete" }
];

const visibleJobs = computed(() => {
  const term = query.value.trim().toLocaleLowerCase();
  return store.jobs.filter((job) => {
    if (!includeArchived.value && job.archived_at) return false;
    if (!term) return true;
    return [job.title, job.company, job.location, ...job.tags]
      .filter(Boolean)
      .some((value) => String(value).toLocaleLowerCase().includes(term));
  });
});
const selectedJobs = computed(() =>
  visibleJobs.value
    .filter((job) => selectedJobIds.value.includes(job.saved_job_id))
    .slice(0, BULK_LIMIT)
);
const allVisibleSelected = computed(() =>
  visibleJobs.value.length > 0
  && visibleJobs.value.slice(0, BULK_LIMIT)
    .every((job) => selectedJobIds.value.includes(job.saved_job_id))
);

onMounted(() => void loadJobs());
watch(includeArchived, () => void loadJobs());

async function loadJobs() {
  actionMessage.value = null;
  try {
    await store.loadJobs(includeArchived.value);
  } catch {
    // Store error is rendered below.
  }
}

async function handleRowAction(key: string, job: SavedJob) {
  actionMessage.value = null;
  try {
    if (key === "archive") {
      await store.archiveJob(job.saved_job_id);
      actionMessage.value = `${job.title} archived.`;
      return;
    }
    if (key === "delete" && window.confirm("Permanently delete this saved job? Search history and profiles will remain.")) {
      await store.deleteJob(job.saved_job_id);
      actionMessage.value = `${job.title} deleted.`;
    }
  } catch {
    // Store error is rendered below.
  }
}

function toggleSelection(jobId: string, checked: boolean) {
  if (checked) {
    if (selectedJobIds.value.length >= BULK_LIMIT) {
      actionMessage.value = `Select up to ${BULK_LIMIT} jobs at a time.`;
      return;
    }
    selectedJobIds.value = [...selectedJobIds.value, jobId];
  } else {
    selectedJobIds.value = selectedJobIds.value.filter((id) => id !== jobId);
  }
}

function toggleSelectVisible(checked: boolean) {
  selectedJobIds.value = checked
    ? visibleJobs.value.slice(0, BULK_LIMIT).map((job) => job.saved_job_id)
    : [];
}

function clearCompletedSelection(successfulIds: string[]) {
  const successful = new Set(successfulIds);
  selectedJobIds.value = selectedJobIds.value.filter((id) => !successful.has(id));
}

function reportBulkResult(action: string, jobs: SavedJob[], successfulIds: string[]) {
  clearCompletedSelection(successfulIds);
  const failures = jobs.length - successfulIds.length;
  actionMessage.value = failures
    ? `${action}: ${successfulIds.length} of ${jobs.length} succeeded; ${failures} failed. Retry the remaining selection.`
    : `${action}: all ${jobs.length} jobs succeeded.`;
}

async function bulkArchive() {
  const jobs = [...selectedJobs.value];
  if (!jobs.length || isBulkSaving.value) return;
  isBulkSaving.value = true;
  actionMessage.value = null;
  const successfulIds: string[] = [];
  for (const job of jobs) {
    try {
      await store.archiveJob(job.saved_job_id);
      successfulIds.push(job.saved_job_id);
    } catch {
      // Keep failed jobs selected for retry.
    }
  }
  reportBulkResult("Archive", jobs, successfulIds);
  isBulkSaving.value = false;
}

async function bulkDelete() {
  const jobs = [...selectedJobs.value];
  if (!jobs.length || isBulkSaving.value) return;
  const confirmed = window.confirm(
    `Permanently delete ${jobs.length} selected saved job${jobs.length === 1 ? "" : "s"}? This cannot be undone.`
  );
  if (!confirmed) return;
  isBulkSaving.value = true;
  actionMessage.value = null;
  const successfulIds: string[] = [];
  for (const job of jobs) {
    try {
      await store.deleteJob(job.saved_job_id);
      successfulIds.push(job.saved_job_id);
    } catch {
      // Keep failed jobs selected for retry.
    }
  }
  reportBulkResult("Permanent delete", jobs, successfulIds);
  isBulkSaving.value = false;
}

function scoreLabel(job: SavedJob): string {
  return job.latest_analysis?.match_score === null || job.latest_analysis?.match_score === undefined
    ? "Not scored"
    : `${job.latest_analysis.match_score}`;
}

function nextStep(job: SavedJob): string {
  if (!job.latest_analysis) return "Review job details";
  if (job.latest_analysis.critical_gaps.length) return `Review gap: ${job.latest_analysis.critical_gaps[0]}`;
  return job.latest_analysis.recommendation || "Review fit and decide next action";
}
</script>

<template>
  <section class="flow-page flow-page-wide">
    <FlowPageHeader
      eyebrow="Library"
      title="Job Workspaces"
      description="Compare opportunities, track progress, and continue preparation."
      :meta="`${visibleJobs.length} shown`"
      :active-step="2"
    />

    <div v-if="store.error" class="error-banner">{{ store.error }}</div>

    <div class="saved-jobs-toolbar workspace-panel">
      <n-input v-model:value="query" clearable placeholder="Search role, company, location, or tag" />
      <label class="saved-jobs-archive-toggle">
        <span>Archived</span>
        <n-switch v-model:value="includeArchived" />
      </label>
      <n-button secondary :loading="store.isLoading" @click="loadJobs">Refresh</n-button>
      <n-button secondary @click="selectionMode = !selectionMode">
        {{ selectionMode ? "Exit selection" : "Select jobs" }}
      </n-button>
    </div>

    <div v-if="selectionMode" class="saved-jobs-bulk-bar workspace-panel">
      <n-checkbox
        :checked="allVisibleSelected"
        :disabled="!visibleJobs.length"
        @update:checked="toggleSelectVisible"
      >
        Select visible (max {{ BULK_LIMIT }})
      </n-checkbox>
      <span class="flow-meta">{{ selectedJobIds.length }} selected</span>
      <n-button
        size="small"
        secondary
        :loading="isBulkSaving"
        :disabled="!selectedJobIds.length"
        @click="bulkArchive"
      >
        Archive
      </n-button>
      <n-button
        size="small"
        type="error"
        secondary
        :loading="isBulkSaving"
        :disabled="!selectedJobIds.length"
        @click="bulkDelete"
      >
        Delete permanently
      </n-button>
    </div>

    <p v-if="actionMessage" class="flow-meta library-message">{{ actionMessage }}</p>

    <div v-if="store.isLoading && !store.jobs.length" class="review-empty-state">
      <p class="flow-message">Loading job workspaces...</p>
    </div>
    <div v-else-if="!visibleJobs.length" class="review-empty-state">
      <p class="flow-message">No job workspaces match the current filters.</p>
    </div>

    <div v-else class="saved-jobs-list">
      <article v-for="job in visibleJobs" :key="job.saved_job_id" class="saved-job-row">
        <n-checkbox
          v-if="selectionMode"
          class="saved-job-row-checkbox"
          :checked="selectedJobIds.includes(job.saved_job_id)"
          @update:checked="toggleSelection(job.saved_job_id, $event)"
        />
        <div class="saved-job-row-main">
          <div class="job-card-header">
            <div>
              <h2 class="job-card-title">{{ job.title }}</h2>
              <p class="job-card-company">
                {{ job.company || "Unknown company" }} · {{ job.location || "Location not set" }}
              </p>
            </div>
            <n-tag :type="job.archived_at ? 'warning' : 'default'" size="small" round>
              {{ job.archived_at ? "Archived" : "Saved" }}
            </n-tag>
          </div>
          <div v-if="job.tags.length" class="job-chip-row">
            <n-tag v-for="tag in job.tags.slice(0, 4)" :key="tag" size="small">{{ tag }}</n-tag>
          </div>
        </div>

        <div class="saved-job-score">
          <span>Match</span>
          <strong>{{ scoreLabel(job) }}</strong>
          <small>{{ job.latest_analysis?.confidence_label || "No confidence" }}</small>
        </div>

        <div class="saved-job-next-step">
          <span>Next step</span>
          <p>{{ nextStep(job) }}</p>
        </div>

        <div class="saved-job-row-actions">
          <n-button type="primary" size="small" @click="router.push({ name: 'saved-job-detail', params: { savedJobId: job.saved_job_id } })">
            Open Workspace
          </n-button>
          <n-dropdown :options="rowActions" trigger="click" @select="handleRowAction($event, job)">
            <n-button size="small" quaternary>More</n-button>
          </n-dropdown>
        </div>
      </article>
    </div>
  </section>
</template>
