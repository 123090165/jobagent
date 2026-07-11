import { client } from "./client";
import type {
  SavedJob,
  SavedJobAnalysisListResponse,
  SavedJobCreatePayload,
  SavedJobFromSearchResultPayload,
  SavedJobListResponse,
  SavedJobStatusEventListResponse,
  SavedJobUpdatePayload
} from "../types/savedJob";

export async function listSavedJobs(includeArchived = false): Promise<SavedJobListResponse> {
  const response = await client.get<SavedJobListResponse>("/api/v1/saved-jobs", {
    params: { include_archived: includeArchived }
  });
  return response.data;
}

export async function createSavedJob(payload: SavedJobCreatePayload): Promise<SavedJob> {
  const response = await client.post<SavedJob>("/api/v1/saved-jobs", payload);
  return response.data;
}

export async function getSavedJob(savedJobId: string): Promise<SavedJob> {
  const response = await client.get<SavedJob>(`/api/v1/saved-jobs/${savedJobId}`);
  return response.data;
}

export async function listSavedJobAnalyses(
  savedJobId: string
): Promise<SavedJobAnalysisListResponse> {
  const response = await client.get<SavedJobAnalysisListResponse>(
    `/api/v1/saved-jobs/${savedJobId}/analyses`
  );
  return response.data;
}

export async function listSavedJobStatusHistory(
  savedJobId: string
): Promise<SavedJobStatusEventListResponse> {
  const response = await client.get<SavedJobStatusEventListResponse>(
    `/api/v1/saved-jobs/${savedJobId}/status-history`
  );
  return response.data;
}

export async function saveJobFromSearchResult(
  payload: SavedJobFromSearchResultPayload
): Promise<SavedJob> {
  const response = await client.post<SavedJob>(
    "/api/v1/saved-jobs/from-search-result",
    payload
  );
  return response.data;
}

export async function updateSavedJob(
  savedJobId: string,
  payload: SavedJobUpdatePayload
): Promise<SavedJob> {
  const response = await client.patch<SavedJob>(`/api/v1/saved-jobs/${savedJobId}`, payload);
  return response.data;
}

export async function archiveSavedJob(savedJobId: string): Promise<SavedJob> {
  const response = await client.post<SavedJob>(`/api/v1/saved-jobs/${savedJobId}/archive`);
  return response.data;
}
