/**
 * 创建和读取浏览器助手配对会话；页面拿到受限 token 后再通过扩展 bridge 发起采集。
 */
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
