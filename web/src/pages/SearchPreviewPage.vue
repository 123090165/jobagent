<script setup lang="ts">
/**
 * 统一搜索设置页面：确认 mission、选择来源，并启动后端或 BOSS 辅助搜索。
 */
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NCard,
  NCheckbox,
  NCheckboxGroup,
  NCollapse,
  NCollapseItem,
  NInputNumber,
  NSelect,
  NSwitch,
  NTag
} from "naive-ui";

import FlowPageHeader from "../components/FlowPageHeader.vue";
import SearchIntentForm from "../components/SearchIntentForm.vue";
import { useBrowserHelperSession } from "../composables/useBrowserHelperSession";
import { useSearchPreviewControls } from "../composables/useSearchPreviewControls";
import {
  BOSS_DEFAULT_JOB_TYPE,
  buildBossSearchQueries,
  formatBossEmptyResultMessage
} from "../services/bossSearchPlanning";
import { fetchBossCandidates } from "../services/browserHelper";
import { useProfileSessionStore } from "../stores/profileSession";
import type {
  JobSearchPreview,
  JobSearchRun,
  LlmProviderName,
  SearchMission
} from "../types/profileSession";

interface SearchIntentFormHandle {
  prepareForSearch(
    useLlm: boolean,
    llmProvider: LlmProviderName
  ): Promise<SearchMission>;
}

const route = useRoute();
const router = useRouter();
const profileSessionStore = useProfileSessionStore();
const sessionId = computed(() => String(route.params.sessionId ?? ""));
const searchIntentForm = ref<SearchIntentFormHandle | null>(null);
const isSearchIntentBusy = ref(true);
const isStartingSearch = ref(false);
const nowMs = ref(Date.now());
let searchElapsedTimer: number | null = null;

const {
  selectedProviderSearchSources,
  isBossSourceSelected,
  useLocalDemo,
  useLlmAnalysis,
  selectedLlmProvider,
  maxResults,
  providerSearchSources,
  canStartSearch,
  effectiveMaxResults,
  effectiveAnalysisMode,
  effectiveLlmProvider,
  buildPayload,
  saveCurrentPreviewControls,
  restorePreviewControls
} = useSearchPreviewControls(sessionId);
const usesBrowserHelper = computed(
  () => isBossSourceSelected.value && !useLocalDemo.value
);

const {
  browserHelperStatus,
  bossLoginStatus,
  browserHelperMessage,
  browserHelperStatusTag,
  bossLoginStatusTag,
  bossLoginStatusSummary,
  checkBrowserHelper,
  checkBossLogin,
  openBossLogin
} = useBrowserHelperSession(usesBrowserHelper);

const llmProviderOptions = [
  { label: "DeepSeek", value: "deepseek" },
  { label: "Ollama", value: "ollama" }
];

const latestResultRun = computed<JobSearchRun | null>(() => (
  profileSessionStore.jobSearchRuns.find(
    (run) => run.status === "completed" && run.results.length > 0
  ) ?? null
));
const canSeeResult = computed(() => latestResultRun.value !== null);
const activeSearchElapsedLabel = computed(() => {
  if (!isStartingSearch.value && !profileSessionStore.isJobSearchCreating) {
    return null;
  }
  const startedAt = profileSessionStore.jobSearchClientStartedAt;
  return startedAt === null ? null : formatDuration(nowMs.value - startedAt);
});

onMounted(async () => {
  startSearchElapsedTicker();
  restorePreviewControls();
  try {
    const session = await profileSessionStore.loadSession(sessionId.value);
    if (session.confirmed_profile_id) {
      await profileSessionStore.loadConfirmedProfile(session.confirmed_profile_id);
    }
    await profileSessionStore.loadJobSearchRuns(sessionId.value);
  } catch {
    // Error state is rendered from the store.
  }
});

onUnmounted(stopSearchElapsedTicker);

function goBackToConfirmed(): void {
  void router.push({
    name: "profile-confirmed",
    params: { sessionId: sessionId.value }
  });
}

