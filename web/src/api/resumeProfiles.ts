import { client } from "./client";
import type {
  ResumeProfile,
  ResumeProfileListResponse,
  ResumeProfileUpdatePayload
} from "../types/resumeProfile";

export async function listResumeProfiles(includeArchived = false): Promise<ResumeProfileListResponse> {
  const response = await client.get<ResumeProfileListResponse>("/api/v1/resume-profiles", {
    params: { include_archived: includeArchived }
  });
  return response.data;
}

export async function getResumeProfile(resumeProfileId: string): Promise<ResumeProfile> {
  const response = await client.get<ResumeProfile>(
    `/api/v1/resume-profiles/${resumeProfileId}`
  );
  return response.data;
}

export async function updateResumeProfile(
  resumeProfileId: string,
  payload: ResumeProfileUpdatePayload
): Promise<ResumeProfile> {
  const response = await client.patch<ResumeProfile>(
    `/api/v1/resume-profiles/${resumeProfileId}`,
    payload
  );
  return response.data;
}

export async function setDefaultResumeProfile(resumeProfileId: string): Promise<ResumeProfile> {
  const response = await client.post<ResumeProfile>(
    `/api/v1/resume-profiles/${resumeProfileId}/default`
  );
  return response.data;
}

export async function archiveResumeProfile(resumeProfileId: string): Promise<ResumeProfile> {
  const response = await client.post<ResumeProfile>(
    `/api/v1/resume-profiles/${resumeProfileId}/archive`
  );
  return response.data;
}

export async function restoreResumeProfile(resumeProfileId: string): Promise<ResumeProfile> {
  const response = await client.post<ResumeProfile>(
    `/api/v1/resume-profiles/${resumeProfileId}/restore`
  );
  return response.data;
}

export async function deleteResumeProfile(resumeProfileId: string): Promise<void> {
  await client.delete(`/api/v1/resume-profiles/${resumeProfileId}`);
}
