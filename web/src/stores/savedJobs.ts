import { defineStore } from "pinia";
import { AxiosError } from "axios";

import {
  archiveSavedJob,
  approveTailoredResume,
  createJobApplication,
  createSavedJob,
  deleteSavedJob,
  getSavedJobWorkspace,
  generateTailoredResume,
  generateJobBrief,
  generateInterviewPreparation,
  getInterviewPreparation,
  listJobBriefs,
  submitPreparationAnswers,
  listSavedJobs,
  listSavedJobAnalyses,
  saveJobFromSearchResult,
  updateJobApplication,
  updateTailoredResume,
  updateSavedJob
} from "../api/savedJobs";
import type {
  SavedJob,
  JobBrief,
  InterviewPreparationWorkspace,
  PreparationAnswer,
  SavedJobAnalysis,
  ApplicationEvent,
  ApplicationStage,
  CommunicationDraft,
  JobApplication,
  TailoredResumeVersion,
  SavedJobCreatePayload,
  SavedJobFromSearchResultPayload,
  SavedJobUpdatePayload
} from "../types/savedJob";

interface SavedJobState {
  jobs: SavedJob[];
  selectedJob: SavedJob | null;
  selectedApplication: JobApplication | null;
  selectedCommunicationDraft: CommunicationDraft | null;
  selectedTailoredResume: TailoredResumeVersion | null;
  allowedStageTransitions: ApplicationStage[];
  selectedJobAnalyses: SavedJobAnalysis[];
  selectedApplicationEvents: ApplicationEvent[];
  selectedJobBriefs: JobBrief[];
  selectedPreparation: InterviewPreparationWorkspace | null;
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
}

interface ApiErrorPayload {
  detail?: string;
}

