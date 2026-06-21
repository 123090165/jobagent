<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NRadioButton, NRadioGroup, NSwitch, NTag } from "naive-ui";

import StepProgress from "../components/StepProgress.vue";
import { useProfileSessionStore } from "../stores/profileSession";
import type { CreateJobSearchRunPayload, JobSearchRun } from "../types/profileSession";

type SearchSource = "cuhksz_career" | "mock";

const route = useRoute();
const router = useRouter();
const profileSessionStore = useProfileSessionStore();
const sessionId = computed(() => String(route.params.sessionId ?? ""));
const selectedSearchSource = ref<SearchSource>("cuhksz_career");
const useLlm = ref(false);
const maxResults = ref(10);
const selectedLlmProvider = computed(() => (useLlm.value ? "deepseek" : "ollama"));

const latestResultRun = computed<JobSearchRun | null>(() => {
  return (
    profileSessionStore.jobSearchRuns.find(
      (run) => run.status === "completed" && run.results.length > 0
    ) ?? null
  );
});

const canSeeResult = computed(() => latestResultRun.value !== null);

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

function buildPayload(): CreateJobSearchRunPayload {
  return {
    session_id: sessionId.value,
    search_mode: selectedSearchSource.value === "mock" ? "local_mock" : "live_search",
    search_provider: selectedSearchSource.value === "mock" ? "mock" : "cuhksz_career",
    use_llm: selectedSearchSource.value === "mock" ? false : useLlm.value,
    max_results: maxResults.value
  };
}

async function refreshPreview() {
  if (!profileSessionStore.session?.confirmed_profile_id) {
    return;
  }
  await profileSessionStore.previewJobSearch(buildPayload());
}

onMounted(async () => {
  try {
    const session = await profileSessionStore.loadSession(sessionId.value);
    if (session.confirmed_profile_id) {
      await profileSessionStore.loadConfirmedProfile(session.confirmed_profile_id);
    }
    await profileSessionStore.loadJobSearchRuns(sessionId.value);
    await profileSessionStore.loadLlmStatus(useLlm.value);
    await profileSessionStore.loadJobSearchProviderStatus(selectedSearchSource.value);
    await refreshPreview();
  } catch {
    // Error state is rendered from the store.
  }
});

watch(selectedSearchSource, async (value) => {
  try {
    await profileSessionStore.loadJobSearchProviderStatus(value);
    await refreshPreview();
  } catch {
    // Error state is rendered from the store.
  }
});

watch(useLlm, async (value) => {
  try {
    await profileSessionStore.loadLlmStatus(value);
    await refreshPreview();
  } catch {
    // Error state is rendered from the store.
  }
});

function goBackToConfirmed() {
  void router.push({ name: "profile-confirmed", params: { sessionId: sessionId.value } });
}

async function startJobSearch() {
  try {
    const run = await profileSessionStore.createJobSearch(buildPayload());
    await router.push({ name: "job-search", params: { runId: run.job_search_run_id } });
  } catch {
    // Error state is rendered from the store.
  }
}

function seeResult() {
  if (!latestResultRun.value) {
    return;
  }
  void router.push({ name: "job-search", params: { runId: latestResultRun.value.job_search_run_id } });
}
</script>

