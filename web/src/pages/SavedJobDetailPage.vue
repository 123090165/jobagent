<script setup lang="ts">
/**
 * 职位工作台：查看 JD/分析，生成 Brief，完成准备问答或打开 Assistant。
 */
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCollapse, NCollapseItem, NInput, NModal, NRadio, NRadioGroup, NSelect, NTabPane, NTabs, NTag } from "naive-ui";

import AppIcon from "../components/AppIcon.vue";
import { createChatConversation } from "../api/chat";
import { useSavedJobsStore } from "../stores/savedJobs";
import type { PreparationAnswer, PreparationQuestion, SavedJobStatus } from "../types/savedJob";

const route = useRoute();
const router = useRouter();
const store = useSavedJobsStore();
const savedJobId = computed(() => String(route.params.savedJobId ?? ""));
const activeTab = ref("overview");
const status = ref<SavedJobStatus>("saved");
const notes = ref("");
const tagsText = ref("");
const actionMessage = ref<string | null>(null);
const preparationDialogOpen = ref(false);
const currentPreparationQuestion = ref(0);
const preparationAnswers = ref<Record<string, PreparationAnswer>>({});
const openingAssistant = ref(false);
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
const skillTags = computed(() => {
  const structured = job.value?.structured_jd ?? {};
  const sources = [structured.skills, structured.skill_tags, structured.technologies, structured.tech_stack];
  const values = sources.flatMap((value) => Array.isArray(value) ? value : typeof value === "string" ? value.split(/,|\n/) : []);
  return [...new Set([...(job.value?.tags ?? []), ...values.map(String)])].map((item) => item.trim()).filter(Boolean);
});
const interviewChecklist = computed(() => latestBrief.value?.content.interview_focus || latestAnalysis.value?.interview_questions || []);
const activeQuestion = computed(() => preparation.value?.questions[currentPreparationQuestion.value] ?? null);
const answeredQuestionCount = computed(() => Object.keys(preparationAnswers.value).length);
const canCompletePreparation = computed(() =>
  Boolean(preparation.value?.questions.length) &&
  preparation.value!.questions.every((question) => isAnswerComplete(question))
);
const activeAnswer = computed(() => activeQuestion.value
  ? preparationAnswers.value[activeQuestion.value.question_id]
  : undefined
);
const activeOption = computed(() => activeQuestion.value?.options.find(
  (item) => item.option_id === activeAnswer.value?.selected_option_id
) ?? null);
const hasPendingFollowUp = computed(() => Object.values(preparationAnswers.value).some(
  (answer) => Boolean(answer.pending_prompt) && ["ask_evidence", "clarify"].includes(answer.route ?? "")
));

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

async function askAssistantAboutJob() {
  if (!job.value || openingAssistant.value) return;
  openingAssistant.value = true;
  actionMessage.value = null;
  try {
    const conversation = await createChatConversation({
      title: `Discuss ${job.value.title}`.slice(0, 120),
      data_scope: {
        resume_profile_id: job.value.latest_analysis?.resume_profile_id ?? null,
        saved_job_ids: [job.value.saved_job_id]
      }
    });
    await router.push({
      name: "assistant",
      query: { conversation: conversation.conversation_id }
    });
  } catch {
    actionMessage.value = "Could not open an assistant conversation for this job.";
  } finally {
    openingAssistant.value = false;
  }
}

function syncPreparationAnswers() {
  preparationAnswers.value = Object.fromEntries(
    (store.selectedPreparation?.answers ?? [])
      .filter((item) => item.experience_level || item.free_text)
      .map((item) => {
        if (item.response_mode === "option" && !item.selected_option_id && item.experience_level) {
          const question = store.selectedPreparation?.questions.find(
            (candidate) => candidate.question_id === item.question_id
          );
          const option = question?.options.find((candidate) => candidate.value === item.experience_level);
          return [item.question_id, { ...item, selected_option_id: option?.option_id ?? null }];
        }
        return [item.question_id, item];
      })
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
    currentPreparationQuestion.value = 0;
    preparationDialogOpen.value = true;
    actionMessage.value = "Preparation session started.";
  } catch {
    // Store error is rendered above.
  }
}

