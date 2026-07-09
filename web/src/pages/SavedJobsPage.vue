<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { NButton, NCard, NInput, NSelect, NSwitch, NTag } from "naive-ui";

import FlowPageHeader from "../components/FlowPageHeader.vue";
import { useSavedJobsStore } from "../stores/savedJobs";
import type { SavedJob, SavedJobStatus } from "../types/savedJob";

interface SavedJobDraft {
  status: SavedJobStatus;
  notes: string;
  tagsText: string;
}

const savedJobsStore = useSavedJobsStore();
const includeArchived = ref(false);
const actionMessage = ref<string | null>(null);
const drafts = ref<Record<string, SavedJobDraft>>({});

const statusOptions: Array<{ label: string; value: SavedJobStatus }> = [
  { label: "Saved", value: "saved" },
  { label: "Interested", value: "interested" },
  { label: "Applied", value: "applied" },
  { label: "Rejected", value: "rejected" },
  { label: "Archived", value: "archived" }
];

const activeJobs = computed(() => savedJobsStore.jobs.filter((job) => !job.archived_at));
const savedJobStats = computed(() => ({
  total: savedJobsStore.jobs.length,
  active: activeJobs.value.length,
  interested: savedJobsStore.jobs.filter((job) => job.status === "interested").length,
  applied: savedJobsStore.jobs.filter((job) => job.status === "applied").length
}));

onMounted(() => {
  void loadJobs();
});

watch(includeArchived, () => {
  void loadJobs();
});

async function loadJobs() {
  actionMessage.value = null;
  try {
    await savedJobsStore.loadJobs(includeArchived.value);
    syncDrafts();
  } catch {
    // Error state is rendered from the store.
  }
}

function syncDrafts() {
  const nextDrafts: Record<string, SavedJobDraft> = {};
  for (const job of savedJobsStore.jobs) {
    nextDrafts[job.saved_job_id] = drafts.value[job.saved_job_id] ?? {
      status: job.status,
      notes: job.notes ?? "",
      tagsText: job.tags.join(", ")
    };
  }
  drafts.value = nextDrafts;
}

async function updateJob(job: SavedJob) {
  const draft = drafts.value[job.saved_job_id];
  if (!draft) {
    return;
  }
  actionMessage.value = null;
  try {
    await savedJobsStore.updateJob(job.saved_job_id, {
      status: draft.status,
      notes: draft.notes.trim() || null,
      tags: toList(draft.tagsText)
    });
    actionMessage.value = `${job.title} updated.`;
  } catch {
    // Error state is rendered from the store.
  }
}

async function archiveJob(job: SavedJob) {
  actionMessage.value = null;
  try {
    await savedJobsStore.archiveJob(job.saved_job_id);
    actionMessage.value = `${job.title} archived.`;
  } catch {
    // Error state is rendered from the store.
  }
}

