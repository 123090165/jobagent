<script setup lang="ts">
/**
 * 展示确定性/LLM 简历审阅结果，并触发画像草稿生成。
 */
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NCode, NCollapse, NCollapseItem, NSwitch, NTag, NThing } from "naive-ui";

import FlowPageHeader from "../components/FlowPageHeader.vue";
import { useProfileSessionStore } from "../stores/profileSession";

const route = useRoute();
const router = useRouter();
const profileSessionStore = useProfileSessionStore();
const sessionId = computed(() => String(route.params.sessionId ?? ""));
const sessionUnavailable = computed(
  () => profileSessionStore.hasLoadedSession && !profileSessionStore.session
);
const hasResume = computed(() => Boolean(profileSessionStore.session?.resume_document_id));
const parsedReview = computed(() => profileSessionStore.parsedReview);
const useLlmResumeAnalysis = ref(false);
const llmStatus = computed(() => profileSessionStore.llmStatus);
const selectedLlmProvider = computed(() => (useLlmResumeAnalysis.value ? "deepseek" : "ollama"));
const llmToggleLabel = computed(() =>
  useLlmResumeAnalysis.value ? "DeepSeek API" : "Local Ollama"
);
const shouldForceLlmRegeneration = computed(
  () =>
    !parsedReview.value ||
    parsedReview.value.analysis_mode !== "llm_guided" ||
    parsedReview.value.analysis_provider !== selectedLlmProvider.value
);
const analysisModeLabel = computed(() => {
  if (!parsedReview.value) {
    return "Not analyzed";
  }
  if (parsedReview.value.analysis_mode === "llm_guided") {
    return "Guided LLM";
  }
  if (parsedReview.value.analysis_mode === "llm") {
    return "LLM-assisted parser";
  }
  if (parsedReview.value.analysis_mode === "fallback") {
    return "Fallback";
  }
  return "Deterministic parser";
});
const analysisModeTagType = computed(() => {
  if (parsedReview.value?.analysis_mode === "llm_guided") {
    return "success";
  }
  if (parsedReview.value?.analysis_mode === "fallback") {
    return "warning";
  }
  return "default";
});
const detectedSectionCount = computed(() => {
  if (!parsedReview.value) {
    return 0;
  }
  return [
    parsedReview.value.education.length,
    parsedReview.value.work_experience.length,
    parsedReview.value.projects.length,
    parsedReview.value.skills.items.length
  ].filter((count) => count > 0).length;
});
const reviewReadinessLabel = computed(() => {
  if (!parsedReview.value) {
    return "Waiting for analysis";
  }
  if (parsedReview.value.quality_warnings.length) {
    return "Needs review";
  }
  return "Ready for draft";
});
const reviewReadinessTagType = computed(() => {
  if (!parsedReview.value) {
    return "default";
  }
  return parsedReview.value.quality_warnings.length ? "warning" : "success";
});

function formatEducationItem(item: Record<string, unknown>): string {
  const parts = [item.school, item.degree, item.major].filter(
    (value): value is string => typeof value === "string" && value.length > 0
  );
  const rawText = typeof item.raw_text === "string" ? item.raw_text : "";
  return parts.join(" - ") || rawText || "Education entry";
}

function formatWorkExperience(item: Record<string, unknown>): string {
  const role = typeof item.role === "string" ? item.role : "";
  const company = typeof item.company === "string" ? item.company : "";
  const description = typeof item.description === "string" ? item.description : "";
  return [role, company].filter(Boolean).join(" @ ") || description || "Work experience entry";
}

function formatProject(item: Record<string, unknown>): string {
  const name = typeof item.name === "string" ? item.name : "";
  const description = typeof item.description === "string" ? item.description : "";
  return name || description || "Project entry";
}

onMounted(async () => {
  try {
    const session = await profileSessionStore.loadSession(sessionId.value);
    if (session.current_step === "resume_review" && session.parsed_review_id) {
      await profileSessionStore.loadParsedReview(sessionId.value);
    }
    await profileSessionStore.loadLlmStatus(selectedLlmProvider.value);
  } catch {
    // Error state is rendered from the store.
  }
});

watch(useLlmResumeAnalysis, async () => {
  try {
    await profileSessionStore.loadLlmStatus(selectedLlmProvider.value);
  } catch {
    // Error state is rendered from the store.
  }
});