function updateSelectedOption(optionId: string) {
  if (!activeQuestion.value) return;
  const option = activeQuestion.value.options.find((item) => item.option_id === optionId);
  if (!option) return;
  const existing = preparationAnswers.value[activeQuestion.value.question_id];
  preparationAnswers.value[activeQuestion.value.question_id] = {
    question_id: activeQuestion.value.question_id,
    response_mode: "option",
    selected_option_id: option.option_id,
    experience_level: option.value,
    free_text: null,
    detail: option.detail_policy === "not_needed" ? null : existing?.detail ?? null,
    detail_quality: "not_provided",
    follow_up_count: existing?.selected_option_id === option.option_id ? existing?.follow_up_count ?? 0 : 0,
    pending_prompt: null
  };
}

function useFreeText() {
  if (!activeQuestion.value) return;
  const existing = preparationAnswers.value[activeQuestion.value.question_id];
  preparationAnswers.value[activeQuestion.value.question_id] = {
    question_id: activeQuestion.value.question_id,
    response_mode: "free_text",
    selected_option_id: null,
    experience_level: null,
    free_text: existing?.free_text ?? "",
    detail: null,
    detail_quality: "not_provided",
    follow_up_count: existing?.response_mode === "free_text" ? existing?.follow_up_count ?? 0 : 0,
    pending_prompt: null
  };
}

function updateFreeText(value: string) {
  if (!activeQuestion.value) return;
  const existing = preparationAnswers.value[activeQuestion.value.question_id];
  if (!existing) return;
  preparationAnswers.value[activeQuestion.value.question_id] = {
    ...existing,
    free_text: value,
    selected_option_id: null,
    experience_level: null,
    evidence_transition: null,
    route: null,
    resolution_source: null,
    detail_quality: "not_provided"
  };
}

function isAnswerComplete(question: PreparationQuestion): boolean {
  const answer = preparationAnswers.value[question.question_id];
  if (!answer) return false;
  if (answer.response_mode === "free_text") return Boolean(answer.free_text?.trim());
  if (!answer.selected_option_id) return false;
  if (answer.follow_up_count && answer.route === "ask_evidence") return Boolean(answer.detail?.trim());
  return true;
}

function updateAnswerDetail(value: string) {
  if (!activeQuestion.value) return;
  const existing = preparationAnswers.value[activeQuestion.value.question_id];
  if (!existing) return;
  preparationAnswers.value[activeQuestion.value.question_id] = {
    ...existing,
    detail: value
  };
}

async function submitPreparation(action: "save" | "complete" | "stop") {
  if (!job.value || !preparation.value) return;
  const answers = Object.values(preparationAnswers.value).map((answer) => ({
    ...answer,
    detail: answer.detail?.trim() || null,
    free_text: answer.free_text?.trim() || null
  }));
  if (!answers.length) {
    if (action !== "stop") {
      actionMessage.value = "Choose at least one option before saving.";
      return;
    }
  }
  try {
    const updated = await store.savePreparationAnswers(job.value.saved_job_id, answers, action);
    if (action === "complete" && updated.status === "paused") {
      syncPreparationAnswers();
      const pendingIndex = updated.questions.findIndex((question) => {
        const answer = updated.answers.find((item) => item.question_id === question.question_id);
        return Boolean(answer?.pending_prompt) && ["ask_evidence", "clarify"].includes(answer?.route ?? "");
      });
      currentPreparationQuestion.value = pendingIndex >= 0 ? pendingIndex : 0;
      preparationDialogOpen.value = true;
      actionMessage.value = "One or more answers need a focused follow-up before the summary can be created.";
      return;
    }
    preparationDialogOpen.value = false;
    activeTab.value = "preparation";
    actionMessage.value = action === "complete"
      ? "Preparation completed and summary created."
      : action === "save" ? "Preparation paused. You can continue later." : "Preparation ended without a summary.";
  } catch {
    // Store error is rendered above.
  }
}

