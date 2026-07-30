/**
 * 覆盖“简历录入→审阅→画像→搜索”的全部会话接口；Store 通过这些函数推进后端状态机。
 */
import { client } from "./client";
import type {
  CreateBrowserHelperJobSearchPayload,
  CreateJobSearchRunPayload,
  ConfirmedProfileResponse,
  JobSearchItemListResponse,
  JobSearchPreview,
  JobSearchTraceStepListResponse,
  JobSearchRunListResponse,
  JobSearchResultFeedback,
  JobSearchResultFeedbackListResponse,
  JobSearchFeedbackType,
  JobSearchRunResponse,
  LlmProviderName,
  LlmStatus,
  ParsedResumeReview,
  ParsedResumeReviewResponse,
  ProfileDraftResponse,
  ProfileSession,
  ResumeIntakeResponse,
  SearchMission,
  SearchMissionInput,
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

export async function getSearchMission(sessionId: string): Promise<SearchMission> {
  const response = await client.get<SearchMission>(
    `/api/v1/profile-sessions/${sessionId}/search-mission`
  );
  return response.data;
}

export async function saveSearchMission(
  sessionId: string,
  payload: SearchMissionInput
): Promise<SearchMission> {
  const response = await client.put<SearchMission>(
    `/api/v1/profile-sessions/${sessionId}/search-mission`,
    payload
  );
  return response.data;
}

export async function interpretSearchMission(
  sessionId: string,
  useLlm: boolean,
  llmProvider: LlmProviderName = "deepseek"
): Promise<SearchMission> {
  const response = await client.post<SearchMission>(
    `/api/v1/profile-sessions/${sessionId}/search-mission/interpret`,
    { use_llm: useLlm, llm_provider: llmProvider }
  );
  return response.data;
}

export async function confirmSearchMission(sessionId: string): Promise<SearchMission> {
  const response = await client.post<SearchMission>(
    `/api/v1/profile-sessions/${sessionId}/search-mission/confirm`
  );
  return response.data;
}

export async function createBrowserHelperJobSearchRun(
  payload: CreateBrowserHelperJobSearchPayload
): Promise<JobSearchRunResponse> {
  const response = await client.post<JobSearchRunResponse>(
    "/api/v1/job-search-runs/browser-helper",
    payload
  );
  return response.data;
}

export async function previewJobSearchRun(
  payload: CreateJobSearchRunPayload
): Promise<JobSearchPreview> {
  const response = await client.post<JobSearchPreview>("/api/v1/job-search-runs/preview", payload);
  return response.data;
}

export async function getLlmStatus(provider: LlmProviderName = "deepseek"): Promise<LlmStatus> {
  const response = await client.get<LlmStatus>("/api/v1/llm/status", {
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

export async function listJobSearchItems(
  runId: string,
  limit = 100,
  offset = 0
): Promise<JobSearchItemListResponse> {
  const response = await client.get<JobSearchItemListResponse>(
    `/api/v1/job-search-runs/${runId}/items`,
    { params: { limit, offset } }
  );
  return response.data;
}

export async function listJobSearchRuns(sessionId: string): Promise<JobSearchRunListResponse> {
  const response = await client.get<JobSearchRunListResponse>(
    `/api/v1/profile-sessions/${sessionId}/job-search-runs`
  );
  return response.data;
}

export async function listUserJobSearchRuns(limit = 100): Promise<JobSearchRunListResponse> {
  const response = await client.get<JobSearchRunListResponse>("/api/v1/job-search-runs", {
    params: { limit }
  });
  return response.data;
}

export async function deleteJobSearchRun(runId: string): Promise<void> {
  await client.delete(`/api/v1/job-search-runs/${runId}`);
}

export async function listJobSearchResultFeedback(
  runId: string
): Promise<JobSearchResultFeedbackListResponse> {
  const response = await client.get<JobSearchResultFeedbackListResponse>(
    `/api/v1/job-search-runs/${runId}/feedback`
  );
  return response.data;
}

export async function saveJobSearchResultFeedback(
  runId: string,
  resultId: string,
  payload: { feedback_type: JobSearchFeedbackType; note?: string | null }
): Promise<JobSearchResultFeedback> {
  const response = await client.post<JobSearchResultFeedback>(
    `/api/v1/job-search-runs/${runId}/results/${resultId}/feedback`,
    payload
  );
  return response.data;
}
