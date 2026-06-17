<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NTag } from "naive-ui";

import StepProgress from "../components/StepProgress.vue";
import { useProfileSessionStore } from "../stores/profileSession";

const route = useRoute();
const router = useRouter();
const profileSessionStore = useProfileSessionStore();
const runId = computed(() => String(route.params.runId ?? ""));
const jobBriefHint = ref<string | null>(null);

onMounted(async () => {
  jobBriefHint.value = null;
  try {
    await profileSessionStore.loadJobSearchRun(runId.value);
  } catch {
    // Error state is rendered from the store.
  }
});

function goBackToConfirmed() {
  const sessionId = profileSessionStore.session?.session_id;
  if (!sessionId) {
    void router.push({ name: "home" });
    return;
  }
  void router.push({ name: "profile-confirmed", params: { sessionId } });
}

function showJobBriefHint() {
  jobBriefHint.value = "Job Brief will be implemented in v4.6.";
}
</script>

<template>
  <section class="flow-page">
    <h1>Job Search Results</h1>
    <p class="flow-message">
      Review deterministic local/mock job results generated from the confirmed profile.
    </p>
    <p class="flow-meta">Run {{ runId }}</p>
    <StepProgress :active-index="2" />

    <div v-if="profileSessionStore.error" class="error-banner">
      {{ profileSessionStore.error }}
    </div>

    <div v-if="profileSessionStore.isJobSearchLoading && !profileSessionStore.jobSearchRun" class="review-empty-state">
      <p class="flow-message">Loading local job search results...</p>
    </div>

    <div v-else-if="!profileSessionStore.jobSearchRun" class="review-empty-state">
      <p class="flow-message">
        This job search run could not be loaded. Return to the confirmed profile and start a new
        local/mock search.
      </p>
      <n-button type="primary" @click="goBackToConfirmed">Back to Confirmed Profile</n-button>
    </div>

    <div v-else class="job-search-layout">
      <div class="review-actions">
        <n-button secondary @click="goBackToConfirmed">Back to Confirmed Profile</n-button>
      </div>

      <n-card title="Search Context" size="small" class="job-search-summary">
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
      </n-card>

      <p v-if="jobBriefHint" class="flow-meta">{{ jobBriefHint }}</p>

      <div class="job-card-grid">
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
            <n-tag type="success" round>{{ result.match_score }}</n-tag>
          </div>

          <p class="job-card-description">{{ result.description }}</p>

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
