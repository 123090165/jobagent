<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { NButton, NDropdown, NInput, NSelect, NSwitch, NTag } from "naive-ui";

import FlowPageHeader from "../components/FlowPageHeader.vue";
import { useSavedJobsStore } from "../stores/savedJobs";
import type { SavedJob, SavedJobStatus } from "../types/savedJob";

const store = useSavedJobsStore();
const router = useRouter();
const includeArchived = ref(false);
const query = ref("");
const statusFilter = ref<string>("active");
const actionMessage = ref<string | null>(null);

const statusOptions: Array<{ label: string; value: SavedJobStatus }> = [
  { label: "Saved", value: "saved" },
  { label: "Interested", value: "interested" },
  { label: "Applied", value: "applied" },
  { label: "Interviewing", value: "interviewing" },
  { label: "Rejected", value: "rejected" },
  { label: "Closed", value: "closed" }
];
const filterOptions = [
  { label: "Active jobs", value: "active" },
  ...statusOptions,
  { label: "All statuses", value: "all" }
];
const rowActions = [
  { label: "Archive", key: "archive" },
  { label: "Delete permanently", key: "delete" }
];

const visibleJobs = computed(() => {
  const term = query.value.trim().toLocaleLowerCase();
  return store.jobs.filter((job) => {
    if (!includeArchived.value && job.archived_at) return false;
    if (statusFilter.value === "active" && ["rejected", "closed", "archived"].includes(job.status)) return false;
    if (statusFilter.value !== "active" && statusFilter.value !== "all" && job.status !== statusFilter.value) return false;
    if (!term) return true;
    return [job.title, job.company, job.location, ...job.tags]
      .filter(Boolean)
      .some((value) => String(value).toLocaleLowerCase().includes(term));
  });
});

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

async function updateStatus(job: SavedJob, value: SavedJobStatus) {
  actionMessage.value = null;
  try {
    await store.updateJob(job.saved_job_id, { status: value });
    actionMessage.value = `${job.title} moved to ${value}.`;
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

function statusTagType(status: SavedJobStatus) {
  if (["interested", "applied", "interviewing"].includes(status)) return "success";
  if (["rejected", "archived"].includes(status)) return "warning";
  return "default";
}

function scoreLabel(job: SavedJob): string {
  return job.latest_analysis?.match_score === null || job.latest_analysis?.match_score === undefined
    ? "Not scored"
    : `${job.latest_analysis.match_score}`;
}

function nextStep(job: SavedJob): string {
  if (job.status === "interviewing") return "Continue interview preparation";
  if (job.status === "applied") return "Review preparation plan";
  if (!job.latest_analysis) return "Review job details";
  if (job.latest_analysis.critical_gaps.length) return `Review gap: ${job.latest_analysis.critical_gaps[0]}`;
  return job.latest_analysis.recommendation || "Review fit and decide next action";
}
</script>

<template>
  <section class="flow-page flow-page-wide">
    <FlowPageHeader
      eyebrow="Library"
      title="Saved Jobs"
      description="Compare opportunities, track progress, and continue preparation."
      :meta="`${visibleJobs.length} shown`"
      :active-step="2"
    />

    <div v-if="store.error" class="error-banner">{{ store.error }}</div>

    <div class="saved-jobs-toolbar workspace-panel">
      <n-input v-model:value="query" clearable placeholder="Search role, company, location, or tag" />
      <n-select v-model:value="statusFilter" :options="filterOptions" />
      <label class="saved-jobs-archive-toggle">
        <span>Archived</span>
        <n-switch v-model:value="includeArchived" />
      </label>
      <n-button secondary :loading="store.isLoading" @click="loadJobs">Refresh</n-button>
    </div>

    <p v-if="actionMessage" class="flow-meta library-message">{{ actionMessage }}</p>

    <div v-if="store.isLoading && !store.jobs.length" class="review-empty-state">
      <p class="flow-message">Loading saved jobs...</p>
    </div>
    <div v-else-if="!visibleJobs.length" class="review-empty-state">
      <p class="flow-message">No saved jobs match the current filters.</p>
    </div>

    <div v-else class="saved-jobs-list">
      <article v-for="job in visibleJobs" :key="job.saved_job_id" class="saved-job-row">
        <div class="saved-job-row-main">
          <div class="job-card-header">
            <div>
              <h2 class="job-card-title">{{ job.title }}</h2>
              <p class="job-card-company">
                {{ job.company || "Unknown company" }} · {{ job.location || "Location not set" }}
              </p>
            </div>
            <n-tag :type="statusTagType(job.status)" size="small" round>{{ job.status }}</n-tag>
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
          <n-select
            :value="job.status"
            :options="statusOptions"
            size="small"
            :disabled="store.isSaving"
            @update:value="updateStatus(job, $event)"
          />
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
