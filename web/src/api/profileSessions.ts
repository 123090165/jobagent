import { client } from "./client";
import type {
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