async function advancePreparation() {
  if (!job.value || !activeQuestion.value || !activeAnswer.value) return;
  const questionId = activeQuestion.value.question_id;
  const answer = {
    ...activeAnswer.value,
    detail: activeAnswer.value.detail?.trim() || null,
    free_text: activeAnswer.value.free_text?.trim() || null
  };
  try {
    const updated = await store.savePreparationAnswers(
      job.value.saved_job_id,
      [answer],
      "advance"
    );
    syncPreparationAnswers();
    const resolved = updated.answers.find((item) => item.question_id === questionId);
    if (updated.status === "paused" && resolved?.pending_prompt) {
      actionMessage.value = "Add the focused detail requested for this answer before continuing.";
      return;
    }
    currentPreparationQuestion.value = Math.min(
      currentPreparationQuestion.value + 1,
      updated.questions.length - 1
    );
    actionMessage.value = null;
  } catch {
    // Store error is rendered above.
  }
}

function openPreparation() {
  if (!preparation.value || preparation.value.status === "completed" || preparation.value.status === "stopped") {
    void generatePreparation();
    return;
  }
  syncPreparationAnswers();
  currentPreparationQuestion.value = Math.min(
    preparation.value.questions.findIndex((question) => !preparationAnswers.value[question.question_id]),
    preparation.value.questions.length - 1
  );
  if (currentPreparationQuestion.value < 0) currentPreparationQuestion.value = 0;
  preparationDialogOpen.value = true;
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString();
}

function formatValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(", ") || "Not set";
  if (value && typeof value === "object") return JSON.stringify(value);
  return String(value ?? "Not set");
}

