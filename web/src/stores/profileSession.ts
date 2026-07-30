/**
 * 保存简历到搜索主流程的前端状态，并负责上游变更失效、run 轮询和页面恢复。
 */
import { defineStore } from "pinia";
import { AxiosError } from "axios";

import {
  confirmProfileDraft,
  createBrowserHelperJobSearchRun,
  createJobSearchRun,
  createProfileDraft,
  createProfileSession,
  deleteJobSearchRun,
  getConfirmedProfile,
  getJobSearchRun,
  getJobSearchRunSteps,
  getLlmStatus,
  getParsedResumeReview,
  getProfileDraft,
  getProfileSession,
  listJobSearchRuns,
  listJobSearchItems,
  listUserJobSearchRuns,
  parseResumeForReview,
  previewJobSearchRun,
  submitResumeFile,
  submitResumeText,
  updateProfileDraft
} from "../api/profileSessions";
import type {
  CreateBrowserHelperJobSearchPayload,
  CreateJobSearchRunPayload,
  ConfirmedProfile,
  JobSearchItem,
  JobSearchPreview,
  JobSearchRun,
  JobSearchTraceStep,
  LlmStatus,
  LlmProviderName,
  ParsedResumeReview,
  ProfileDraft,
  ProfileSession,
  ResumeDocument,
  UpdateProfileDraftPayload
} from "../types/profileSession";
import type { ProviderSearchSource } from "../services/jobSearchSources";

interface ProfileSessionState {
  session: ProfileSession | null;
  resumeDocument: ResumeDocument | null;
  parsedReview: ParsedResumeReview | null;
  profileDraft: ProfileDraft | null;
  confirmedProfile: ConfirmedProfile | null;
  jobSearchRun: JobSearchRun | null;
  jobSearchRuns: JobSearchRun[];
  jobSearchSteps: JobSearchTraceStep[];
  jobSearchItems: JobSearchItem[];
  jobSearchItemTotal: number;
  jobSearchItemsError: string | null;
  llmStatus: LlmStatus | null;
  isCreating: boolean;
  isSubmitting: boolean;
  isReviewLoading: boolean;
  isDraftLoading: boolean;
  isDraftSaving: boolean;
  isConfirming: boolean;
  isConfirmedLoading: boolean;
  isJobSearchCreating: boolean;
  isJobSearchLoading: boolean;
  isJobSearchItemsLoading: boolean;
  isJobSearchPolling: boolean;
  isLlmStatusLoading: boolean;
  hasLoadedSession: boolean;
  error: string | null;
  jobSearchPollTimer: number | null;
  jobSearchPreviewControls: JobSearchPreviewControls | null;
  jobSearchClientStartedAt: number | null;
  jobSearchClientRunId: string | null;
  jobSearchClientStages: JobSearchClientStage[];
}

export interface JobSearchClientStage {
  label: string;
  duration_ms: number;
}

export interface JobSearchPreviewControls {
  sessionId: string;
  selectedProviderSearchSources: ProviderSearchSource[];
  isBossSourceSelected: boolean;
  useLocalDemo: boolean;
  useLlm?: boolean;
  useLlmAnalysis: boolean;
  llmProvider: LlmProviderName;
  maxResults: number | null;
}

interface ApiErrorPayload {
  detail?: string;
}

