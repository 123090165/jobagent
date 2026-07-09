import { defineStore } from "pinia";
import { AxiosError } from "axios";

import {
  archiveSavedJob,
  createSavedJob,
  listSavedJobs,
  saveJobFromSearchResult,
  updateSavedJob
} from "../api/savedJobs";
import type {
  SavedJob,
  SavedJobCreatePayload,
  SavedJobFromSearchResultPayload,
  SavedJobUpdatePayload
} from "../types/savedJob";

interface SavedJobState {
  jobs: SavedJob[];
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
        return job;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to archive saved job.");
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
