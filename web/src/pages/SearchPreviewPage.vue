<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NCheckbox, NCheckboxGroup, NSwitch, NTag } from "naive-ui";

import StepProgress from "../components/StepProgress.vue";
import { useProfileSessionStore } from "../stores/profileSession";
import type { CreateJobSearchRunPayload, JobSearchRun } from "../types/profileSession";

type SearchSource = "cuhksz_career" | "linkedin" | "remoteok";

const route = useRoute();
const router = useRouter();
const profileSessionStore = useProfileSessionStore();
const sessionId = computed(() => String(route.params.sessionId ?? ""));
const selectedSearchSources = ref<SearchSource[]>(["cuhksz_career"]);
const useLocalDemo = ref(false);
const useLlm = ref(false);
const maxResults = ref(10);
const selectedLlmProvider = computed(() => (useLlm.value ? "deepseek" : "ollama"));
const canStartSearch = computed(() => useLocalDemo.value || selectedSearchSources.value.length > 0);

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
  if (useLocalDemo.value) {
    return "Local demo provider ready";
  }
  const selected = selectedSearchSources.value.join(", ") || "none";
  const status = profileSessionStore.jobSearchProviderStatus;
  if (!status) {
    return `Selected sources: ${selected}`;
  }
  if (status.provider === "multi_source") {
    if (status.configured) {
      return `Selected sources: ${selected}${status.reason ? ` - ${status.reason}` : ""}`;
    }
    return `Provider unavailable${status.reason ? ` - ${status.reason}` : ""}`;
  }
  if (status.provider === "mock") {
    return "Local demo provider ready";
  }
  if (status.provider === "serper_web") {
    if (status.configured) {
      return `Web search ready${status.search_url ? ` - ${status.search_url}` : ""}`;
    }
    return `Web search unavailable${status.reason ? ` - ${status.reason}` : ""}`;
  }
  if (status.configured) {
    return `CUHKSZ Career ready${status.search_url ? ` • ${status.search_url}` : ""}`;
  }
  return `CUHKSZ Career unavailable${status.reason ? ` • ${status.reason}` : ""}`;
});

function buildPayload(): CreateJobSearchRunPayload {
  return {
    session_id: sessionId.value,
    search_mode: useLocalDemo.value ? "local_mock" : "live_search",
    search_provider: useLocalDemo.value ? "mock" : "multi_source",
    selected_sources: useLocalDemo.value ? [] : selectedSearchSources.value,
    use_llm: useLocalDemo.value ? false : useLlm.value,
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
    await profileSessionStore.loadJobSearchProviderStatus(useLocalDemo.value ? "mock" : "multi_source");
    await refreshPreview();
  } catch {
    // Error state is rendered from the store.
  }
});

watch(selectedSearchSources, async () => {
  try {
    await profileSessionStore.loadJobSearchProviderStatus(useLocalDemo.value ? "mock" : "multi_source");
    await refreshPreview();
  } catch {
    // Error state is rendered from the store.
  }
}, { deep: true });