function toList(value: string): string[] {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function statusTagType(status: SavedJobStatus) {
  if (status === "interested" || status === "applied") return "success";
  if (status === "rejected" || status === "archived") return "warning";
  return "default";
}

function formatDate(value: string | null): string {
  if (!value) {
    return "Not set";
  }
  return new Date(value).toLocaleString();
}

function analysisLabel(job: SavedJob): string {
  const analysis = job.latest_analysis;
  if (!analysis) {
    return "No analysis saved";
  }
  const score = analysis.match_score === null ? "unscored" : `${analysis.match_score}`;
  return `${score} / ${analysis.confidence_label || analysis.analysis_mode}`;
}
</script>

<template>
  <section class="flow-page flow-page-wide">
    <FlowPageHeader
      eyebrow="Library"
      title="Saved Jobs"
      description="Review structured JDs and saved match analysis under the current account."
      meta="User data"
      :active-step="5"
    />

    <div v-if="savedJobsStore.error" class="error-banner">
      {{ savedJobsStore.error }}
    </div>

    <div class="workspace-panel">
      <div class="panel-heading">
        <div>
          <h2>Job collection</h2>
          <p>{{ activeJobs.length }} active saved jobs.</p>
        </div>
        <div class="flow-toolbar-secondary">
          <div class="setting-control">
            <span class="flow-meta">Archived</span>
            <n-switch v-model:value="includeArchived" />
          </div>
          <n-button secondary :loading="savedJobsStore.isLoading" @click="loadJobs">
            Refresh
          </n-button>
        </div>
      </div>
    </div>

    <div class="metric-grid">
      <div class="metric-card">
        <span>Total</span>
        <strong>{{ savedJobStats.total }}</strong>
      </div>
      <div class="metric-card">
        <span>Active</span>
        <strong>{{ savedJobStats.active }}</strong>
      </div>
      <div class="metric-card">
        <span>Interested</span>
        <strong>{{ savedJobStats.interested }}</strong>
      </div>
      <div class="metric-card">
        <span>Applied</span>
        <strong>{{ savedJobStats.applied }}</strong>
      </div>
    </div>

    <p v-if="actionMessage" class="flow-meta library-message">{{ actionMessage }}</p>

    <div
      v-if="savedJobsStore.isLoading && savedJobsStore.jobs.length === 0"
      class="review-empty-state"
    >
      <p class="flow-message">Loading saved jobs...</p>
    </div>

    <div v-else-if="savedJobsStore.jobs.length === 0" class="review-empty-state">
      <p class="flow-message">
        No job has been saved yet. Run a job search and save matching results from the result cards.
      </p>
    </div>

    <div v-else class="library-grid">
      <n-card
        v-for="job in savedJobsStore.jobs"
        :key="job.saved_job_id"
        size="small"
        class="library-card"
      >
        <div class="job-card-header">
          <div>
            <h2 class="job-card-title">{{ job.title }}</h2>
            <p class="job-card-company">
              {{ job.company || "Unknown company" }} - {{ job.location || "Unknown location" }}
            </p>
          </div>
          <div class="trace-step-tags">
            <n-tag :type="statusTagType(job.status)" round>{{ job.status }}</n-tag>
            <n-tag v-if="job.archived_at" type="warning" round>Archived</n-tag>
          </div>
        </div>

        <p class="job-card-description">{{ job.raw_jd_text }}</p>

        <div class="job-card-section">
          <strong>Source</strong>
          <p>
            {{ job.source_provider || "manual" }}
            <template v-if="job.source_url">
              -
              <a :href="job.source_url" target="_blank" rel="noreferrer">Open listing</a>
            </template>
          </p>
        </div>

        <div class="job-card-section">
          <strong>Latest Analysis</strong>
          <p>{{ analysisLabel(job) }}</p>
          <p v-if="job.latest_analysis?.recommendation">
            {{ job.latest_analysis.recommendation }}
          </p>
        </div>

        <div class="job-card-section">
          <strong>Tags</strong>
          <div class="job-chip-row">
            <n-tag v-for="tag in job.tags" :key="tag" size="small" round>{{ tag }}</n-tag>
            <span v-if="!job.tags.length" class="flow-meta">No tags</span>
          </div>
        </div>

        <div v-if="drafts[job.saved_job_id]" class="saved-job-editor">
          <label class="draft-field">
            <span>Status</span>
            <n-select
              v-model:value="drafts[job.saved_job_id].status"
              :options="statusOptions"
              size="small"
            />
          </label>
          <label class="draft-field">
            <span>Notes</span>
            <n-input
              v-model:value="drafts[job.saved_job_id].notes"
              type="textarea"
              :rows="3"
            />
          </label>
          <label class="draft-field">
            <span>Tags</span>
            <n-input
              v-model:value="drafts[job.saved_job_id].tagsText"
              placeholder="tag one, tag two"
            />
          </label>
        </div>

        <div class="job-card-footer">
          <span>Saved {{ formatDate(job.saved_at) }}</span>
          <div class="flow-toolbar-secondary">
            <n-button
              size="small"
              type="primary"
              :loading="savedJobsStore.isSaving"
              @click="updateJob(job)"
            >
              Save Changes
            </n-button>
            <n-button
              size="small"
              tertiary
              :disabled="Boolean(job.archived_at)"
              :loading="savedJobsStore.isSaving"
              @click="archiveJob(job)"
            >
              Archive
            </n-button>
          </div>
        </div>
      </n-card>
    </div>
  </section>
</template>