function preparationResource(url: string) {
  return preparation.value?.learning_resources.find((item) => item.url === url);
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
      <header class="saved-job-workspace-header detail-hero">
        <n-button text @click="router.push({ name: 'saved-jobs' })">← Saved Jobs</n-button>
        <div class="saved-job-workspace-title">
          <div>
            <p class="flow-kicker">Saved opportunity</p>
            <h1>{{ job.title }}</h1>
            <p>{{ job.company || "Unknown company" }} · {{ job.location || "Location not set" }}</p>
          </div>
          <div class="saved-job-header-actions">
            <span class="status-pill">{{ job.status }}</span>
            <n-select v-model:value="status" :options="statusOptions" @update:value="saveTracking" />
            <n-button secondary :loading="openingAssistant" @click="askAssistantAboutJob">
              <AppIcon name="chat" /> Ask Assistant
            </n-button>
            <n-button v-if="job.source_url" tag="a" :href="job.source_url" target="_blank" secondary>
              Open Listing
            </n-button>
          </div>
        </div>
        <p v-if="actionMessage" class="flow-meta library-message">{{ actionMessage }}</p>
      </header>

      <n-tabs v-model:value="activeTab" type="line" animated class="saved-job-tabs">
        <n-tab-pane name="overview" tab="Overview">
          <div class="saved-job-overview-grid job-bento-grid">
            <section class="workspace-panel decision-snapshot bento-decision">
              <div class="panel-heading">
                <div><p class="card-kicker"><AppIcon name="sparkles" /> Application decision</p><h2>Is this role worth your time?</h2><p>Recommendation first, match score as supporting evidence.</p></div>
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

            <aside class="workspace-panel saved-job-tracking-panel bento-tracking">
              <div class="panel-heading"><div><p class="card-kicker"><AppIcon name="bookmark" /> Progress</p><h2>Tracking & Notes</h2><p>Private notes and organization.</p></div></div>
              <label class="draft-field"><span>Application status</span><n-select v-model:value="status" :options="statusOptions" /></label>
              <label class="draft-field"><span>Notes</span><n-input v-model:value="notes" type="textarea" :rows="5" /></label>
              <label class="draft-field"><span>Tags</span><n-input v-model:value="tagsText" placeholder="priority, remote" /></label>
              <n-button type="primary" :loading="store.isSaving" @click="saveTracking">Save Notes</n-button>
            </aside>
          </div>

          <section class="workspace-panel bento-requirements">
            <div class="panel-heading"><div><p class="card-kicker"><AppIcon name="note" /> Role requirements</p><h2>What the role asks for</h2></div><n-button size="small" text @click="activeTab = 'details'">View all details</n-button></div>
            <dl v-if="structuredEntries.length" class="requirement-preview">
              <template v-for="[key, value] in structuredEntries.slice(0, 4)" :key="key"><dt>{{ key.replace(/_/g, " ") }}</dt><dd>{{ formatValue(value) }}</dd></template>
            </dl>
            <p v-else class="empty-copy">No structured requirements are available. The original description remains under Job Details.</p>
            <div class="skill-section"><h3>Skills & tags</h3><div v-if="skillTags.length" class="job-chip-row"><n-tag v-for="tag in skillTags" :key="tag" size="small">{{ tag }}</n-tag></div><p v-else class="empty-copy">No skill tags available.</p></div>
          </section>

          <section class="saved-job-primary-next-step workspace-panel bento-next-action">
            <div><h2>Continue with this opportunity</h2><p>Turn the current evidence gaps into a focused preparation plan.</p></div>
            <n-button type="primary" :loading="store.isSaving" @click="openPreparation">
              {{ preparation ? "Continue Preparation" : "Start Preparation" }}
            </n-button>
          </section>

          <section class="workspace-panel bento-interview">
            <div class="panel-heading"><div><p class="card-kicker"><AppIcon name="check" /> Interview checklist</p><h2>Prepare the evidence</h2></div><n-tag v-if="preparation" size="small">{{ preparation.status }}</n-tag></div>
            <ul v-if="interviewChecklist.length" class="checklist"><li v-for="item in interviewChecklist" :key="item"><span><AppIcon name="check" /></span>{{ item }}</li></ul>
            <p v-else class="empty-copy">No interview checklist is available yet. Start preparation to build one from real evidence.</p>
          </section>
        </n-tab-pane>

        <n-tab-pane name="preparation" tab="Preparation">
          <section class="workspace-panel preparation-workspace">
            <div class="panel-heading">
              <div><h2>Interview Preparation</h2><p>Validate your current experience and build a focused preparation plan.</p></div>
              <n-button type="primary" :loading="store.isSaving" @click="openPreparation">
                {{ preparation && !['completed', 'stopped'].includes(preparation.status) ? "Continue" : "Start Preparation" }}
              </n-button>
            </div>
            <p v-if="!preparation" class="flow-message">Start a guided session to review the most important preparation areas.</p>
            <template v-else>
              <div class="preparation-status-row">
                <n-tag :type="preparation.status === 'completed' ? 'success' : 'warning'" round>{{ preparation.status }}</n-tag>
                <span v-if="preparation.resource_warning" class="flow-meta">{{ preparation.resource_warning }}</span>
              </div>

              <section class="preparation-stage">
                <h3>Preparation areas</h3>
                <div class="preparation-gap-grid">
                  <article v-for="gap in preparation.skill_gaps" :key="gap.skill" class="preparation-gap-item">
                    <div class="job-card-header"><strong>{{ gap.skill }}</strong><n-tag size="small">{{ gap.evidence_status }}</n-tag></div>
                    <p>{{ gap.rationale }}</p>
                    <small class="flow-meta">{{ gap.jd_evidence }}</small>
                  </article>
                </div>
              </section>

              <section v-if="preparation.status === 'completed' && preparation.learning_resources.length" class="preparation-stage">
                <h3>Learning resources</h3>
                <div class="learning-resource-list">
                  <a v-for="resource in preparation.learning_resources" :key="resource.url" :href="resource.url" target="_blank" rel="noreferrer">
                    <strong>{{ resource.title }}</strong><span>{{ resource.source }} · {{ resource.reason }}</span>
                  </a>
                </div>
              </section>

              <section v-if="preparation.recommendations.length" class="preparation-stage">
                <h3>Preparation summary</h3>
                <div class="preparation-action-list">
                  <article v-for="item in preparation.recommendations" :key="item.title">
                    <div class="job-card-header"><strong>{{ item.title }}</strong><n-tag size="small">{{ item.action_type.replace(/_/g, ' ') }}</n-tag></div>
                    <p>{{ item.action }}</p>
                    <div v-if="item.resource_urls.length" class="learning-resource-list">
                      <a v-for="url in item.resource_urls" :key="url" :href="url" target="_blank" rel="noreferrer">
                        <strong>{{ preparationResource(url)?.title || 'Linked learning resource' }}</strong>
                        <span>{{ preparationResource(url)?.source || url }}</span>
                      </a>
                    </div>
                  </article>
                </div>
              </section>
              <p v-else-if="preparation.status === 'stopped'" class="flow-message">
                This session ended before enough evidence was collected, so no summary was generated.
              </p>
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

      <n-modal
        v-model:show="preparationDialogOpen"
        preset="card"
        class="preparation-dialog"
        title="Guided Preparation"
        :mask-closable="false"
      >
        <template v-if="preparation && activeQuestion">
          <div class="preparation-dialog-progress">
            <span>Question {{ currentPreparationQuestion + 1 }} of {{ preparation.questions.length }}</span>
            <span>{{ answeredQuestionCount }} answered</span>
          </div>
          <h2>{{ activeQuestion.skill }}</h2>
          <p>{{ activeQuestion.prompt }}</p>
          <small class="flow-meta">{{ activeQuestion.why_asked }}</small>

          <n-radio-group
            :key="activeQuestion.question_id"
            :value="preparationAnswers[activeQuestion.question_id]?.selected_option_id"
            class="preparation-option-list"
            @update:value="updateSelectedOption"
          >
            <n-radio v-for="option in activeQuestion.options" :key="`${activeQuestion.question_id}:${option.option_id}`" :value="option.option_id">
              <span class="preparation-option-copy"><strong>{{ option.label }}</strong><small>{{ option.description }}</small></span>
            </n-radio>
          </n-radio-group>

          <n-button
            v-if="activeQuestion.free_text_allowed && activeAnswer?.response_mode !== 'free_text'"
            text
            @click="useFreeText"
          >None of these fits — explain in my own words</n-button>

          <label v-if="activeAnswer?.response_mode === 'free_text'" class="draft-field">
            <span>Your situation</span>
            <small class="flow-meta">{{ activeAnswer.pending_prompt || activeQuestion.free_text_prompt }}</small>
            <n-input
              :value="activeAnswer.free_text || ''"
              type="textarea"
              :rows="3"
              placeholder="Explain only what the options missed..."
              @update:value="updateFreeText"
            />
          </label>

          <label v-else-if="activeOption && activeOption.detail_policy !== 'not_needed'" class="draft-field">
            <span>{{ activeOption.detail_policy === 'required' ? 'One focused follow-up' : 'Optional clarification' }}</span>
            <small class="flow-meta">{{ activeAnswer?.pending_prompt || activeOption.follow_up_prompt }}</small>
            <n-input
              :value="activeAnswer?.detail || ''"
              type="textarea"
              :rows="3"
              placeholder="Use a truthful, concrete example..."
              @update:value="updateAnswerDetail"
            />
          </label>

          <div class="preparation-dialog-actions">
            <n-button secondary :disabled="currentPreparationQuestion === 0" @click="currentPreparationQuestion--">Previous</n-button>
            <n-button
              v-if="currentPreparationQuestion < preparation.questions.length - 1"
              type="primary"
              :disabled="!isAnswerComplete(activeQuestion)"
              :loading="store.isSaving"
              @click="advancePreparation"
            >Next</n-button>
            <n-button v-else type="primary" :disabled="!canCompletePreparation" :loading="store.isSaving" @click="submitPreparation('complete')">
              {{ hasPendingFollowUp ? "Recheck & Create Summary" : "Finish & Create Summary" }}
            </n-button>
          </div>
        </template>
        <template #footer>
          <div class="preparation-dialog-footer">
            <n-button text @click="submitPreparation('stop')">End without summary</n-button>
            <n-button secondary :loading="store.isSaving" @click="submitPreparation('save')">Save & close</n-button>
          </div>
        </template>
      </n-modal>
    </template>
  </section>
</template>
