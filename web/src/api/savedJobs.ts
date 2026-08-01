import { client } from "./client";
import type {
  SavedJob,
  JobBrief,
  JobBriefGeneratePayload,
  JobBriefListResponse,
  InterviewPreparationWorkspace,
  PreparationAnswer,
  SavedJobAnalysisListResponse,
  SavedJobCreatePayload,
  SavedJobFromSearchResultPayload,
  SavedJobListResponse,
  SavedJobWorkspace,
  JobApplication,
  ExternalApplicationStage,
  TailoredResumeVersion,
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

export async function getSavedJobWorkspace(savedJobId: string): Promise<SavedJobWorkspace> {
  const response = await client.get<SavedJobWorkspace>(
    `/api/v1/saved-jobs/${savedJobId}/workspace`
  );
  return response.data;
}

export async function recordExternalApplicationProgress(
  savedJobId: string,
  payload: { stage: ExternalApplicationStage; detail?: string | null }
): Promise<JobApplication> {
  const response = await client.post<JobApplication>(
    `/api/v1/saved-jobs/${savedJobId}/application/external-progress`,
    payload
  );
  return response.data;
}

export async function generateTailoredResume(
  savedJobId: string,
  resumeProfileId?: string | null
): Promise<TailoredResumeVersion> {
  const response = await client.post<TailoredResumeVersion>(
    `/api/v1/saved-jobs/${savedJobId}/tailored-resumes`,
    { resume_profile_id: resumeProfileId ?? null }
  );
  return response.data;
}

export async function updateTailoredResume(
  tailoredResumeId: string,
  content: string
): Promise<TailoredResumeVersion> {
  const response = await client.patch<TailoredResumeVersion>(
    `/api/v1/tailored-resumes/${tailoredResumeId}`,
    { content }
  );
  return response.data;
}

export async function approveTailoredResume(
  tailoredResumeId: string
): Promise<TailoredResumeVersion> {
  const response = await client.post<TailoredResumeVersion>(
    `/api/v1/tailored-resumes/${tailoredResumeId}/approve`
  );
  return response.data;
}

export async function downloadTailoredResumePdf(
  tailoredResumeId: string
): Promise<Blob> {
  const response = await client.get<Blob>(
    `/api/v1/tailored-resumes/${tailoredResumeId}/pdf`,
    { responseType: "blob" }
  );
  return response.data;
}

export async function listJobBriefs(savedJobId: string): Promise<JobBriefListResponse> {
  const response = await client.get<JobBriefListResponse>(
    `/api/v1/saved-jobs/${savedJobId}/briefs`
  );
  return response.data;
}

export async function generateJobBrief(
  savedJobId: string,
  payload: JobBriefGeneratePayload = {}
): Promise<JobBrief> {
  const response = await client.post<JobBrief>(
    `/api/v1/saved-jobs/${savedJobId}/briefs`,
    payload
  );
  return response.data;
}

export async function getInterviewPreparation(
  savedJobId: string
): Promise<InterviewPreparationWorkspace> {
  const response = await client.get<InterviewPreparationWorkspace>(
    `/api/v1/saved-jobs/${savedJobId}/preparation`
  );
  return response.data;
}

export async function generateInterviewPreparation(
  savedJobId: string
): Promise<InterviewPreparationWorkspace> {
  const response = await client.post<InterviewPreparationWorkspace>(
    `/api/v1/saved-jobs/${savedJobId}/preparation`,
    {}
  );
  return response.data;
}

export async function submitPreparationAnswers(
  savedJobId: string,
  answers: PreparationAnswer[],
  action: "advance" | "save" | "complete" | "stop" = "complete"
): Promise<InterviewPreparationWorkspace> {
  const response = await client.put<InterviewPreparationWorkspace>(
    `/api/v1/saved-jobs/${savedJobId}/preparation/answers`,
    { answers, action }
  );
  return response.data;
}

export async function downloadPreparationPrompt(savedJobId: string): Promise<Blob> {
  const response = await client.get(
    `/api/v1/saved-jobs/${savedJobId}/preparation/prompt.txt`,
    { responseType: "blob" }
  );
  return response.data as Blob;
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

export async function deleteSavedJob(savedJobId: string): Promise<void> {
  await client.delete(`/api/v1/saved-jobs/${savedJobId}`);
}
