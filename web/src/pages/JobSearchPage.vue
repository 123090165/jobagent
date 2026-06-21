<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NTag } from "naive-ui";

import StepProgress from "../components/StepProgress.vue";
import { useProfileSessionStore } from "../stores/profileSession";

const route = useRoute();
const router = useRouter();
const profileSessionStore = useProfileSessionStore();
const runId = computed(() => String(route.params.runId ?? ""));
const jobBriefHint = ref<string | null>(null);

const isRunning = computed(() =>
  ["pending", "running"].includes(profileSessionStore.jobSearchRun?.status ?? "")
);

onMounted(async () => {
  jobBriefHint.value = null;
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
  jobBriefHint.value = "Job Brief will be implemented in v4.6.";
}

function statusTagType(status: string) {
  if (status === "completed") return "success";
  if (status === "failed") return "error";
  if (status === "running") return "warning";
  return "default";
}
</script>

<template>
  <section class="flow-page">
    <h1>Job Search Run</h1>
    <p class="flow-message">
      Follow the live search timeline, wait for analysis to finish, and then review the provider-backed job cards.
    </p>
    <p class="flow-meta">Run {{ runId }}</p>
    <StepProgress :active-index="2" />

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
      <div class="review-actions">
        <n-button secondary @click="goBackToConfirmed">Back to Confirmed Profile</n-button>
        <n-button secondary @click="goBackToSearchPreview">Back to Search Preview</n-button>
      </div>

      <n-card title="Run Status" size="small" class="job-search-summary">
        <div class="job-status-row">
          <n-tag :type="statusTagType(profileSessionStore.jobSearchRun.status)" round>
            {{ profileSessionStore.jobSearchRun.status }}
          </n-tag>
          <span>
            Mode: {{ profileSessionStore.jobSearchRun.search_mode }} • Provider:
            {{ profileSessionStore.jobSearchRun.search_provider || "not set" }}
          </span>
        </div>
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
            <p v-if="step.quality_warnings.length">
              <strong>Warnings:</strong> {{ step.quality_warnings.join(" • ") }}
            </p>
          </div>
        </div>
      </n-card>

      <p v-if="jobBriefHint" class="flow-meta">{{ jobBriefHint }}</p>

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
              <p class="job-card-company">{{ result.company }} · {{ result.location }}</p>
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
              {{ result.source_provider || result.source }}
              <template v-if="result.source_url">
                ·
                <a :href="result.source_url" target="_blank" rel="noreferrer">Open listing</a>
              </template>
            </p>
          </div>

          <div class="job-card-section">
            <strong>Analysis</strong>
            <p>{{ result.analysis_mode }} · {{ result.confidence_label }}</p>
          </div>

          <div class="job-card-section">
            <strong>Matched Keywords</strong>
            <div class="job-chip-row">
              <n-tag v-for="keyword in result.matched_keywords" :key="keyword" size="small" round>
                {{ keyword }}
              </n-tag>
            </div>
          </div>

          <div class="job-card-section">
            <strong>Match Reasons</strong>
            <ul class="review-list">
              <li v-for="reason in result.match_reasons" :key="reason">{{ reason }}</li>
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
            <n-button tertiary size="small" @click="showJobBriefHint">
              Generate Job Brief
            </n-button>
          </div>
        </n-card>
      </div>
    </div>
  </section>
</template>
