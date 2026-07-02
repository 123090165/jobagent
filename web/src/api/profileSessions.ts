import { client } from "./client";
import type {
  CreateJobSearchRunPayload,
  ConfirmedProfileResponse,
  JobSearchProviderStatus,
  JobSearchPreview,
  JobSearchTraceStepListResponse,
  JobSearchRunListResponse,
  JobSearchRunResponse,
  LlmStatus,
  ParsedResumeReview,
  ParsedResumeReviewResponse,
  ProfileDraftResponse,
  ProfileSession,
  ResumeDocument,
  ResumeIntakeResponse,
  UpdateProfileDraftPayload
} from "../types/profileSession";

export async function createProfileSession(): Promise<ProfileSession> {
  const response = await client.post<ProfileSession>("/api/v1/profile-sessions");
  return response.data;
}

export async function getProfileSession(sessionId: string): Promise<ProfileSession> {
  const response = await client.get<ProfileSession>(
    `/api/v1/profile-sessions/${sessionId}`
  );
  return response.data;
}

export async function submitResumeText(
  sessionId: string,
  text: string
): Promise<ResumeIntakeResponse> {
  const response = await client.post<ResumeIntakeResponse>(
    `/api/v1/profile-sessions/${sessionId}/resume-text`,
    { text }
  );
  return response.data;
}

export async function submitResumeFile(
  sessionId: string,
  file: File
): Promise<ResumeIntakeResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await client.post<ResumeIntakeResponse>(
    `/api/v1/profile-sessions/${sessionId}/resume-file`,
    formData
  );
  return response.data;
}

export async function getResumeDocument(sessionId: string): Promise<ResumeDocument> {
  const response = await client.get<ResumeDocument>(
    `/api/v1/profile-sessions/${sessionId}/resume`
  );
  return response.data;
}

export async function parseResumeForReview(
  sessionId: string,
  regenerate = false,
  useLlm = false
): Promise<ParsedResumeReviewResponse> {
  const response = await client.post<ParsedResumeReviewResponse>(
    `/api/v1/profile-sessions/${sessionId}/parse-resume`,
    null,
    {
      params: { regenerate, use_llm: useLlm }
    }
  );
  return response.data;
}

export async function getParsedResumeReview(
  sessionId: string
): Promise<ParsedResumeReviewResponse> {
  const response = await client.get<ParsedResumeReviewResponse>(
    `/api/v1/profile-sessions/${sessionId}/parsed-review`
  );
  return response.data;
}

export async function createProfileDraft(
  sessionId: string,
  regenerate = false
): Promise<ProfileDraftResponse> {
  const response = await client.post<ProfileDraftResponse>(
    `/api/v1/profile-sessions/${sessionId}/profile-draft`,
    null,
    {
      params: { regenerate }
    }
  );
  return response.data;
}

export async function getProfileDraft(draftId: string): Promise<ProfileDraftResponse> {
  const response = await client.get<ProfileDraftResponse>(`/api/v1/profile-drafts/${draftId}`);
  return response.data;
}

export async function updateProfileDraft(
  draftId: string,
  payload: UpdateProfileDraftPayload
): Promise<ProfileDraftResponse> {
  const response = await client.patch<ProfileDraftResponse>(
    `/api/v1/profile-drafts/${draftId}`,
    payload
  );
  return response.data;
}

export async function confirmProfileDraft(
  draftId: string
): Promise<ConfirmedProfileResponse> {
  const response = await client.post<ConfirmedProfileResponse>(
    `/api/v1/profile-drafts/${draftId}/confirm`
  );
  return response.data;
}

export async function getConfirmedProfile(
  confirmedProfileId: string
): Promise<ConfirmedProfileResponse> {
  const response = await client.get<ConfirmedProfileResponse>(
    `/api/v1/confirmed-profiles/${confirmedProfileId}`
  );
  return response.data;
}

export async function createJobSearchRun(
  payload: CreateJobSearchRunPayload
): Promise<JobSearchRunResponse> {
  const response = await client.post<JobSearchRunResponse>("/api/v1/job-search-runs", payload);
  return response.data;
}

export async function previewJobSearchRun(
  payload: CreateJobSearchRunPayload
): Promise<JobSearchPreview> {
  const response = await client.post<JobSearchPreview>("/api/v1/job-search-runs/preview", payload);
  return response.data;
}

export async function getLlmStatus(useDeepseek = false): Promise<LlmStatus> {
  const response = await client.get<LlmStatus>("/api/v1/llm/status", {
    params: { use_deepseek: useDeepseek }
  });
  return response.data;
}

export async function getJobSearchProviderStatus(
  provider?: "mock" | "cuhksz_career" | "linkedin" | "remoteok" | "serper_web" | "multi_source"
): Promise<JobSearchProviderStatus> {
  const response = await client.get<JobSearchProviderStatus>("/api/v1/job-search-providers/status", {
    params: { provider }
  });
  return response.data;
}

export async function getJobSearchRun(runId: string): Promise<JobSearchRunResponse> {
  const response = await client.get<JobSearchRunResponse>(`/api/v1/job-search-runs/${runId}`);
  return response.data;
}

export async function getJobSearchRunSteps(runId: string): Promise<JobSearchTraceStepListResponse> {
  const response = await client.get<JobSearchTraceStepListResponse>(
    `/api/v1/job-search-runs/${runId}/steps`
  );
  return response.data;
}

export async function listJobSearchRuns(sessionId: string): Promise<JobSearchRunListResponse> {
  const response = await client.get<JobSearchRunListResponse>(
    `/api/v1/profile-sessions/${sessionId}/job-search-runs`
  );
  return response.data;
}