export const useSavedJobsStore = defineStore("savedJobs", {
  state: (): SavedJobState => ({
    jobs: [],
    selectedJob: null,
    selectedApplication: null,
    selectedCommunicationDraft: null,
    selectedTailoredResume: null,
    allowedStageTransitions: [],
    selectedJobAnalyses: [],
    selectedApplicationEvents: [],
    selectedJobBriefs: [],
    selectedPreparation: null,
    isLoading: false,
    isSaving: false,
    error: null
  }),
  getters: {
    activeJobs: (state) => state.jobs.filter((job) => !job.archived_at)
  },
  actions: {
    async loadJobs(includeArchived = false): Promise<SavedJob[]> {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await listSavedJobs(includeArchived);
        this.jobs = response.items;
        return response.items;
      } catch (error) {
        this.jobs = [];
        this.error = toApiErrorMessage(error, "Failed to load saved jobs.");
        throw error;
      } finally {
        this.isLoading = false;
      }
    },
    async createJob(payload: SavedJobCreatePayload): Promise<SavedJob> {
      this.isSaving = true;
      this.error = null;
      try {
        const job = await createSavedJob(payload);
        this.mergeJob(job);
        return job;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to save job.");
        throw error;
      } finally {
        this.isSaving = false;
      }
    },
    async loadJobDetail(savedJobId: string): Promise<SavedJob> {
      this.isLoading = true;
      this.error = null;
      try {
        const [workspace, analyses, briefs, preparation] = await Promise.all([
          getSavedJobWorkspace(savedJobId),
          listSavedJobAnalyses(savedJobId),
          listJobBriefs(savedJobId),
          getInterviewPreparation(savedJobId).catch(() => null)
        ]);
        this.selectedJob = workspace.job;
        this.selectedApplication = workspace.application;
        this.selectedCommunicationDraft = workspace.communication_draft;
        this.selectedTailoredResume = workspace.tailored_resume;
        this.allowedStageTransitions = workspace.allowed_stage_transitions;
        this.selectedJobAnalyses = analyses.items;
        this.selectedApplicationEvents = workspace.events;
        this.selectedJobBriefs = briefs.items;
        this.selectedPreparation = preparation;
        this.mergeJob(workspace.job);
        return workspace.job;
      } catch (error) {
        this.selectedJob = null;
        this.selectedApplication = null;
        this.selectedCommunicationDraft = null;
        this.selectedTailoredResume = null;
        this.allowedStageTransitions = [];
        this.selectedJobAnalyses = [];
        this.selectedApplicationEvents = [];
        this.selectedJobBriefs = [];
        this.selectedPreparation = null;
        this.error = toApiErrorMessage(error, "Failed to load saved job details.");
        throw error;
      } finally {
        this.isLoading = false;
      }
    },
    async saveFromSearchResult(payload: SavedJobFromSearchResultPayload): Promise<SavedJob> {
      this.isSaving = true;
      this.error = null;
      try {
        const job = await saveJobFromSearchResult(payload);
        this.mergeJob(job);
        return job;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to save search result.");
        throw error;
      } finally {
        this.isSaving = false;
      }
    },
    async updateJob(savedJobId: string, payload: SavedJobUpdatePayload): Promise<SavedJob> {
      this.isSaving = true;
      this.error = null;
      try {
        const job = await updateSavedJob(savedJobId, payload);
        this.mergeJob(job);
        if (this.selectedJob?.saved_job_id === savedJobId) {
          this.selectedJob = job;
        }
        return job;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to update saved job.");
        throw error;
      } finally {
        this.isSaving = false;
      }
    },
    async startApplication(savedJobId: string): Promise<JobApplication> {
      this.isSaving = true;
      this.error = null;
      try {
        const application = await createJobApplication(savedJobId);
        this.selectedApplication = application;
        const workspace = await getSavedJobWorkspace(savedJobId);
        this.selectedCommunicationDraft = workspace.communication_draft;
        this.selectedTailoredResume = workspace.tailored_resume;
        this.allowedStageTransitions = workspace.allowed_stage_transitions;
        this.selectedApplicationEvents = workspace.events;
        return application;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to start application tracking.");
        throw error;
      } finally {
        this.isSaving = false;
      }
    },
    async changeApplicationStage(stage: ApplicationStage): Promise<JobApplication> {
      if (!this.selectedApplication) throw new Error("Application tracking has not started.");
      this.isSaving = true;
      this.error = null;
      try {
        const application = await updateJobApplication(
          this.selectedApplication.application_id,
          { stage }
        );
        this.selectedApplication = application;
        const workspace = await getSavedJobWorkspace(application.saved_job_id);
        this.selectedCommunicationDraft = workspace.communication_draft;
        this.selectedTailoredResume = workspace.tailored_resume;
        this.allowedStageTransitions = workspace.allowed_stage_transitions;
        this.selectedApplicationEvents = workspace.events;
        return application;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to update application stage.");
        throw error;
      } finally {
        this.isSaving = false;
      }
    },
    async archiveJob(savedJobId: string): Promise<SavedJob> {
      this.isSaving = true;
      this.error = null;
      try {
        const job = await archiveSavedJob(savedJobId);
        this.mergeJob(job);
        if (this.selectedJob?.saved_job_id === savedJobId) this.selectedJob = job;
        return job;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to archive saved job.");
        throw error;
      } finally {
        this.isSaving = false;
      }
    },
    async createTailoredResume(savedJobId: string): Promise<TailoredResumeVersion> {
      this.isSaving = true;
      this.error = null;
      try {
        const version = await generateTailoredResume(savedJobId);
        this.selectedTailoredResume = version;
        const workspace = await getSavedJobWorkspace(savedJobId);
        this.selectedApplication = workspace.application;
        this.allowedStageTransitions = workspace.allowed_stage_transitions;
        this.selectedApplicationEvents = workspace.events;
        return version;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to generate a tailored resume.");
        throw error;
      } finally {
        this.isSaving = false;
      }
    },
    async saveTailoredResume(content: string): Promise<TailoredResumeVersion> {
      if (!this.selectedTailoredResume) throw new Error("No tailored resume is selected.");
      this.isSaving = true;
      this.error = null;
      try {
        const version = await updateTailoredResume(
          this.selectedTailoredResume.tailored_resume_id,
          content
        );
        this.selectedTailoredResume = version;
        return version;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to save the tailored resume.");
        throw error;
      } finally {
        this.isSaving = false;
      }
    },
    async confirmTailoredResume(): Promise<TailoredResumeVersion> {
      if (!this.selectedTailoredResume) throw new Error("No tailored resume is selected.");
      this.isSaving = true;
      this.error = null;
      try {
        const version = await approveTailoredResume(this.selectedTailoredResume.tailored_resume_id);
        this.selectedTailoredResume = version;
        const workspace = await getSavedJobWorkspace(version.saved_job_id);
        this.selectedApplication = workspace.application;
        this.allowedStageTransitions = workspace.allowed_stage_transitions;
        this.selectedApplicationEvents = workspace.events;
        return version;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Resolve validation issues before confirming.");
        throw error;
      } finally {
        this.isSaving = false;
      }
    },
    async generateBrief(savedJobId: string): Promise<JobBrief> {
      this.isSaving = true;
      this.error = null;
      try {
        const brief = await generateJobBrief(savedJobId);
        this.selectedJobBriefs = [brief, ...this.selectedJobBriefs];
        return brief;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to generate job brief.");
        throw error;
      } finally {
        this.isSaving = false;
      }
    },
    async generatePreparation(savedJobId: string): Promise<InterviewPreparationWorkspace> {
      this.isSaving = true;
      this.error = null;
      try {
        const workspace = await generateInterviewPreparation(savedJobId);
        this.selectedPreparation = workspace;
        return workspace;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to prepare interview evidence questions.");
        throw error;
      } finally {
        this.isSaving = false;
      }
    },
    async savePreparationAnswers(
      savedJobId: string,
      answers: PreparationAnswer[],
      action: "advance" | "save" | "complete" | "stop" = "complete"
    ): Promise<InterviewPreparationWorkspace> {
      this.isSaving = true;
      this.error = null;
      try {
        const workspace = await submitPreparationAnswers(savedJobId, answers, action);
        this.selectedPreparation = workspace;
        return workspace;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to save preparation answers.");
        throw error;
      } finally {
        this.isSaving = false;
      }
    },
    async deleteJob(savedJobId: string): Promise<void> {
      this.isSaving = true;
      this.error = null;
      try {
        await deleteSavedJob(savedJobId);
        this.jobs = this.jobs.filter((job) => job.saved_job_id !== savedJobId);
        if (this.selectedJob?.saved_job_id === savedJobId) {
          this.selectedJob = null;
          this.selectedApplication = null;
          this.selectedCommunicationDraft = null;
          this.selectedTailoredResume = null;
          this.allowedStageTransitions = [];
          this.selectedJobAnalyses = [];
          this.selectedApplicationEvents = [];
          this.selectedJobBriefs = [];
          this.selectedPreparation = null;
        }
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to delete saved job.");
        throw error;
      } finally {
        this.isSaving = false;
      }
    },
    mergeJob(job: SavedJob): void {
      const index = this.jobs.findIndex((item) => item.saved_job_id === job.saved_job_id);
      if (index === -1) {
        this.jobs = [job, ...this.jobs];
        return;
      }
      this.jobs.splice(index, 1, job);
    }
  }
});

function toApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof AxiosError) {
    return (error.response?.data as ApiErrorPayload | undefined)?.detail ?? fallback;
  }
  return error instanceof Error ? error.message : fallback;
}