async function startJobSearch(): Promise<void> {
  if (!searchIntentForm.value || isStartingSearch.value) {
    return;
  }

  isStartingSearch.value = true;
  saveCurrentPreviewControls();
  try {
    // 先保存、解释并确认 mission；搜索 run 只读取一份确定的意图快照。
    await searchIntentForm.value.prepareForSearch(
      effectiveAnalysisMode.value === "llm",
      selectedLlmProvider.value
    );

    profileSessionStore.beginJobSearchClientTiming();
    profileSessionStore.prepareNewJobSearch();

    if (usesBrowserHelper.value) {
      // BOSS 需要后端预览生成查询，但此时仍不会创建可轮询的 run。
      const preview = await measureSearchStage(
        "Search planning",
        () => profileSessionStore.previewJobSearch(buildPayload())
      );
      await startBrowserHelperJobSearch(preview);
      return;
    }

    const run = await measureSearchStage(
      "Backend start",
      () => profileSessionStore.createJobSearch(buildPayload())
    );
    await router.push({
      name: "job-search",
      params: { runId: run.job_search_run_id }
    });
  } catch {
    profileSessionStore.clearJobSearchClientTiming();
    // Mission and search errors are rendered by their owning store/component.
  } finally {
    isStartingSearch.value = false;
  }
}

async function startBrowserHelperJobSearch(
  preview: JobSearchPreview
): Promise<void> {
  const selectedProviderSources = [...providerSearchSources.value];
  browserHelperMessage.value = null;

  if (!browserHelperStatus.value) {
    // 仅在用户点击 Start 后探测扩展，页面参数变化不会自动触发浏览器操作。
    await measureSearchStage("Helper check", checkBrowserHelper);
  }
  if (!browserHelperStatus.value?.installed) {
    browserHelperMessage.value =
      "Install and detect the Browser Helper before starting BOSS search.";
    return;
  }

  if (!bossLoginStatus.value) {
    await measureSearchStage("BOSS login check", checkBossLogin);
  }
  if (!bossLoginStatus.value?.loggedIn) {
    browserHelperMessage.value =
      "BOSS login is required before starting this search.";
    return;
  }

  const bossQueries = buildBossSearchQueries(preview);
  const result = await measureSearchStage(
    "BOSS capture",
    () => fetchBossCandidates(
      preview.query,
      preview.locations[0] ?? null,
      effectiveMaxResults.value,
      bossQueries,
      BOSS_DEFAULT_JOB_TYPE
    )
  );

  if (!result.candidates.length) {
    browserHelperMessage.value = formatBossEmptyResultMessage(result);
    if (!selectedProviderSources.length) {
      return;
    }
  }

  const run = await measureSearchStage(
    "Backend import",
    () => profileSessionStore.createBrowserHelperJobSearch({
      session_id: sessionId.value,
      query: preview.query,
      helper_version: result.version,
      platforms: ["boss"],
      selected_sources: selectedProviderSources,
      analysis_mode: effectiveAnalysisMode.value,
      llm_provider: effectiveLlmProvider.value,
      use_llm: effectiveLlmProvider.value === "deepseek",
      locations: preview.locations,
      target_roles: preview.target_roles,
      keywords: preview.keywords,
      max_results: effectiveMaxResults.value,
      candidates: result.candidates
    })
  );
  await router.push({
    name: "job-search",
    params: { runId: run.job_search_run_id }
  });
}

async function measureSearchStage<T>(
  label: string,
  action: () => Promise<T>
): Promise<T> {
  const startedAt = Date.now();
  try {
    return await action();
  } finally {
    profileSessionStore.addJobSearchClientStage({
      label,
      duration_ms: Date.now() - startedAt
    });
  }
}

function startSearchElapsedTicker(): void {
  stopSearchElapsedTicker();
  searchElapsedTimer = window.setInterval(() => {
    nowMs.value = Date.now();
  }, 1000);
}

function stopSearchElapsedTicker(): void {
  if (searchElapsedTimer !== null) {
    window.clearInterval(searchElapsedTimer);
    searchElapsedTimer = null;
  }
}

