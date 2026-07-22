import { client } from "./client";

export interface BrowserHelperProfileSessionOption {
  session_id: string;
  label: string;
  is_default: boolean;
}

export interface BrowserHelperSession {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  profile_sessions: BrowserHelperProfileSessionOption[];
}

export async function createBrowserHelperSession(): Promise<BrowserHelperSession> {
  const response = await client.post<BrowserHelperSession>("/api/v1/browser-helper/sessions");
  return response.data;
}
