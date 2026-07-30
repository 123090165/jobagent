/**
 * 在浏览器本地保存登录 token；API 客户端读取它注入请求，退出登录时统一清除。
 */
const AUTH_TOKEN_STORAGE_KEY = "jobagent.access_token";

export function getAuthToken(): string | null {
  return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
}

export function setAuthToken(token: string): void {
  window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
}

export function clearAuthToken(): void {
  window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
}
