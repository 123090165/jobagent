<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NInput, NSelect, NTag } from "naive-ui";

import FlowPageHeader from "../components/FlowPageHeader.vue";
import { useSavedJobsStore } from "../stores/savedJobs";
import type { SavedJobStatus } from "../types/savedJob";

const route = useRoute();
const router = useRouter();
const store = useSavedJobsStore();
const savedJobId = computed(() => String(route.params.savedJobId ?? ""));
const status = ref<SavedJobStatus>("saved");
const notes = ref("");
const tagsText = ref("");
const actionMessage = ref<string | null>(null);
const statusOptions: Array<{ label: string; value: SavedJobStatus }> = [
  { label: "Saved", value: "saved" },
  { label: "Interested", value: "interested" },
  { label: "Applied", value: "applied" },
  { label: "Interviewing", value: "interviewing" },
  { label: "Rejected", value: "rejected" },
  { label: "Closed", value: "closed" }
];

const job = computed(() => store.selectedJob);
const structuredEntries = computed(() => Object.entries(job.value?.structured_jd ?? {}));

onMounted(async () => {
  try {
    const loaded = await store.loadJobDetail(savedJobId.value);
    status.value = loaded.status;
    notes.value = loaded.notes ?? "";
    tagsText.value = loaded.tags.join(", ");
  } catch {
    // Store error is rendered below.
  }
});

async function saveChanges() {
  if (!job.value) return;
  actionMessage.value = null;
  try {
    await store.updateJob(job.value.saved_job_id, {
      status: status.value,
      notes: notes.value.trim() || null,
      tags: tagsText.value.split(/\r?\n|,/).map((item) => item.trim()).filter(Boolean)
    });
    actionMessage.value = "Saved job updated.";
  } catch {
    // Store error is rendered below.
  }
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString();
}

function formatValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(", ") || "Not set";
  if (value && typeof value === "object") return JSON.stringify(value);
  return String(value ?? "Not set");
}
</script>

<template>
  <section class="flow-page flow-page-wide">
    <FlowPageHeader
      eyebrow="Saved Job"
      :title="job?.title || 'Job Details'"
      :description="job ? `${job.company || 'Unknown company'} - ${job.location || 'Unknown location'}` : 'Loading saved job.'"
      meta="Analysis history"
      :active-step="5"
    />

    <div v-if="store.error" class="error-banner">{{ store.error }}</div>
    <div v-if="store.isLoading && !job" class="review-empty-state">
      <p class="flow-message">Loading saved job details...</p>
    </div>
    <div v-else-if="!job" class="review-empty-state">
      <p class="flow-message">This saved job could not be loaded.</p>
      <n-button @click="router.push({ name: 'saved-jobs' })">Back to Saved Jobs</n-button>
    </div>

    <div v-else class="saved-job-detail-layout">
      <div class="flow-toolbar">
        <n-button secondary @click="router.push({ name: 'saved-jobs' })">Back to Saved Jobs</n-button>
        <n-button v-if="job.source_url" tag="a" :href="job.source_url" target="_blank" secondary>
          Open Listing
        </n-button>
      </div>

      <div class="saved-job-detail-grid">
        <n-card title="Job Description" size="small">
          <p class="saved-job-jd">{{ job.raw_jd_text }}</p>
        </n-card>

        <n-card title="Tracking" size="small">
          <div class="saved-job-editor">
            <label class="draft-field">
              <span>Status</span>
              <n-select v-model:value="status" :options="statusOptions" />
            </label>
            <label class="draft-field">
              <span>Notes</span>
              <n-input v-model:value="notes" type="textarea" :rows="5" />
            </label>
            <label class="draft-field">
              <span>Tags</span>
              <n-input v-model:value="tagsText" placeholder="priority, remote" />
            </label>
            <n-button type="primary" :loading="store.isSaving" @click="saveChanges">Save Changes</n-button>
            <p v-if="actionMessage" class="flow-meta">{{ actionMessage }}</p>
          </div>
        </n-card>
      </div>

      <n-card v-if="structuredEntries.length" title="Structured JD" size="small">
        <dl class="structured-jd-grid">
          <template v-for="[key, value] in structuredEntries" :key="key">
            <dt>{{ key.replace(/_/g, " ") }}</dt>
            <dd>{{ formatValue(value) }}</dd>
          </template>
        </dl>
      </n-card>

      <n-card title="Application Status History" size="small">
        <p v-if="!store.selectedJobStatusHistory.length" class="flow-message">
          No status changes recorded.
        </p>
        <div v-else class="status-history-list">
          <div
            v-for="event in store.selectedJobStatusHistory"
            :key="event.saved_job_status_event_id"
            class="status-history-item"
          >
            <div>
              <strong>{{ event.to_status }}</strong>
              <span v-if="event.from_status" class="flow-meta"> from {{ event.from_status }}</span>
            </div>
            <div class="status-history-meta">
              <span>{{ formatDate(event.changed_at) }}</span>
              <span v-if="event.reason">{{ event.reason }}</span>
            </div>
          </div>
        </div>
      </n-card>

      <n-card title="Analysis History" size="small">
        <p v-if="!store.selectedJobAnalyses.length" class="flow-message">No analysis snapshots saved.</p>
        <div v-else class="analysis-history-list">
          <article v-for="analysis in store.selectedJobAnalyses" :key="analysis.saved_job_analysis_id" class="analysis-history-item">
            <div class="job-card-header">
              <div>
                <h2>{{ formatDate(analysis.created_at) }}</h2>
                <p class="job-card-company">{{ analysis.analysis_mode }} analysis</p>
              </div>
              <div class="trace-step-tags">
                <n-tag v-if="analysis.match_score !== null" type="success" round>{{ analysis.match_score }}</n-tag>
                <n-tag v-if="analysis.confidence_label" round>{{ analysis.confidence_label }}</n-tag>
              </div>
            </div>
            <p v-if="analysis.recommendation">{{ analysis.recommendation }}</p>
            <div v-if="analysis.matched_strengths.length" class="job-card-section">
              <strong>Strengths</strong>
              <ul class="review-list"><li v-for="item in analysis.matched_strengths" :key="item">{{ item }}</li></ul>
            </div>
            <div v-if="analysis.critical_gaps.length" class="job-card-section">
              <strong>Critical Gaps</strong>
              <ul class="review-list"><li v-for="item in analysis.critical_gaps" :key="item">{{ item }}</li></ul>
            </div>
            <div v-if="analysis.resume_actions.length" class="job-card-section">
              <strong>Resume Actions</strong>
              <ul class="review-list"><li v-for="item in analysis.resume_actions" :key="item">{{ item }}</li></ul>
            </div>
            <div v-if="analysis.interview_questions.length" class="job-card-section">
              <strong>Interview Questions</strong>
              <ul class="review-list"><li v-for="item in analysis.interview_questions" :key="item">{{ item }}</li></ul>
            </div>
            <div class="flow-toolbar-secondary">
              <n-button
                v-if="analysis.source_job_search_run_id"
                size="small"
                secondary
                @click="router.push({ name: 'job-search', params: { runId: analysis.source_job_search_run_id } })"
              >Open Source Run</n-button>
              <span v-if="analysis.resume_profile_id" class="flow-meta">Profile {{ analysis.resume_profile_id }}</span>
            </div>
          </article>
        </div>
      </n-card>
    </div>
  </section>
</template>