watch(useLocalDemo, async (value) => {
  if (value) {
    useLlm.value = false;
  }
  try {
    await profileSessionStore.loadJobSearchProviderStatus(value ? "mock" : "multi_source");
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
          :disabled="!profileSessionStore.jobSearchPreview || !canStartSearch"
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
            <span class="job-search-setup-label">Recruiting Websites</span>
            <n-checkbox-group v-model:value="selectedSearchSources" :disabled="useLocalDemo">
              <n-checkbox value="cuhksz_career">CUHKSZ Career</n-checkbox>
              <n-checkbox value="linkedin">LinkedIn</n-checkbox>
              <n-checkbox value="remoteok">RemoteOK</n-checkbox>
            </n-checkbox-group>
          </div>

          <div class="job-search-setup-row">
            <span class="job-search-setup-label">Use Local Demo</span>
            <n-switch v-model:value="useLocalDemo" />
          </div>

          <div class="job-search-setup-row">
            <span class="job-search-setup-label">Use DeepSeek API for analysis</span>
            <n-switch v-model:value="useLlm" :disabled="useLocalDemo" />
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
            <n-tag round>{{ profileSessionStore.jobSearchPreview.search_source_kind }}</n-tag>
            <span>
              Query: {{ profileSessionStore.jobSearchPreview.query }}
            </span>
          </div>
          <p>
            <strong>Selected Sources:</strong>
            {{ profileSessionStore.jobSearchPreview.selected_sources.join(", ") || "None" }}
          </p>
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

        <n-card title="Recall And Ranking Plan" size="small" class="job-search-summary">
          <div class="confirmed-grid">
            <div>
              <strong>Recall Queries</strong>
              <ul class="review-list">
                <li
                  v-for="query in profileSessionStore.jobSearchPreview.recall_queries"
                  :key="query"
                >
                  {{ query }}
                </li>
              </ul>
            </div>
            <div>
              <strong>Ranking Signals</strong>
              <div class="job-chip-row">
                <n-tag
                  v-for="signal in profileSessionStore.jobSearchPreview.ranking_signals"
                  :key="signal"
                  size="small"
                  round
                >
                  {{ signal }}
                </n-tag>
              </div>
            </div>
          </div>
          <ul
            v-if="profileSessionStore.jobSearchPreview.search_source_notes.length"
            class="review-list"
          >
            <li
              v-for="note in profileSessionStore.jobSearchPreview.search_source_notes"
              :key="note"
            >
              {{ note }}
            </li>
          </ul>
        </n-card>

        <n-card
          v-if="profileSessionStore.jobSearchPreview.search_intent"
          title="Search Intent"
          size="small"
          class="job-search-summary"
        >
          <div class="confirmed-grid">
            <div>
              <strong>Role Titles</strong>
              <div class="job-chip-row">
                <n-tag
                  v-for="item in profileSessionStore.jobSearchPreview.search_intent.role_titles"
                  :key="item"
                  size="small"
                  round
                >
                  {{ item }}
                </n-tag>
              </div>
            </div>
            <div>
              <strong>Role Families</strong>
              <div class="job-chip-row">
                <n-tag
                  v-for="item in profileSessionStore.jobSearchPreview.search_intent.role_families"
                  :key="item"
                  size="small"
                  round
                >
                  {{ item }}
                </n-tag>
              </div>
            </div>
            <div>
              <strong>Industry Domains</strong>
              <div class="job-chip-row">
                <n-tag
                  v-for="item in profileSessionStore.jobSearchPreview.search_intent.industry_domains"
                  :key="item"
                  size="small"
                  round
                >
                  {{ item }}
                </n-tag>
              </div>
            </div>
            <div>
              <strong>Evidence Skills</strong>
              <div class="job-chip-row">
                <n-tag
                  v-for="item in profileSessionStore.jobSearchPreview.search_intent.evidence_skills"
                  :key="item"
                  size="small"
                  round
                >
                  {{ item }}
                </n-tag>
              </div>
            </div>
            <div>
              <strong>Generic Tools</strong>
              <div class="job-chip-row">
                <n-tag
                  v-for="item in profileSessionStore.jobSearchPreview.search_intent.generic_tools"
                  :key="item"
                  size="small"
                  round
                >
                  {{ item }}
                </n-tag>
              </div>
            </div>
            <div>
              <strong>Constraints</strong>
              <p>{{ profileSessionStore.jobSearchPreview.search_intent.constraints.join(", ") || "None" }}</p>
            </div>
          </div>
        </n-card>

        <n-card title="Query Budget" size="small" class="job-search-summary">
          <div class="confirmed-grid">
            <div>
              <strong>Provider query groups</strong>
              <p>{{ profileSessionStore.jobSearchPreview.provider_query_count }}</p>
            </div>
            <div>
              <strong>Estimated provider requests</strong>
              <p>{{ profileSessionStore.jobSearchPreview.estimated_provider_requests }}</p>
            </div>
            <div>
              <strong>Candidate pool cap</strong>
              <p>{{ profileSessionStore.jobSearchPreview.estimated_candidate_pool_size }}</p>
            </div>
            <div>
              <strong>Estimated LLM requests</strong>
              <p>{{ profileSessionStore.jobSearchPreview.estimated_total_llm_requests }}</p>
            </div>
          </div>
          <p class="flow-meta">
            Planning {{ profileSessionStore.jobSearchPreview.estimated_llm_planning_requests }},
            filtering {{ profileSessionStore.jobSearchPreview.estimated_llm_filtering_requests }},
            JD analysis {{ profileSessionStore.jobSearchPreview.estimated_llm_analysis_requests }}
          </p>
          <ul
            v-if="profileSessionStore.jobSearchPreview.query_strategy_notes.length"
            class="review-list"
          >
            <li
              v-for="note in profileSessionStore.jobSearchPreview.query_strategy_notes"
              :key="note"
            >
              {{ note }}
            </li>
          </ul>
        </n-card>

        <div class="confirmed-grid">
          <n-card title="Provider Search Terms" size="small">
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

          <n-card title="Provider Search URLs" size="small">
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
