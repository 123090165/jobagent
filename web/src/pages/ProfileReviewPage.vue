<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NCode, NCollapse, NCollapseItem, NSwitch, NTag, NThing } from "naive-ui";

import StepProgress from "../components/StepProgress.vue";
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
const analysisModeLabel = computed(() => {
  if (!parsedReview.value) {
    return "Not analyzed";
  }
  if (parsedReview.value.analysis_mode === "llm") {
    return "LLM-assisted parser";
  }
  if (parsedReview.value.analysis_mode === "fallback") {
    return "Fallback parser";
  }
  return "Deterministic parser";
});
const analysisModeTagType = computed(() => {
  if (parsedReview.value?.analysis_mode === "llm") {
    return "success";
  }
  if (parsedReview.value?.analysis_mode === "fallback") {
    return "warning";
  }
  return "default";
});

function formatEducationItem(item: Record<string, unknown>): string {
  const parts = [item.school, item.degree, item.major].filter(
    (value): value is string => typeof value === "string" && value.length > 0
  );
  const rawText = typeof item.raw_text === "string" ? item.raw_text : "";
  return parts.join(" · ") || rawText || "Education entry";
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
  } catch {
    // Error state is rendered from the store.
  }
});

async function analyzeResume(regenerate = false) {
  try {
    await profileSessionStore.analyzeResume(sessionId.value, regenerate, useLlmResumeAnalysis.value);
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
    <h1>Profile Review</h1>
    <p class="flow-message">
      Review how JobAgent understands your resume before we move on to profile drafting.
    </p>
    <p class="flow-meta">Session {{ sessionId }}</p>
    <StepProgress :active-index="1" />

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
      <div class="review-actions">
        <div class="job-search-setup-row">
          <span class="job-search-setup-label">Use LLM-assisted resume analysis</span>
          <n-switch v-model:value="useLlmResumeAnalysis" />
        </div>
        <n-button
          type="primary"
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
        <n-button
          tertiary
          :disabled="!parsedReview"
          :loading="profileSessionStore.isDraftLoading"
          @click="continueToDraft"
        >
          Continue to Profile Draft
        </n-button>
      </div>

      <div v-if="!parsedReview" class="review-empty-state">
        <p class="flow-message">
          Resume received. Click Analyze Resume to generate the first ParsedResumeReview.
        </p>
      </div>

      <div v-else class="review-grid">
        <n-card title="Analysis Mode" size="small">
          <div class="job-search-status-copy">
            <n-tag :type="analysisModeTagType" round>{{ analysisModeLabel }}</n-tag>
          </div>
          <ul v-if="parsedReview.analysis_warnings.length" class="review-list">
            <li v-for="warning in parsedReview.analysis_warnings" :key="warning">
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
