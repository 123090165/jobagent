import { client } from "./client";
import type { ProfileSession } from "../types/profileSession";

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