<template>
  <section class="flow-page">
    <h1>Search Preview</h1>
    <p class="flow-message">
      Confirm the search plan before running provider retrieval.
    </p>
    <p class="flow-meta">Session {{ sessionId }}</p>
    <StepProgress :active-index="2" />

    <div v-if="profileSessionStore.error" class="error-banner">
      {{ profileSessionStore.error }}
    </div>

    <div class="confirmed-layout">
      <div class="review-actions">
        <n-button secondary @click="goBackToConfirmed">Back to Confirmed Profile</n-button>
        <n-button
          type="primary"
          :disabled="!profileSessionStore.jobSearchPreview"
          :loading="profileSessionStore.isJobSearchCreating"
          @click="startJobSearch"
        >
          Start Job Search
        </n-button>
        <n-button secondary :disabled="!canSeeResult" @click="seeResult">See Result</n-button>
      </div>

      <n-card title="Search Setup" size="small" class="job-search-setup-card">
        <div class="job-search-setup">
          <div class="job-search-setup-row">
            <span class="job-search-setup-label">Search Source</span>
            <n-radio-group v-model:value="selectedSearchSource">
              <n-radio-button value="cuhksz_career">CUHKSZ Career</n-radio-button>
              <n-radio-button value="mock">Local Demo</n-radio-button>
            </n-radio-group>
          </div>

          <div class="job-search-setup-row">
            <span class="job-search-setup-label">Use DeepSeek API for analysis</span>
            <n-switch v-model:value="useLlm" :disabled="selectedSearchSource === 'mock'" />
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
              <span>{{ selectedLlmProvider }} / {{ llmStatusLabel }}</span>
            </div>
          </div>
        </div>
      </n-card>

      <div
        v-if="profileSessionStore.isJobSearchPreviewLoading && !profileSessionStore.jobSearchPreview"
        class="review-empty-state"
      >
        <p class="flow-message">Loading search preview...</p>
      </div>

      <template v-else-if="profileSessionStore.jobSearchPreview">
        <n-card title="Provider Queries" size="small" class="job-search-summary">
          <div class="job-status-row">
            <n-tag round>{{ profileSessionStore.jobSearchPreview.planning_mode }}</n-tag>
            <span>
              Query: {{ profileSessionStore.jobSearchPreview.query }}
            </span>
          </div>
          <ul class="review-list">
            <li
              v-for="query in profileSessionStore.jobSearchPreview.provider_queries"
              :key="query"
            >
              {{ query }}
            </li>
          </ul>
          <p v-if="profileSessionStore.jobSearchPreview.fallback_reason">
            <strong>Fallback:</strong> {{ profileSessionStore.jobSearchPreview.fallback_reason }}
          </p>
          <p v-if="profileSessionStore.jobSearchPreview.quality_warnings.length">
            <strong>Warnings:</strong>
            {{ profileSessionStore.jobSearchPreview.quality_warnings.join(" • ") }}
          </p>
        </n-card>

        <div class="confirmed-grid">
          <n-card title="CUHKSZ Search Terms" size="small">
            <div class="job-chip-row">
              <n-tag
                v-for="term in profileSessionStore.jobSearchPreview.provider_search_terms"
                :key="term"
                size="small"
                round
              >
                {{ term }}
              </n-tag>
              <span
                v-if="!profileSessionStore.jobSearchPreview.provider_search_terms.length"
                class="flow-meta"
              >
                Not used for this provider.
              </span>
            </div>
          </n-card>

          <n-card title="CUHKSZ Search URLs" size="small">
            <ul class="review-list">
              <li
                v-for="url in profileSessionStore.jobSearchPreview.provider_search_urls"
                :key="url"
              >
                <a :href="url" target="_blank" rel="noreferrer">{{ url }}</a>
              </li>
            </ul>
            <p
              v-if="!profileSessionStore.jobSearchPreview.provider_search_urls.length"
              class="flow-meta"
            >
              Not used for this provider.
            </p>
          </n-card>

          <n-card title="Target Roles" size="small">
            <ul class="review-list">
              <li
                v-for="role in profileSessionStore.jobSearchPreview.target_roles"
                :key="role"
              >
                {{ role }}
              </li>
            </ul>
          </n-card>

          <n-card title="Search Signal Terms" size="small">
            <div class="job-chip-row">
              <n-tag
                v-for="term in profileSessionStore.jobSearchPreview.search_signal_terms"
                :key="term"
                size="small"
                round
              >
                {{ term }}
              </n-tag>
            </div>
          </n-card>

          <n-card title="Locations" size="small">
            <p>
              {{ profileSessionStore.jobSearchPreview.locations.join(", ") || "Not set" }}
            </p>
          </n-card>

          <n-card title="Excluded Signals" size="small">
            <p>
              {{ profileSessionStore.jobSearchPreview.excluded_signals.join(", ") || "None" }}
            </p>
          </n-card>
        </div>
      </template>
    </div>
  </section>
</template>
