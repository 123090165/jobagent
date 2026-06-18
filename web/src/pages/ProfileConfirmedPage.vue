<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NRadioButton, NRadioGroup, NSwitch, NTag } from "naive-ui";

import StepProgress from "../components/StepProgress.vue";
import { useProfileSessionStore } from "../stores/profileSession";
import type { CreateJobSearchRunPayload } from "../types/profileSession";

type SearchSource = "cuhksz_career" | "mock";

const route = useRoute();
const router = useRouter();
const profileSessionStore = useProfileSessionStore();
const sessionId = computed(() => String(route.params.sessionId ?? ""));
const sessionUnavailable = computed(
  () => profileSessionStore.hasLoadedSession && !profileSessionStore.session
);

const selectedSearchSource = ref<SearchSource>("cuhksz_career");
const useLlm = ref(false);
const maxResults = ref(10);

const llmStatusLabel = computed(() => {
  if (profileSessionStore.isLlmStatusLoading) {
    return "Checking LLM provider...";
  }
  if (!profileSessionStore.llmStatus) {
    return "LLM status unavailable.";
  }
  const { provider, configured, model, reason } = profileSessionStore.llmStatus;
  if (configured) {
    return `${provider}${model ? ` • ${model}` : ""}`;
  }
  return `${provider} unavailable${reason ? ` • ${reason}` : ""}`;
});

const providerStatusLabel = computed(() => {
  const status = profileSessionStore.jobSearchProviderStatus;
  if (!status) {
    return "Provider status unavailable.";
  }
  if (status.provider === "mock") {
    return "Local demo provider ready";
  }
  if (status.configured) {
    return `CUHKSZ Career ready${status.search_url ? ` • ${status.search_url}` : ""}`;
  }
  return `CUHKSZ Career unavailable${status.reason ? ` • ${status.reason}` : ""}`;
});

onMounted(async () => {
  try {
    const session = await profileSessionStore.loadSession(sessionId.value);
    if (session.confirmed_profile_id) {
      await profileSessionStore.loadConfirmedProfile(session.confirmed_profile_id);
    }
    await profileSessionStore.loadLlmStatus();
    await profileSessionStore.loadJobSearchProviderStatus(selectedSearchSource.value);
  } catch {
    // Error state is rendered from the store.
  }
});

watch(selectedSearchSource, async (value) => {
  try {
    await profileSessionStore.loadJobSearchProviderStatus(value);
  } catch {
    // Error state is rendered from the store.
  }
});

function goBackToDraft() {
  void router.push({ name: "profile-draft", params: { sessionId: sessionId.value } });
}

async function startJobSearch() {
  if (!profileSessionStore.session?.confirmed_profile_id) {
    return;
  }
  try {
    const payload: CreateJobSearchRunPayload = {
      session_id: sessionId.value,
      search_mode: selectedSearchSource.value === "mock" ? "local_mock" : "live_search",
      search_provider: selectedSearchSource.value === "mock" ? "mock" : "cuhksz_career",
      use_llm: selectedSearchSource.value === "mock" ? false : useLlm.value,
      max_results: maxResults.value
    };
    const run = await profileSessionStore.createJobSearch(payload);
    await router.push({ name: "job-search", params: { runId: run.job_search_run_id } });
  } catch {
    // Error state is rendered from the store.
  }
}
</script>

