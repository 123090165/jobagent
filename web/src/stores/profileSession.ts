import { defineStore } from "pinia";
import { AxiosError } from "axios";

import {
  confirmProfileDraft,
  createJobSearchRun,
  createProfileDraft,
  createProfileSession,
  getConfirmedProfile,
  getJobSearchProviderStatus,
  getJobSearchRun,
  getJobSearchRunSteps,
  getLlmStatus,
  getParsedResumeReview,
  getProfileDraft,
  getProfileSession,
  listJobSearchRuns,
  parseResumeForReview,
  submitResumeFile,
  submitResumeText,
  updateProfileDraft
} from "../api/profileSessions";
import type {
  CreateJobSearchRunPayload,
  ConfirmedProfile,
  JobSearchProviderStatus,
  JobSearchRun,
  JobSearchTraceStep,
  LlmStatus,
  ParsedResumeReview,
  ProfileDraft,
  ProfileSession,
  ResumeDocument,
  UpdateProfileDraftPayload
} from "../types/profileSession";

interface ProfileSessionState {
  session: ProfileSession | null;
  resumeDocument: ResumeDocument | null;
  parsedReview: ParsedResumeReview | null;
  profileDraft: ProfileDraft | null;
  confirmedProfile: ConfirmedProfile | null;
  jobSearchRun: JobSearchRun | null;
  jobSearchRuns: JobSearchRun[];
  jobSearchSteps: JobSearchTraceStep[];
  jobSearchProviderStatus: JobSearchProviderStatus | null;
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
  isJobSearchPolling: boolean;
  isLlmStatusLoading: boolean;
  hasLoadedSession: boolean;
  error: string | null;
  jobSearchPollTimer: number | null;
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
    jobSearchProviderStatus: null,
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
    isJobSearchPolling: false,
    isLlmStatusLoading: false,
    hasLoadedSession: false,
    error: null,
    jobSearchPollTimer: null
  }),
  actions: {
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
        this.jobSearchRun = null;
        this.jobSearchRuns = [];
        this.jobSearchSteps = [];
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
        this.parsedReview = null;
        this.profileDraft = null;
        this.confirmedProfile = null;
        this.jobSearchRun = null;
        this.jobSearchRuns = [];
        this.jobSearchSteps = [];
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
        this.parsedReview = null;
        this.profileDraft = null;
        this.confirmedProfile = null;
        this.jobSearchRun = null;
        this.jobSearchRuns = [];
        this.jobSearchSteps = [];
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
    async analyzeResume(sessionId: string, regenerate = false): Promise<ParsedResumeReview> {
      this.isReviewLoading = true;
      this.error = null;
      try {
        const response = await parseResumeForReview(sessionId, regenerate);
        this.session = response.profile_session;
        this.parsedReview = response.parsed_review;
        this.profileDraft = null;
        this.confirmedProfile = null;
        this.jobSearchRun = null;
        this.jobSearchRuns = [];
        this.jobSearchSteps = [];
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
        this.confirmedProfile = null;
        this.jobSearchRun = null;
        this.jobSearchRuns = [];
        this.jobSearchSteps = [];
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
        this.confirmedProfile = null;
        this.jobSearchRun = null;
        this.jobSearchRuns = [];
        this.jobSearchSteps = [];
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
    async loadLlmStatus(): Promise<LlmStatus> {
      this.isLlmStatusLoading = true;
      this.error = null;
      try {
        this.llmStatus = await getLlmStatus();
        return this.llmStatus;
      } catch (error) {
        this.llmStatus = null;
        this.error = toApiErrorMessage(error, "Failed to load LLM status.");
        throw error;
      } finally {
        this.isLlmStatusLoading = false;
      }
    },
    async loadJobSearchProviderStatus(
      provider?: "mock" | "cuhksz_career"
    ): Promise<JobSearchProviderStatus> {
      this.error = null;
      try {
        this.jobSearchProviderStatus = await getJobSearchProviderStatus(provider);
        return this.jobSearchProviderStatus;
      } catch (error) {
        this.jobSearchProviderStatus = null;
        this.error = toApiErrorMessage(error, "Failed to load job search provider status.");
        throw error;
      }
    },
    async createJobSearch(
      payload: CreateJobSearchRunPayload
    ): Promise<JobSearchRun> {
      this.isJobSearchCreating = true;
      this.error = null;
      try {
        const response = await createJobSearchRun(payload);
        this.session = response.profile_session;
        this.jobSearchRun = response.job_search_run;
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
    async loadJobSearchRun(runId: string): Promise<JobSearchRun> {
      this.isJobSearchLoading = true;
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
    async pollJobSearchRun(runId: string): Promise<void> {
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
