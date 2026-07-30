/**
 * 保存并恢复搜索来源、模型和数量等页面控件，兼容旧缓存字段。
 */
import { computed, ref, type ComputedRef } from "vue";

import {
  legacySelectedSearchSources,
  normalizeProviderSearchSources,
  type ProviderSearchSource,
  type SearchSource
} from "../services/jobSearchSources";
import {
  useProfileSessionStore,
  type JobSearchPreviewControls
} from "../stores/profileSession";
import type {
  CreateJobSearchRunPayload,
  LlmProviderName
} from "../types/profileSession";

export function useSearchPreviewControls(sessionId: ComputedRef<string>) {
  const profileSessionStore = useProfileSessionStore();
  const selectedProviderSearchSources = ref<ProviderSearchSource[]>(["cuhksz_career"]);
  const isBossSourceSelected = ref(false);
  const useLocalDemo = ref(false);
  const useLlmAnalysis = ref(true);
  const selectedLlmProvider = ref<LlmProviderName>("deepseek");
  const maxResults = ref<number | null>(10);

  const selectedSearchSources = computed<SearchSource[]>(() => [
    ...selectedProviderSearchSources.value,
    ...(isBossSourceSelected.value ? (["boss"] as const) : [])
  ]);
  const providerSearchSources = computed<ProviderSearchSource[]>(() => [
    ...selectedProviderSearchSources.value
  ]);
  const canStartSearch = computed(
    () => useLocalDemo.value || selectedSearchSources.value.length > 0
  );
  const effectiveMaxResults = computed(() => maxResults.value ?? 10);
  const effectiveAnalysisMode = computed(() =>
    useLocalDemo.value || !useLlmAnalysis.value ? "deterministic" : "llm"
  );
  const effectiveLlmProvider = computed<LlmProviderName | null>(() =>
    effectiveAnalysisMode.value === "llm" ? selectedLlmProvider.value : null
  );

  function buildPayload(): CreateJobSearchRunPayload {
    const selectedProviderSources = providerSearchSources.value;
    return {
      session_id: sessionId.value,
      search_mode: useLocalDemo.value ? "local_mock" : "live_search",
      search_provider: useLocalDemo.value
        ? "mock"
        : isBossSourceSelected.value && selectedProviderSources.length === 0
          ? "browser_helper"
          : "multi_source",
      selected_sources: useLocalDemo.value ? [] : selectedProviderSources,
      analysis_mode: effectiveAnalysisMode.value,
      llm_provider: effectiveLlmProvider.value,
      use_llm: effectiveLlmProvider.value === "deepseek",
      max_results: effectiveMaxResults.value
    };
  }

  function saveCurrentPreviewControls(): void {
    const controls: JobSearchPreviewControls = {
      sessionId: sessionId.value,
      selectedProviderSearchSources: normalizeProviderSearchSources(
        selectedProviderSearchSources.value
      ),
      isBossSourceSelected: isBossSourceSelected.value,
      useLocalDemo: useLocalDemo.value,
      useLlm: effectiveLlmProvider.value === "deepseek",
      useLlmAnalysis: useLocalDemo.value ? false : useLlmAnalysis.value,
      llmProvider: selectedLlmProvider.value,
      maxResults: maxResults.value
    };
    profileSessionStore.saveJobSearchPreviewControls(controls);
  }

  function restorePreviewControls(): boolean {
    const controls = profileSessionStore.jobSearchPreviewControls;
    if (!controls || controls.sessionId !== sessionId.value) {
      return false;
    }
    const legacySources = legacySelectedSearchSources(controls);
    selectedProviderSearchSources.value = normalizeProviderSearchSources(
      controls.selectedProviderSearchSources ?? legacySources
    );
    isBossSourceSelected.value = Boolean(
      controls.isBossSourceSelected || legacySources.includes("boss")
    );
    useLocalDemo.value = controls.useLocalDemo;
    useLlmAnalysis.value = controls.useLocalDemo
      ? false
      : controls.useLlmAnalysis ?? true;
    selectedLlmProvider.value =
      controls.llmProvider ?? (controls.useLlm ? "deepseek" : "ollama");
    maxResults.value = controls.maxResults;
    return true;
  }

  return {
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
  };
}