async function analyzeResume(regenerate = false) {
  try {
    const shouldRegenerate = regenerate || shouldForceLlmRegeneration.value;
    await profileSessionStore.analyzeResume(
      sessionId.value,
      shouldRegenerate,
      useLlmResumeAnalysis.value
    );
  } catch {
    // Error state is rendered from the store.
  }
}

function goToIntake() {
  void router.push({ name: "home" });
}

async function continueToDraft() {
  try {
    await profileSessionStore.createDraft(sessionId.value, false);
    await router.push({ name: "profile-draft", params: { sessionId: sessionId.value } });
  } catch {
    // Error state is rendered from the store.
  }
}
</script>

<template>
  <section class="flow-page">
    <FlowPageHeader
      title="Profile Review"
      description="Review the parsed resume signal before creating an editable search profile."
      :meta="`Session ${sessionId}`"
      :active-step="0"
    />

    <div v-if="profileSessionStore.error" class="error-banner">
      {{ profileSessionStore.error }}
    </div>

    <div v-if="sessionUnavailable" class="review-empty-state">
      <p class="flow-message">
        This profile session could not be loaded. Start from Resume Intake to create a new session.
      </p>
      <n-button type="primary" @click="goToIntake">Go to Resume Intake</n-button>
    </div>

    <div v-else-if="!hasResume" class="review-empty-state">
      <p class="flow-message">
        This session does not have a resume yet. Go back to Resume Intake and submit a txt,
        md, or pasted resume first.
      </p>
      <n-button type="primary" @click="goToIntake">Back to Resume Intake</n-button>
    </div>

    <div v-else class="review-layout">
      <div class="workspace-panel">
        <div class="panel-heading">
          <div>
            <h2>Analysis setup</h2>
            <p>Parser mode and downstream draft handoff.</p>
          </div>
          <n-tag :type="reviewReadinessTagType" round>{{ reviewReadinessLabel }}</n-tag>
        </div>

        <div class="setup-grid">
          <div class="setting-row">
            <span class="setting-label">DeepSeek resume analysis</span>
            <div class="setting-control">
              <n-switch v-model:value="useLlmResumeAnalysis" />
              <span>{{ llmToggleLabel }}</span>
            </div>
          </div>
          <div class="setting-row">
            <span class="setting-label">Provider status</span>
            <div class="job-search-status-copy">
              <n-tag :type="llmStatus?.configured ? 'success' : 'warning'" round>
                {{ llmStatus?.configured ? "Configured" : "Fallback Ready" }}
              </n-tag>
              <span>{{ selectedLlmProvider }}</span>
            </div>
          </div>
        </div>

        <div class="flow-toolbar">
          <div class="flow-toolbar-secondary">
            <n-button
              :type="parsedReview ? 'default' : 'primary'"
              :loading="profileSessionStore.isReviewLoading"
              @click="analyzeResume(false)"
            >
              Analyze Resume
            </n-button>
            <n-button
              secondary
              :disabled="!parsedReview"
              :loading="profileSessionStore.isReviewLoading"
              @click="analyzeResume(true)"
            >
              Regenerate Review
            </n-button>
          </div>
          <n-button
            type="primary"
            :disabled="!parsedReview"
            :loading="profileSessionStore.isDraftLoading"
            @click="continueToDraft"
          >
            Continue to Profile Draft
          </n-button>
        </div>
      </div>

      <div v-if="!parsedReview" class="review-empty-state">
        <p class="flow-message">
          Resume received. Click Analyze Resume to generate the first ParsedResumeReview.
        </p>
      </div>

      <template v-else>
        <div class="metric-grid">
          <div class="metric-card">
            <span>Detected sections</span>
            <strong>{{ detectedSectionCount }}/4</strong>
          </div>
          <div class="metric-card">
            <span>Skills</span>
            <strong>{{ parsedReview.skills.count }}</strong>
          </div>
          <div class="metric-card">
            <span>Warnings</span>
            <strong>{{ parsedReview.quality_warnings.length }}</strong>
          </div>
          <div class="metric-card">
            <span>Questions</span>
            <strong>{{ parsedReview.missing_info_questions.length }}</strong>
          </div>
        </div>

        <div class="review-grid">
          <n-card title="Analysis Mode" size="small">
          <div class="job-search-status-copy">
            <n-tag :type="analysisModeTagType" round>{{ analysisModeLabel }}</n-tag>
          </div>
          <ul class="review-list">
            <li>LLM toggle: {{ llmToggleLabel }}</li>
            <li>Selected LLM provider: {{ selectedLlmProvider }}</li>
            <li v-if="parsedReview.analysis_provider">
              Review provider: {{ parsedReview.analysis_provider }}
            </li>
            <li v-if="llmStatus">
              Provider: {{ llmStatus.provider }}
              <span v-if="llmStatus.model"> / {{ llmStatus.model }}</span>
            </li>
            <li v-if="llmStatus">
              LLM configured: {{ llmStatus.configured ? "yes" : "no" }}
            </li>
            <li v-if="llmStatus?.reason">LLM status: {{ llmStatus.reason }}</li>
            <li v-if="shouldForceLlmRegeneration">
              Next analysis will regenerate so LLM can run against the current resume.
            </li>
          </ul>
          <ul v-if="parsedReview.analysis_warnings.length" class="review-list">
            <li v-for="warning in parsedReview.analysis_warnings" :key="warning">
              <span v-if="parsedReview.analysis_mode === 'fallback'">Reason: </span>
              {{ warning }}
            </li>
          </ul>
        </n-card>

        <n-card title="Basic Info" size="small">
          <n-thing>
            <p><strong>Name:</strong> {{ parsedReview.basic_info.name || "Not detected" }}</p>
            <p>
              <strong>Highlights:</strong>
              {{ (parsedReview.basic_info.highlights || []).join(", ") || "None yet" }}
            </p>
            <p>
              <strong>Certificates:</strong>
              {{ (parsedReview.basic_info.certificates || []).join(", ") || "None detected" }}
            </p>
          </n-thing>
        </n-card>

        <n-card title="Education" size="small">
          <ul class="review-list">
            <li v-for="(item, index) in parsedReview.education" :key="`edu-${index}`">
              {{ formatEducationItem(item) }}
            </li>
            <li v-if="parsedReview.education.length === 0">No education entries detected.</li>
          </ul>
        </n-card>

        <n-card title="Work Experience" size="small">
          <ul class="review-list">
            <li v-for="(item, index) in parsedReview.work_experience" :key="`work-${index}`">
              {{ formatWorkExperience(item) }}
            </li>
            <li v-if="parsedReview.work_experience.length === 0">
              No work experience entries detected.
            </li>
          </ul>
        </n-card>

        <n-card title="Projects" size="small">
          <ul class="review-list">
            <li v-for="(item, index) in parsedReview.projects" :key="`project-${index}`">
              {{ formatProject(item) }}
            </li>
            <li v-if="parsedReview.projects.length === 0">No projects detected.</li>
          </ul>
        </n-card>

        <n-card title="Skills" size="small">
          <p class="review-stat">{{ parsedReview.skills.count }} detected skills</p>
          <ul class="review-list inline">
            <li v-for="skill in parsedReview.skills.items" :key="skill">{{ skill }}</li>
            <li v-if="parsedReview.skills.items.length === 0">No explicit skills detected.</li>
          </ul>
        </n-card>

        <n-card title="Target Signals" size="small">
          <ul class="review-list">
            <li v-for="signal in parsedReview.target_signals" :key="signal">{{ signal }}</li>
            <li v-if="parsedReview.target_signals.length === 0">No target signals detected yet.</li>
          </ul>
        </n-card>

        <n-card title="Quality Warnings" size="small">
          <ul class="review-list">
            <li v-for="warning in parsedReview.quality_warnings" :key="warning">{{ warning }}</li>
            <li v-if="parsedReview.quality_warnings.length === 0">No major quality warnings.</li>
          </ul>
        </n-card>

        <n-card title="Missing Info Questions" size="small">
          <ul class="review-list">
            <li v-for="question in parsedReview.missing_info_questions" :key="question">
              {{ question }}
            </li>
            <li v-if="parsedReview.missing_info_questions.length === 0">
              No follow-up questions right now.
            </li>
          </ul>
          </n-card>
        </div>
      </template>

      <n-collapse v-if="parsedReview?.raw_parser_output" class="review-debug">
        <n-collapse-item title="Raw parser output" name="raw-parser-output">
          <n-code
            :code="JSON.stringify(parsedReview.raw_parser_output, null, 2)"
            language="json"
            word-wrap
          />
        </n-collapse-item>
      </n-collapse>
    </div>
  </section>
</template>
