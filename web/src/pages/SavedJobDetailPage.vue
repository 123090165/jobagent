<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NCollapse, NCollapseItem, NInput, NSelect, NTabPane, NTabs, NTag } from "naive-ui";

import { downloadPreparationPrompt } from "../api/savedJobs";
import { useSavedJobsStore } from "../stores/savedJobs";
import type { SavedJobStatus } from "../types/savedJob";

const route = useRoute();
const router = useRouter();
const store = useSavedJobsStore();
const savedJobId = computed(() => String(route.params.savedJobId ?? ""));
const activeTab = ref("overview");
const status = ref<SavedJobStatus>("saved");
const notes = ref("");
const tagsText = ref("");
const actionMessage = ref<string | null>(null);
const preparationAnswers = ref<Record<string, string>>({});
const externalAnswerJson = ref("");
const showExternalExchange = ref(false);
const statusOptions: Array<{ label: string; value: SavedJobStatus }> = [
  { label: "Saved", value: "saved" },
  { label: "Interested", value: "interested" },
  { label: "Applied", value: "applied" },
  { label: "Interviewing", value: "interviewing" },
  { label: "Rejected", value: "rejected" },
  { label: "Closed", value: "closed" }
];

const job = computed(() => store.selectedJob);
const latestAnalysis = computed(() => store.selectedJobAnalyses[0] ?? job.value?.latest_analysis ?? null);
const latestBrief = computed(() => store.selectedJobBriefs[0] ?? null);
const preparation = computed(() => store.selectedPreparation);
const structuredEntries = computed(() => Object.entries(job.value?.structured_jd ?? {}));
const preparationButtonLabel = computed(() => preparation.value ? "Refresh Preparation" : "Start Preparation");

onMounted(async () => {
  try {
    const loaded = await store.loadJobDetail(savedJobId.value);
    status.value = loaded.status;
    notes.value = loaded.notes ?? "";
    tagsText.value = loaded.tags.join(", ");
    syncPreparationAnswers();
  } catch {
    // Store error is rendered below.
  }
});

async function saveTracking() {
  if (!job.value) return;
  actionMessage.value = null;
  try {
    await store.updateJob(job.value.saved_job_id, {
      status: status.value,
      notes: notes.value.trim() || null,
      tags: tagsText.value.split(/\r?\n|,/).map((item) => item.trim()).filter(Boolean)
    });
    actionMessage.value = "Tracking details saved.";
  } catch {
    // Store error is rendered above.
  }
}

function syncPreparationAnswers() {
  preparationAnswers.value = Object.fromEntries(
    (store.selectedPreparation?.answers ?? []).map((item) => [item.question_id, item.answer])
  );
}

async function refreshSnapshot() {
  if (!job.value) return;
  actionMessage.value = null;
  try {
    await store.generateBrief(job.value.saved_job_id);
    actionMessage.value = "Decision snapshot refreshed.";
  } catch {
    // Store error is rendered above.
  }
}

async function generatePreparation() {
  if (!job.value) return;
  actionMessage.value = null;
  try {
    await store.generatePreparation(job.value.saved_job_id);
    syncPreparationAnswers();
    activeTab.value = "preparation";
    actionMessage.value = "Preparation workspace refreshed.";
  } catch {
    // Store error is rendered above.
  }
}

async function savePreparationAnswers() {
  if (!job.value || !preparation.value) return;
  const answers = preparation.value.questions
    .map((question) => ({
      question_id: question.question_id,
      answer: (preparationAnswers.value[question.question_id] ?? "").trim()
    }))
    .filter((answer) => answer.answer.length > 0);
  if (!answers.length) {
    actionMessage.value = "Answer at least one evidence question.";
    return;
  }
  try {
    await store.savePreparationAnswers(job.value.saved_job_id, answers);
    actionMessage.value = "Answers saved and preparation plan updated.";
  } catch {
    // Store error is rendered above.
  }
}

async function exportPreparationPrompt() {
  if (!job.value) return;
  try {
    const blob = await downloadPreparationPrompt(job.value.saved_job_id);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "interview-preparation-prompt.txt";
    anchor.click();
    URL.revokeObjectURL(url);
  } catch {
    actionMessage.value = "External chat prompt could not be exported.";
  }
}