export const useProfileSessionStore = defineStore("profileSession", {
  state: (): ProfileSessionState => ({
    session: null,
    resumeDocument: null,
    parsedReview: null,
    profileDraft: null,
    confirmedProfile: null,
    jobSearchRun: null,
    jobSearchRuns: [],
    jobSearchSteps: [],
    jobSearchItems: [],
    jobSearchItemTotal: 0,
    jobSearchItemsError: null,
    llmStatus: null,
    isCreating: false,
    isSubmitting: false,
    isReviewLoading: false,
    isDraftLoading: false,
    isDraftSaving: false,
    isConfirming: false,
    isConfirmedLoading: false,
    isJobSearchCreating: false,
    isJobSearchLoading: false,
    isJobSearchItemsLoading: false,
    isJobSearchPolling: false,
    isLlmStatusLoading: false,
    hasLoadedSession: false,
    error: null,
    jobSearchPollTimer: null,
    jobSearchPreviewControls: null,
    jobSearchClientStartedAt: null,
    jobSearchClientRunId: null,
    jobSearchClientStages: []
  }),
  actions: {
    resetJobSearchResults(): void {
      this.jobSearchRun = null;
      this.jobSearchRuns = [];
      this.jobSearchSteps = [];
      this.jobSearchItems = [];
      this.jobSearchItemTotal = 0;
      this.jobSearchItemsError = null;
    },
    resetJobSearchState(): void {
      this.jobSearchPreviewControls = null;
      this.resetJobSearchResults();
    },
    invalidateAfterResumeChange(): void {
      // 简历是整条流程的根输入；替换后不能继续展示任何由旧简历生成的下游状态。
      this.parsedReview = null;
      this.profileDraft = null;
      this.confirmedProfile = null;
      this.resetJobSearchState();
    },
    invalidateAfterReviewChange(): void {
      // 重新解析只使草稿及其后续结果失效，保留用户刚得到的新 review。
      this.profileDraft = null;
      this.confirmedProfile = null;
      this.resetJobSearchResults();
    },
    invalidateAfterDraftChange(): void {
      // 草稿编辑后必须重新确认，旧确认画像和搜索条件都不再可信。
      this.confirmedProfile = null;
      this.resetJobSearchState();
    },
    async createSession(): Promise<ProfileSession> {
      this.isCreating = true;
      this.error = null;

      try {
        this.session = await createProfileSession();
        this.hasLoadedSession = true;
        return this.session;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to create profile session.");
        throw error;
      } finally {
        this.isCreating = false;
      }
    },
    async loadSession(sessionId: string): Promise<ProfileSession> {
      try {
        this.session = await getProfileSession(sessionId);
        this.hasLoadedSession = true;
        this.error = null;
        // 后端 session 是恢复页面时的真相源，本地缓存必须按当前引用主动清空。
        if (this.session.current_step !== "resume_review") {
          this.parsedReview = null;
        }
        if (!this.session.profile_draft_id) {
          this.profileDraft = null;
        }
        if (!this.session.confirmed_profile_id) {
          this.confirmedProfile = null;
        }
        if (!["job_search_running", "job_search_completed"].includes(this.session.current_step)) {
          this.jobSearchRun = null;
          this.jobSearchSteps = [];
        }
        return this.session;
      } catch (error) {
        this.stopPollingJobSearchRun();
        this.session = null;
        this.resumeDocument = null;
        this.parsedReview = null;
        this.profileDraft = null;
        this.confirmedProfile = null;
        this.resetJobSearchState();
        this.error = toApiErrorMessage(error, "Failed to load profile session.");
        throw error;
      }
    },
    async submitTextResume(text: string): Promise<ProfileSession> {
      const session = await this.ensureSession();
      this.isSubmitting = true;
      this.error = null;
      try {
        const response = await submitResumeText(session.session_id, text);
        this.session = response.profile_session;
        this.resumeDocument = response.resume_document;
        this.invalidateAfterResumeChange();
        return response.profile_session;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to submit resume text.");
        throw error;
      } finally {
        this.isSubmitting = false;
      }
    },
    async submitFileResume(file: File): Promise<ProfileSession> {
      const session = await this.ensureSession();
      this.isSubmitting = true;
      this.error = null;
      try {
        const response = await submitResumeFile(session.session_id, file);
        this.session = response.profile_session;
        this.resumeDocument = response.resume_document;
        this.invalidateAfterResumeChange();
        return response.profile_session;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to submit resume file.");
        throw error;
      } finally {
        this.isSubmitting = false;
      }
    },
    async ensureSession(): Promise<ProfileSession> {
      if (this.session) {
        return this.session;
      }
      return this.createSession();
    },
    async loadParsedReview(sessionId: string): Promise<ParsedResumeReview> {
      this.isReviewLoading = true;
      this.error = null;
      try {
        const response = await getParsedResumeReview(sessionId);
        this.session = response.profile_session;
        this.parsedReview = response.parsed_review;
        return response.parsed_review;
      } catch (error) {
        this.parsedReview = null;
        this.error = toApiErrorMessage(error, "Failed to load parsed resume review.");
        throw error;
      } finally {
        this.isReviewLoading = false;
      }
    },
    async analyzeResume(
      sessionId: string,
      regenerate = false,
      useLlm = false
    ): Promise<ParsedResumeReview> {
      this.isReviewLoading = true;
      this.error = null;
      try {
        const response = await parseResumeForReview(sessionId, regenerate, useLlm);
        this.session = response.profile_session;
        this.parsedReview = response.parsed_review;
        this.invalidateAfterReviewChange();
        return response.parsed_review;
      } catch (error) {
        this.parsedReview = null;
        this.error = toApiErrorMessage(error, "Failed to analyze resume.");
        throw error;
      } finally {
        this.isReviewLoading = false;
      }
    },
    async createDraft(sessionId: string, regenerate = false): Promise<ProfileDraft> {
      this.isDraftLoading = true;
      this.error = null;
      try {
        const response = await createProfileDraft(sessionId, regenerate);
        this.session = response.profile_session;
        this.profileDraft = response.profile_draft;
        this.invalidateAfterDraftChange();
        return response.profile_draft;
      } catch (error) {
        this.profileDraft = null;
        this.error = toApiErrorMessage(error, "Failed to create profile draft.");
        throw error;
      } finally {
        this.isDraftLoading = false;
      }
    },
    async loadDraft(draftId: string): Promise<ProfileDraft> {
      this.isDraftLoading = true;
      this.error = null;
      try {
        const response = await getProfileDraft(draftId);
        this.session = response.profile_session;
        this.profileDraft = response.profile_draft;
        return response.profile_draft;
      } catch (error) {
        this.profileDraft = null;
        this.error = toApiErrorMessage(error, "Failed to load profile draft.");
        throw error;
      } finally {
        this.isDraftLoading = false;
      }
    },
    async saveDraft(
      draftId: string,
      payload: UpdateProfileDraftPayload
    ): Promise<ProfileDraft> {
      this.isDraftSaving = true;
      this.error = null;
      try {
        const response = await updateProfileDraft(draftId, payload);
        this.session = response.profile_session;
        this.profileDraft = response.profile_draft;
        this.invalidateAfterDraftChange();
        return response.profile_draft;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to save profile draft.");
        throw error;
      } finally {
        this.isDraftSaving = false;
      }
    },
    async confirmDraft(draftId: string): Promise<ConfirmedProfile> {
      this.isConfirming = true;
      this.error = null;
      try {
        const response = await confirmProfileDraft(draftId);
        this.session = response.profile_session;
        this.confirmedProfile = response.confirmed_profile;
        this.jobSearchPreviewControls = null;
        return response.confirmed_profile;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to confirm profile.");
        throw error;
      } finally {
        this.isConfirming = false;
      }
    },
    async loadConfirmedProfile(confirmedProfileId: string): Promise<ConfirmedProfile> {
      this.isConfirmedLoading = true;
      this.error = null;
      try {
        const response = await getConfirmedProfile(confirmedProfileId);
        this.session = response.profile_session;
        this.confirmedProfile = response.confirmed_profile;
        return response.confirmed_profile;
      } catch (error) {
        this.confirmedProfile = null;
        this.error = toApiErrorMessage(error, "Failed to load confirmed profile.");
        throw error;
      } finally {
        this.isConfirmedLoading = false;
      }
    },
    async loadLlmStatus(provider: LlmProviderName = "deepseek"): Promise<LlmStatus> {
      this.isLlmStatusLoading = true;
      this.error = null;
      try {
        this.llmStatus = await getLlmStatus(provider);
        return this.llmStatus;
      } catch (error) {
        this.llmStatus = null;
        this.error = toApiErrorMessage(error, "Failed to load LLM status.");
        throw error;
      } finally {
        this.isLlmStatusLoading = false;
      }
    },
    prepareNewJobSearch(): void {
      this.stopPollingJobSearchRun();
      this.jobSearchRun = null;
      this.jobSearchSteps = [];
      this.jobSearchItems = [];
      this.jobSearchItemTotal = 0;
      this.jobSearchItemsError = null;
      this.error = null;
    },
    beginJobSearchClientTiming(): void {
      this.jobSearchClientStartedAt = Date.now();
      this.jobSearchClientRunId = null;
      this.jobSearchClientStages = [];
    },
    clearJobSearchClientTiming(): void {
      this.jobSearchClientStartedAt = null;
      this.jobSearchClientRunId = null;
      this.jobSearchClientStages = [];
    },
    addJobSearchClientStage(stage: JobSearchClientStage): void {
      this.jobSearchClientStages = [...this.jobSearchClientStages, stage];
    },
    saveJobSearchPreviewControls(controls: JobSearchPreviewControls): void {
      this.jobSearchPreviewControls = {
        ...controls,
        selectedProviderSearchSources: [...controls.selectedProviderSearchSources]
      };
    },
    async createJobSearch(
      payload: CreateJobSearchRunPayload
    ): Promise<JobSearchRun> {
      this.isJobSearchCreating = true;
      this.prepareNewJobSearch();
      this.error = null;
      try {
        // 接口返回 pending/running run；真正执行由后端 BackgroundTasks 继续推进。
        const response = await createJobSearchRun(payload);
        this.session = response.profile_session;
        this.jobSearchRun = response.job_search_run;
        if (this.jobSearchClientStartedAt !== null) {
          this.jobSearchClientRunId = response.job_search_run.job_search_run_id;
        }
        this.jobSearchSteps = response.steps;
        this.jobSearchRuns = [response.job_search_run, ...this.jobSearchRuns.filter(
          (item) => item.job_search_run_id !== response.job_search_run.job_search_run_id
        )];
        return response.job_search_run;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to start job search.");
        throw error;
      } finally {
        this.isJobSearchCreating = false;
      }
    },
    async createBrowserHelperJobSearch(
      payload: CreateBrowserHelperJobSearchPayload
    ): Promise<JobSearchRun> {
      this.isJobSearchCreating = true;
      this.prepareNewJobSearch();
      this.error = null;
      try {
        // 扩展候选进入后端后仍生成普通 run，结果页不需要维护另一套分析状态。
        const response = await createBrowserHelperJobSearchRun(payload);
        this.session = response.profile_session;
        this.jobSearchRun = response.job_search_run;
        if (this.jobSearchClientStartedAt !== null) {
          this.jobSearchClientRunId = response.job_search_run.job_search_run_id;
        }
        this.jobSearchSteps = response.steps;
        this.jobSearchRuns = [response.job_search_run, ...this.jobSearchRuns.filter(
          (item) => item.job_search_run_id !== response.job_search_run.job_search_run_id
        )];
        return response.job_search_run;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to import browser helper candidates.");
        throw error;
      } finally {
        this.isJobSearchCreating = false;
      }
    },
    async previewJobSearch(
      payload: CreateJobSearchRunPayload
    ): Promise<JobSearchPreview> {
      this.error = null;
      try {
        return await previewJobSearchRun(payload);
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to prepare BOSS search.");
        throw error;
      }
    },
    async loadJobSearchRun(runId: string): Promise<JobSearchRun> {
      this.isJobSearchLoading = true;
      if (this.jobSearchRun?.job_search_run_id !== runId) {
        this.jobSearchItems = [];
        this.jobSearchItemTotal = 0;
        this.jobSearchItemsError = null;
      }
      this.error = null;
      try {
        const response = await getJobSearchRun(runId);
        this.session = response.profile_session;
        this.jobSearchRun = response.job_search_run;
        this.jobSearchSteps = response.steps;
        return response.job_search_run;
      } catch (error) {
        this.jobSearchRun = null;
        this.jobSearchSteps = [];
        this.error = toApiErrorMessage(error, "Failed to load job search run.");
        throw error;
      } finally {
        this.isJobSearchLoading = false;
      }
    },
    async loadJobSearchSteps(runId: string): Promise<JobSearchTraceStep[]> {
      this.error = null;
      try {
        const response = await getJobSearchRunSteps(runId);
        this.jobSearchSteps = response.items;
        return response.items;
      } catch (error) {
        this.jobSearchSteps = [];
        this.error = toApiErrorMessage(error, "Failed to load job search steps.");
        throw error;
      }
    },
    async loadJobSearchItems(runId: string): Promise<JobSearchItem[]> {
      this.isJobSearchItemsLoading = true;
      this.jobSearchItemsError = null;
      try {
        const response = await listJobSearchItems(runId, 100, 0);
        this.jobSearchItems = response.items;
        this.jobSearchItemTotal = response.total;
        return response.items;
      } catch (error) {
        this.jobSearchItems = [];
        this.jobSearchItemTotal = 0;
        this.jobSearchItemsError = toApiErrorMessage(
          error,
          "Candidate pool could not be loaded."
        );
        throw error;
      } finally {
        this.isJobSearchItemsLoading = false;
      }
    },
    async loadJobSearchRuns(sessionId: string): Promise<JobSearchRun[]> {
      this.isJobSearchLoading = true;
      this.error = null;
      try {
        const response = await listJobSearchRuns(sessionId);
        this.jobSearchRuns = response.items;
        return response.items;
      } catch (error) {
        this.jobSearchRuns = [];
        this.error = toApiErrorMessage(error, "Failed to load job search runs.");
        throw error;
      } finally {
        this.isJobSearchLoading = false;
      }
    },
    async loadUserJobSearchRuns(): Promise<JobSearchRun[]> {
      this.isJobSearchLoading = true;
      this.error = null;
      try {
        const response = await listUserJobSearchRuns();
        this.jobSearchRuns = response.items;
        return response.items;
      } catch (error) {
        this.jobSearchRuns = [];
        this.error = toApiErrorMessage(error, "Failed to load search history.");
        throw error;
      } finally {
        this.isJobSearchLoading = false;
      }
    },
    async deleteJobSearchRun(runId: string): Promise<void> {
      this.isJobSearchLoading = true;
      this.error = null;
      try {
        await deleteJobSearchRun(runId);
        this.jobSearchRuns = this.jobSearchRuns.filter(
          (run) => run.job_search_run_id !== runId
        );
        if (this.jobSearchRun?.job_search_run_id === runId) this.jobSearchRun = null;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to delete search history.");
        throw error;
      } finally {
        this.isJobSearchLoading = false;
      }
    },
    async pollJobSearchRun(runId: string): Promise<void> {
      // 使用递归 setTimeout，确保上一轮完成后才发下一轮请求，避免慢请求重叠。
      this.stopPollingJobSearchRun();
      this.isJobSearchPolling = true;

      const tick = async (): Promise<void> => {
        try {
          const response = await getJobSearchRun(runId);
          this.session = response.profile_session;
          this.jobSearchRun = response.job_search_run;
          this.jobSearchSteps = response.steps;
          const status = response.job_search_run.status;
          if (status === "completed" || status === "failed") {
            // 两种终态都必须停止计时器；失败详情由 run 和 trace 提供。
            this.stopPollingJobSearchRun();
            return;
          }
          this.jobSearchPollTimer = window.setTimeout(() => {
            void tick();
          }, 1500);
        } catch (error) {
          this.error = toApiErrorMessage(error, "Failed to poll job search run.");
          this.stopPollingJobSearchRun();
        }
      };

      await tick();
    },
    stopPollingJobSearchRun(): void {
      if (this.jobSearchPollTimer !== null) {
        window.clearTimeout(this.jobSearchPollTimer);
        this.jobSearchPollTimer = null;
      }
      this.isJobSearchPolling = false;
    }
  }
});

function toApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof AxiosError) {
    return (error.response?.data as ApiErrorPayload | undefined)?.detail ?? fallback;
  }
  return error instanceof Error ? error.message : fallback;
}
