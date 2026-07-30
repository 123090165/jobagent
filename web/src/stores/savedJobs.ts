/**
 * 管理收藏职位、分析历史、Job Brief、状态历史和面试准备工作区。
 */
import { defineStore } from "pinia";
import { AxiosError } from "axios";

import {
  archiveSavedJob,
  createSavedJob,
  deleteSavedJob,
  getSavedJob,
  generateJobBrief,
  generateInterviewPreparation,
  getInterviewPreparation,
  listJobBriefs,
  submitPreparationAnswers,
  listSavedJobs,
  listSavedJobAnalyses,
  listSavedJobStatusHistory,
  saveJobFromSearchResult,
  updateSavedJob
} from "../api/savedJobs";
import type {
  SavedJob,
  JobBrief,
  InterviewPreparationWorkspace,
  PreparationAnswer,
  SavedJobAnalysis,
  SavedJobStatusEvent,
  SavedJobCreatePayload,
  SavedJobFromSearchResultPayload,
  SavedJobUpdatePayload
} from "../types/savedJob";

interface SavedJobState {
  jobs: SavedJob[];
  selectedJob: SavedJob | null;
  selectedJobAnalyses: SavedJobAnalysis[];
  selectedJobStatusHistory: SavedJobStatusEvent[];
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
    selectedJobAnalyses: [],
    selectedJobStatusHistory: [],
    selectedJobBriefs: [],
    selectedPreparation: null,
    isLoading: false,
    isSaving: false,
    error: null
  }),
  getters: {
    activeJobs: (state) => state.jobs.filter((job) => !job.archived_at),
    savedCount: (state) => state.jobs.filter((job) => job.status === "saved").length,
    interestedCount: (state) => state.jobs.filter((job) => job.status === "interested").length
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
        // 工作台并行读取各持久化视图；尚未创建 preparation 属于正常空状态。
        const [job, analyses, statusHistory, briefs, preparation] = await Promise.all([
          getSavedJob(savedJobId),
          listSavedJobAnalyses(savedJobId),
          listSavedJobStatusHistory(savedJobId),
          listJobBriefs(savedJobId),
          getInterviewPreparation(savedJobId).catch(() => null)
        ]);
        this.selectedJob = job;
        this.selectedJobAnalyses = analyses.items;
        this.selectedJobStatusHistory = statusHistory.items;
        this.selectedJobBriefs = briefs.items;
        this.selectedPreparation = preparation;
        this.mergeJob(job);
        return job;
      } catch (error) {
        this.selectedJob = null;
        this.selectedJobAnalyses = [];
        this.selectedJobStatusHistory = [];
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
        // 服务端可能返回已存在的职位，始终用返回值合并而不是在前端假设新建成功。
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
          this.selectedJobStatusHistory = (await listSavedJobStatusHistory(savedJobId)).items;
        }
        return job;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to update saved job.");
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
          this.selectedJobAnalyses = [];
          this.selectedJobStatusHistory = [];
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
