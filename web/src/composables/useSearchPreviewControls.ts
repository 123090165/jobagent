import { computed, nextTick, ref, type ComputedRef } from "vue";

import {
  legacySelectedSearchSources,
  normalizeProviderSearchSources,
  sameProviderSearchSources,
  uniqueProviderSearchSources,
  type ProviderSearchSource,
  type SearchSource
} from "../services/jobSearchSources";
import {
  useProfileSessionStore,
  type JobSearchPreviewControls
} from "../stores/profileSession";
import type {
  CreateJobSearchRunPayload,
  JobSearchPreview,
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
  const isRestoringPreviewControls = ref(false);

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

  async function restorePreviewControls(): Promise<boolean> {
    const controls = profileSessionStore.jobSearchPreviewControls;
    if (!controls || controls.sessionId !== sessionId.value) {
      return false;
    }
    isRestoringPreviewControls.value = true;
    try {
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
      await nextTick();
      return true;
    } finally {
      isRestoringPreviewControls.value = false;
    }
  }

  function canReuseStoredPreview(): boolean {
    const preview = profileSessionStore.jobSearchPreview;
    if (!preview || preview.session_id !== sessionId.value) {
      return false;
    }
    const payload = buildPayload();
    return (
      preview.search_mode === payload.search_mode &&
      preview.search_provider === expectedStoredPreviewProvider(payload) &&
      preview.analysis_mode === payload.analysis_mode &&
      preview.llm_enabled === (payload.analysis_mode === "llm") &&
      preview.llm_provider ===
        (payload.analysis_mode === "llm" ? payload.llm_provider : null) &&
      sameProviderSearchSources(
        normalizeProviderSearchSources(preview.selected_sources ?? []),
        payload.selected_sources ?? []
      )
    );
  }

  function providerSourcesForRun(preview: JobSearchPreview | null): ProviderSearchSource[] {
    const previewSources = normalizeProviderSearchSources(preview?.selected_sources ?? []);
    const savedSources = normalizeProviderSearchSources(
      profileSessionStore.jobSearchPreviewControls?.selectedProviderSearchSources ??
        legacySelectedSearchSources(profileSessionStore.jobSearchPreviewControls)
    );
    return uniqueProviderSearchSources([
      ...providerSearchSources.value,
      ...previewSources,
      ...savedSources
    ]);
  }

  return {
    selectedProviderSearchSources,
    isBossSourceSelected,
    useLocalDemo,
    useLlmAnalysis,
    selectedLlmProvider,
    maxResults,
    isRestoringPreviewControls,
    selectedSearchSources,
    providerSearchSources,
    canStartSearch,
    effectiveMaxResults,
    effectiveAnalysisMode,
    effectiveLlmProvider,
    buildPayload,
    saveCurrentPreviewControls,
    restorePreviewControls,
    canReuseStoredPreview,
    providerSourcesForRun
  };
}

function expectedStoredPreviewProvider(payload: CreateJobSearchRunPayload): string | null {
  if (payload.search_mode === "local_mock") {
    return "mock";
  }
  const selectedSources = normalizeProviderSearchSources(payload.selected_sources ?? []);
  if (selectedSources.length === 1) {
    return selectedSources[0];
  }
  if (selectedSources.length > 1) {
    return `multi_source:${selectedSources.join(",")}`;
  }
  return payload.search_provider ?? null;
}