function importExternalAnswers() {
  try {
    const parsed = JSON.parse(externalAnswerJson.value) as {
      answers?: Array<{ question_id?: string; answer?: string }>;
    };
    const validIds = new Set(preparation.value?.questions.map((item) => item.question_id) ?? []);
    for (const item of parsed.answers ?? []) {
      if (item.question_id && validIds.has(item.question_id) && item.answer?.trim()) {
        preparationAnswers.value[item.question_id] = item.answer.trim();
      }
    }
    actionMessage.value = "External answers imported. Review before creating the plan.";
  } catch {
    actionMessage.value = "Expected JSON with an answers array containing question_id and answer.";
  }
}

function openPreparation() {
  if (preparation.value) activeTab.value = "preparation";
  else void generatePreparation();
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
  <section class="flow-page flow-page-wide saved-job-workspace">
    <div v-if="store.error" class="error-banner">{{ store.error }}</div>
    <div v-if="store.isLoading && !job" class="review-empty-state">
      <p class="flow-message">Loading saved job workspace...</p>
    </div>
    <div v-else-if="!job" class="review-empty-state">
      <p class="flow-message">This saved job could not be loaded.</p>
      <n-button @click="router.push({ name: 'saved-jobs' })">Back to Saved Jobs</n-button>
    </div>

    <template v-else>
      <header class="saved-job-workspace-header">
        <n-button text @click="router.push({ name: 'saved-jobs' })">← Saved Jobs</n-button>
        <div class="saved-job-workspace-title">
          <div>
            <p class="flow-kicker">Saved opportunity</p>
            <h1>{{ job.title }}</h1>
            <p>{{ job.company || "Unknown company" }} · {{ job.location || "Location not set" }}</p>
          </div>
          <div class="saved-job-header-actions">
            <n-select v-model:value="status" :options="statusOptions" @update:value="saveTracking" />
            <n-button v-if="job.source_url" tag="a" :href="job.source_url" target="_blank" secondary>
              Open Listing
            </n-button>
          </div>
        </div>
        <p v-if="actionMessage" class="flow-meta library-message">{{ actionMessage }}</p>
      </header>

      <n-tabs v-model:value="activeTab" type="line" animated class="saved-job-tabs">
        <n-tab-pane name="overview" tab="Overview">
          <div class="saved-job-overview-grid">
            <section class="workspace-panel decision-snapshot">
              <div class="panel-heading">
                <div><h2>Decision Snapshot</h2><p>Latest fit assessment and recommended action.</p></div>
                <n-button size="small" secondary :loading="store.isSaving" @click="refreshSnapshot">
                  {{ latestBrief ? "Refresh Snapshot" : "Create Snapshot" }}
                </n-button>
              </div>

              <div class="decision-score-row">
                <div class="decision-score">
                  <span>Match</span>
                  <strong>{{ latestAnalysis?.match_score ?? "—" }}</strong>
                  <small>{{ latestAnalysis?.confidence_label || "Not assessed" }}</small>
                </div>
                <p>{{ latestBrief?.content.decision_summary || latestAnalysis?.recommendation || "Create a snapshot to summarize fit and next actions." }}</p>
              </div>

              <div v-if="latestBrief || latestAnalysis" class="decision-columns">
                <div>
                  <h3>Strengths</h3>
                  <ul class="review-list">
                    <li v-for="item in (latestBrief?.content.fit_signals || latestAnalysis?.matched_strengths || [])" :key="item">{{ item }}</li>
                  </ul>
                </div>
                <div>
                  <h3>Important Gaps</h3>
                  <ul class="review-list">
                    <li v-for="item in (latestBrief?.content.evidence_gaps || latestAnalysis?.critical_gaps || [])" :key="item">{{ item }}</li>
                  </ul>
                </div>
                <div>
                  <h3>Next Actions</h3>
                  <ul class="review-list">
                    <li v-for="item in (latestBrief?.content.next_actions || latestAnalysis?.resume_actions || [])" :key="item">{{ item }}</li>
                  </ul>
                </div>
              </div>
            </section>

            <aside class="workspace-panel saved-job-tracking-panel">
              <div class="panel-heading"><div><h2>Tracking</h2><p>Private notes and organization.</p></div></div>
              <label class="draft-field"><span>Notes</span><n-input v-model:value="notes" type="textarea" :rows="5" /></label>
              <label class="draft-field"><span>Tags</span><n-input v-model:value="tagsText" placeholder="priority, remote" /></label>
              <n-button type="primary" :loading="store.isSaving" @click="saveTracking">Save Notes</n-button>
            </aside>
          </div>

          <section class="saved-job-primary-next-step workspace-panel">
            <div><h2>Continue with this opportunity</h2><p>Turn the current evidence gaps into a focused preparation plan.</p></div>
            <n-button type="primary" :loading="store.isSaving" @click="openPreparation">
              {{ preparation ? "Continue Preparation" : "Start Preparation" }}
            </n-button>
          </section>
        </n-tab-pane>

        <n-tab-pane name="preparation" tab="Preparation">
          <section class="workspace-panel preparation-workspace">
            <div class="panel-heading">
              <div><h2>Interview Preparation</h2><p>Close knowledge gaps and develop truthful evidence for this role.</p></div>
              <n-button secondary :loading="store.isSaving" @click="generatePreparation">{{ preparationButtonLabel }}</n-button>
            </div>
            <p v-if="!preparation" class="flow-message">Start preparation to identify skill gaps, resources, and evidence questions.</p>
            <template v-else>
              <div class="preparation-status-row">
                <n-tag :type="preparation.status === 'completed' ? 'success' : 'warning'" round>{{ preparation.status }}</n-tag>
                <span v-if="preparation.resource_warning" class="flow-meta">{{ preparation.resource_warning }}</span>
              </div>

              <section class="preparation-stage">
                <h3>1. Skill and evidence gaps</h3>
                <div class="preparation-gap-grid">
                  <article v-for="gap in preparation.skill_gaps" :key="gap.skill" class="preparation-gap-item">
                    <div class="job-card-header"><strong>{{ gap.skill }}</strong><n-tag size="small">{{ gap.evidence_status }}</n-tag></div>
                    <p>{{ gap.rationale }}</p>
                    <small class="flow-meta">{{ gap.jd_evidence }}</small>
                  </article>
                </div>
              </section>

              <section v-if="preparation.learning_resources.length" class="preparation-stage">
                <h3>2. Learning resources</h3>
                <div class="learning-resource-list">
                  <a v-for="resource in preparation.learning_resources" :key="resource.url" :href="resource.url" target="_blank" rel="noreferrer">
                    <strong>{{ resource.title }}</strong><span>{{ resource.source }} · {{ resource.reason }}</span>
                  </a>
                </div>
              </section>

              <section v-if="preparation.questions.length" class="preparation-stage">
                <h3>3. Evidence questions</h3>
                <div class="saved-job-editor preparation-questions">
                  <label v-for="question in preparation.questions" :key="question.question_id" class="draft-field">
                    <span>{{ question.prompt }}</span>
                    <small class="flow-meta">{{ question.why_asked }}</small>
                    <n-input v-model:value="preparationAnswers[question.question_id]" type="textarea" :rows="3" placeholder="Describe a truthful example, or state that you do not have one." />
                  </label>
                </div>
                <div class="flow-toolbar-secondary">
                  <n-button secondary @click="showExternalExchange = !showExternalExchange">Use External Chat</n-button>
                  <n-button type="primary" :loading="store.isSaving" @click="savePreparationAnswers">Save Answers & Create Plan</n-button>
                </div>
                <div v-if="showExternalExchange" class="external-chat-panel">
                  <p class="flow-meta">Export the guided prompt, then import the returned answer JSON.</p>
                  <n-button secondary @click="exportPreparationPrompt">Export for External Chat</n-button>
                  <n-input v-model:value="externalAnswerJson" type="textarea" :rows="3" placeholder='{"answers":[{"question_id":"...","answer":"..."}]}' />
                  <n-button secondary @click="importExternalAnswers">Import External Answers</n-button>
                </div>
              </section>

              <section v-if="preparation.recommendations.length" class="preparation-stage">
                <h3>4. Preparation plan</h3>
                <div class="preparation-action-list">
                  <article v-for="item in preparation.recommendations" :key="item.title">
                    <strong>{{ item.title }}</strong><p>{{ item.action }}</p>
                  </article>
                </div>
              </section>
            </template>
          </section>
        </n-tab-pane>

        <n-tab-pane name="details" tab="Job Details">
          <section class="workspace-panel">
            <div class="panel-heading"><div><h2>Structured Job Description</h2><p>Requirements normalized from the source listing.</p></div></div>
            <dl v-if="structuredEntries.length" class="structured-jd-grid">
              <template v-for="[key, value] in structuredEntries" :key="key"><dt>{{ key.replace(/_/g, " ") }}</dt><dd>{{ formatValue(value) }}</dd></template>
            </dl>
            <p v-else class="flow-message">No structured fields are available.</p>
          </section>
          <n-collapse class="saved-job-raw-jd">
            <n-collapse-item title="Raw job description" name="raw-jd"><p class="saved-job-jd">{{ job.raw_jd_text }}</p></n-collapse-item>
          </n-collapse>
        </n-tab-pane>

        <n-tab-pane name="activity" tab="Activity">
          <section class="workspace-panel">
            <div class="panel-heading"><div><h2>Activity and Versions</h2><p>Status changes and generated analysis retained for reference.</p></div></div>
            <n-collapse>
              <n-collapse-item :title="`Status history (${store.selectedJobStatusHistory.length})`" name="status-history">
                <p v-if="!store.selectedJobStatusHistory.length" class="flow-message">No status changes recorded.</p>
                <div v-else class="status-history-list">
                  <div v-for="event in store.selectedJobStatusHistory" :key="event.saved_job_status_event_id" class="status-history-item">
                    <div><strong>{{ event.to_status }}</strong><span v-if="event.from_status" class="flow-meta"> from {{ event.from_status }}</span></div>
                    <div class="status-history-meta"><span>{{ formatDate(event.changed_at) }}</span><span v-if="event.reason">{{ event.reason }}</span></div>
                  </div>
                </div>
              </n-collapse-item>

              <n-collapse-item :title="`Analysis versions (${store.selectedJobAnalyses.length})`" name="analysis-history">
                <div v-if="!store.selectedJobAnalyses.length" class="flow-message">No analysis snapshots saved.</div>
                <n-collapse v-else>
                  <n-collapse-item v-for="analysis in store.selectedJobAnalyses" :key="analysis.saved_job_analysis_id" :name="analysis.saved_job_analysis_id">
                    <template #header>{{ formatDate(analysis.created_at) }} · Score {{ analysis.match_score ?? "—" }} · {{ analysis.analysis_mode }}</template>
                    <p v-if="analysis.recommendation">{{ analysis.recommendation }}</p>
                    <div class="decision-columns compact">
                      <div><h3>Strengths</h3><ul class="review-list"><li v-for="item in analysis.matched_strengths" :key="item">{{ item }}</li></ul></div>
                      <div><h3>Gaps</h3><ul class="review-list"><li v-for="item in analysis.critical_gaps" :key="item">{{ item }}</li></ul></div>
                      <div><h3>Actions</h3><ul class="review-list"><li v-for="item in analysis.resume_actions" :key="item">{{ item }}</li></ul></div>
                    </div>
                    <n-button v-if="analysis.source_job_search_run_id" size="small" secondary @click="router.push({ name: 'job-search', params: { runId: analysis.source_job_search_run_id } })">View Original Search</n-button>
                  </n-collapse-item>
                </n-collapse>
              </n-collapse-item>

              <n-collapse-item :title="`Decision snapshot versions (${store.selectedJobBriefs.length})`" name="brief-history">
                <div v-for="brief in store.selectedJobBriefs" :key="brief.job_brief_id" class="status-history-item">
                  <div><strong>Version {{ brief.version }}</strong><p>{{ brief.content.decision_summary }}</p></div>
                  <span class="flow-meta">{{ formatDate(brief.created_at) }}</span>
                </div>
              </n-collapse-item>
            </n-collapse>
          </section>
        </n-tab-pane>
      </n-tabs>
    </template>
  </section>
</template>
