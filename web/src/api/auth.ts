/**
 * 封装认证账户与会话的类型化 HTTP 请求；这里只处理传输，不复制后端规则。
 */
import { client } from "./client";
import type {
  AuthLoginPayload,
  AuthMeResponse,
  AuthRegisterPayload,
  AuthTokenResponse
} from "../types/auth";

export async function loginUser(payload: AuthLoginPayload): Promise<AuthTokenResponse> {
  const response = await client.post<AuthTokenResponse>("/api/v1/auth/login", payload);
  return response.data;
}

export async function registerUser(payload: AuthRegisterPayload): Promise<AuthTokenResponse> {
  const response = await client.post<AuthTokenResponse>("/api/v1/auth/register", payload);
  return response.data;
}

export async function logoutUser(): Promise<void> {
  await client.post("/api/v1/auth/logout");
}

export async function getCurrentUser(): Promise<AuthMeResponse> {
  const response = await client.get<AuthMeResponse>("/api/v1/auth/me");
  return response.data;
}