function formatDuration(milliseconds: number): string {
  const totalSeconds = Math.max(0, Math.round(milliseconds / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
}

function seeResult(): void {
  if (latestResultRun.value) {
    void router.push({
      name: "job-search",
      params: { runId: latestResultRun.value.job_search_run_id }
    });
  }
}
</script>

<template>
  <section class="flow-page">
    <FlowPageHeader
      title="New Job Search"
      description="Set the search target and execution options, then start when ready."
      :meta="`Session ${sessionId}`"
      :active-step="1"
    />

    <div v-if="profileSessionStore.error" class="error-banner">
      {{ profileSessionStore.error }}
    </div>

    <div class="confirmed-layout">
      <div class="workspace-panel">
        <div class="panel-heading">
          <div>
            <h2>Ready to search</h2>
            <p>Changes stay local until you start the search.</p>
          </div>
        </div>

        <div class="flow-toolbar">
          <n-button secondary @click="goBackToConfirmed">Back to Profile</n-button>
          <div class="flow-toolbar-secondary">
            <n-button
              secondary
              :disabled="!canSeeResult || isStartingSearch"
              @click="seeResult"
            >
              See Result
            </n-button>
            <n-button
              type="primary"
              :disabled="!canStartSearch || isSearchIntentBusy || isStartingSearch"
              :loading="isSearchIntentBusy || isStartingSearch"
              @click="startJobSearch"
            >
              Start Job Search
            </n-button>
          </div>
        </div>
      </div>

      <SearchIntentForm
        ref="searchIntentForm"
        :session-id="sessionId"
        :profile="profileSessionStore.confirmedProfile"
        @busy-change="isSearchIntentBusy = $event"
      />

      <n-card title="Where and how to search" size="small" class="job-search-setup-card">
        <div class="job-search-setup">
          <div class="job-search-setup-row">
            <span class="job-search-setup-label">Recruiting Websites</span>
            <n-checkbox-group
              v-model:value="selectedProviderSearchSources"
              :disabled="useLocalDemo"
            >
              <n-checkbox value="cuhksz_career">CUHKSZ Career</n-checkbox>
              <n-checkbox value="linkedin">LinkedIn</n-checkbox>
              <n-checkbox value="remoteok">RemoteOK</n-checkbox>
            </n-checkbox-group>
            <n-checkbox
              v-model:checked="isBossSourceSelected"
              :disabled="useLocalDemo"
            >
              BOSS
            </n-checkbox>
          </div>

          <div class="job-search-setup-row">
            <span class="job-search-setup-label">LLM Analysis</span>
            <n-switch v-model:value="useLlmAnalysis" :disabled="useLocalDemo" />
          </div>

          <div
            v-if="useLlmAnalysis && !useLocalDemo"
            class="job-search-setup-row"
          >
            <span class="job-search-setup-label">LLM Provider</span>
            <n-select
              v-model:value="selectedLlmProvider"
              :options="llmProviderOptions"
              size="small"
              class="job-search-provider-select"
            />
          </div>

          <div class="job-search-setup-row">
            <span class="job-search-setup-label">Result Limit</span>
            <n-input-number
              v-model:value="maxResults"
              :min="1"
              :max="50"
              :step="1"
              size="small"
            />
          </div>

          <n-collapse class="job-search-advanced">
            <n-collapse-item title="Advanced execution" name="advanced-execution">
              <div class="job-search-setup-row">
                <span class="job-search-setup-label">Use Local Demo</span>
                <n-switch v-model:value="useLocalDemo" />
              </div>
            </n-collapse-item>
          </n-collapse>

          <template v-if="isBossSourceSelected">
            <p
              v-if="!browserHelperStatus && !browserHelperMessage"
              class="flow-meta"
            >
              Browser Helper and BOSS login will be checked after Start.
            </p>
            <div v-if="browserHelperStatus" class="job-search-setup-row">
              <span class="job-search-setup-label">Helper</span>
              <n-tag
                :type="browserHelperStatus.installed ? 'success' : 'warning'"
                round
              >
                {{ browserHelperStatusTag }}
              </n-tag>
            </div>
            <div v-if="bossLoginStatus" class="job-search-setup-row">
              <span class="job-search-setup-label">BOSS Login</span>
              <div class="job-search-status-copy">
                <n-tag
                  :type="bossLoginStatus.loggedIn ? 'success' : 'warning'"
                  round
                >
                  {{ bossLoginStatusTag }}
                </n-tag>
                <span>{{ bossLoginStatusSummary }}</span>
              </div>
            </div>
            <n-button
              v-if="browserHelperStatus?.installed && !bossLoginStatus?.loggedIn"
              secondary
              @click="openBossLogin"
            >
              Open BOSS Login
            </n-button>
            <p v-if="browserHelperMessage" class="flow-meta">
              {{ browserHelperMessage }}
            </p>
          </template>

          <p v-if="activeSearchElapsedLabel" class="flow-meta">
            Search elapsed: {{ activeSearchElapsedLabel }}
          </p>
          <div
            v-if="profileSessionStore.jobSearchClientStages.length"
            class="job-chip-row"
          >
            <n-tag
              v-for="stage in profileSessionStore.jobSearchClientStages"
              :key="`${stage.label}-${stage.duration_ms}`"
              size="small"
              round
            >
              {{ stage.label }} {{ formatDuration(stage.duration_ms) }}
            </n-tag>
          </div>
        </div>
      </n-card>
    </div>
  </section>
</template>