<template>
  <section class="flow-page">
    <h1>Profile Confirmed</h1>
    <p class="flow-message">
      Review the final confirmed profile, choose between the CUHKSZ live board and the local demo path, and launch the next job search run.
    </p>
    <p class="flow-meta">Session {{ sessionId }}</p>
    <StepProgress :active-index="2" />

    <div v-if="profileSessionStore.error" class="error-banner">
      {{ profileSessionStore.error }}
    </div>

    <div v-if="sessionUnavailable" class="review-empty-state">
      <p class="flow-message">
        This profile session could not be loaded. Start from Resume Intake to create a new session.
      </p>
      <n-button type="primary" @click="goBackToDraft">Back to Draft</n-button>
    </div>

    <div v-else-if="!profileSessionStore.session?.confirmed_profile_id" class="review-empty-state">
      <p class="flow-message">
        This session does not have a confirmed profile yet. Confirm the draft first.
      </p>
      <n-button type="primary" @click="goBackToDraft">Back to Draft</n-button>
    </div>

    <div v-else class="confirmed-layout">
      <div class="review-actions">
        <n-button secondary @click="goBackToDraft">Back to Draft</n-button>
        <n-button
          type="primary"
          :disabled="!profileSessionStore.confirmedProfile"
          :loading="profileSessionStore.isJobSearchCreating"
          @click="startJobSearch"
        >
          Start Job Search
        </n-button>
      </div>

      <div
        v-if="profileSessionStore.isConfirmedLoading && !profileSessionStore.confirmedProfile"
        class="review-empty-state"
      >
        <p class="flow-message">Loading confirmed profile...</p>
      </div>

      <template v-else-if="profileSessionStore.confirmedProfile">
        <n-card title="Job Search Setup" size="small" class="job-search-setup-card">
          <div class="job-search-setup">
            <div class="job-search-setup-row">
              <span class="job-search-setup-label">Search Source</span>
              <n-radio-group v-model:value="selectedSearchSource">
                <n-radio-button value="cuhksz_career">CUHKSZ Career</n-radio-button>
                <n-radio-button value="mock">Local Demo</n-radio-button>
              </n-radio-group>
            </div>

            <div class="job-search-setup-row">
              <span class="job-search-setup-label">Use LLM-assisted analysis</span>
              <n-switch
                v-model:value="useLlm"
                :disabled="selectedSearchSource === 'mock'"
              />
            </div>

            <div class="job-search-setup-row">
              <span class="job-search-setup-label">Provider Status</span>
              <div class="job-search-status-copy">
                <n-tag
                  :type="profileSessionStore.jobSearchProviderStatus?.configured ? 'success' : 'warning'"
                  round
                >
                  {{ profileSessionStore.jobSearchProviderStatus?.configured ? "Configured" : "Fallback Ready" }}
                </n-tag>
                <span>{{ providerStatusLabel }}</span>
              </div>
            </div>

            <div class="job-search-setup-row">
              <span class="job-search-setup-label">LLM Status</span>
              <div class="job-search-status-copy">
                <n-tag
                  :type="profileSessionStore.llmStatus?.configured ? 'success' : 'warning'"
                  round
                >
                  {{ profileSessionStore.llmStatus?.configured ? "Configured" : "Fallback Ready" }}
                </n-tag>
                <span>{{ llmStatusLabel }}</span>
              </div>
            </div>

            <p class="flow-meta">
              Current live provider: CUHKSZ Career at `https://career.cuhk.edu.cn/job/search`. No login, captcha handling, or anti-bot bypassing is used.
            </p>
          </div>
        </n-card>

        <div class="confirmed-grid">
          <n-card title="Summary" size="small">
            <p class="confirmed-summary">{{ profileSessionStore.confirmedProfile.summary }}</p>
          </n-card>

          <n-card title="Target Roles" size="small">
            <ul class="review-list">
              <li v-for="role in profileSessionStore.confirmedProfile.target_roles" :key="role">
                {{ role }}
              </li>
            </ul>
          </n-card>

          <n-card title="Target Directions" size="small">
            <ul class="review-list">
              <li
                v-for="direction in profileSessionStore.confirmedProfile.target_directions"
                :key="direction"
              >
                {{ direction }}
              </li>
            </ul>
          </n-card>

          <n-card title="Core Skills" size="small">
            <ul class="review-list inline">
              <li v-for="skill in profileSessionStore.confirmedProfile.core_skills" :key="skill">
                {{ skill }}
              </li>
            </ul>
          </n-card>

          <n-card title="Supporting Skills" size="small">
            <ul class="review-list inline">
              <li
                v-for="skill in profileSessionStore.confirmedProfile.supporting_skills"
                :key="skill"
              >
                {{ skill }}
              </li>
            </ul>
          </n-card>

          <n-card title="Search Keywords" size="small">
            <ul class="review-list inline">
              <li
                v-for="keyword in profileSessionStore.confirmedProfile.search_keywords"
                :key="keyword"
              >
                {{ keyword }}
              </li>
            </ul>
          </n-card>

          <n-card title="Preferences" size="small">
            <p>
              <strong>Preferred Locations:</strong>
              {{ profileSessionStore.confirmedProfile.preferred_locations.join(", ") || "Not set" }}
            </p>
            <p>
              <strong>Work Arrangements:</strong>
              {{ profileSessionStore.confirmedProfile.work_arrangements.join(", ") || "Not set" }}
            </p>
          </n-card>

          <n-card title="Strengths" size="small">
            <ul class="review-list">
              <li v-for="strength in profileSessionStore.confirmedProfile.strengths" :key="strength">
                {{ strength }}
              </li>
            </ul>
          </n-card>

          <n-card title="Risks" size="small">
            <ul class="review-list">
              <li v-for="risk in profileSessionStore.confirmedProfile.risks" :key="risk">
                {{ risk }}
              </li>
            </ul>
          </n-card>
        </div>
      </template>
    </div>
  </section>
</template>
