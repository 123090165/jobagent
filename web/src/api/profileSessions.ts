import { client } from "./client";
import type {
  ParsedResumeReview,
  ParsedResumeReviewResponse,
  ProfileSession,
  ResumeDocument,
  ResumeIntakeResponse
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
  regenerate = false
): Promise<ParsedResumeReviewResponse> {
  const response = await client.post<ParsedResumeReviewResponse>(
    `/api/v1/profile-sessions/${sessionId}/parse-resume`,
    null,
    {
      params: { regenerate }
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
