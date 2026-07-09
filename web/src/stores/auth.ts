import { defineStore } from "pinia";
import { AxiosError } from "axios";

import {
  getCurrentUser,
  loginUser,
  logoutUser,
  registerUser
} from "../api/auth";
import { clearAuthToken, getAuthToken, setAuthToken } from "../services/authToken";
import type {
  AuthLoginPayload,
  AuthRegisterPayload,
  AuthTokenResponse,
  UserAccount
} from "../types/auth";

interface AuthState {
  user: UserAccount | null;
  accessToken: string | null;
  expiresAt: string | null;
  isBootstrapped: boolean;
  isLoading: boolean;
  error: string | null;
}

interface ApiErrorPayload {
  detail?: string;
}

export const useAuthStore = defineStore("auth", {
  state: (): AuthState => ({
    user: null,
    accessToken: getAuthToken(),
    expiresAt: null,
    isBootstrapped: false,
    isLoading: false,
    error: null
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.accessToken && state.user),
    displayName: (state) => state.user?.display_name || state.user?.username || ""
  },
  actions: {
    async bootstrap(): Promise<void> {
      if (this.isBootstrapped) {
        return;
      }
      this.accessToken = getAuthToken();
      if (!this.accessToken) {
        this.user = null;
        this.expiresAt = null;
        this.isBootstrapped = true;
        return;
      }

      this.isLoading = true;
      try {
        const response = await getCurrentUser();
        this.user = response.user;
        this.error = null;
      } catch (error) {
        this.clearSession();
        this.error = toApiErrorMessage(error, "Failed to restore login session.");
      } finally {
        this.isLoading = false;
        this.isBootstrapped = true;
      }
    },
    async login(payload: AuthLoginPayload): Promise<UserAccount> {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await loginUser(payload);
        this.applyTokenResponse(response);
        return response.user;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Login failed.");
        throw error;
      } finally {
        this.isLoading = false;
        this.isBootstrapped = true;
      }
    },
    async register(payload: AuthRegisterPayload): Promise<UserAccount> {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await registerUser(payload);
        this.applyTokenResponse(response);
        return response.user;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Registration failed.");
        throw error;
      } finally {
        this.isLoading = false;
        this.isBootstrapped = true;
      }
    },
    async logout(): Promise<void> {
      this.isLoading = true;
      try {
        if (this.accessToken) {
          await logoutUser();
        }
      } catch {
        // Local cleanup should still happen when the server session is gone.
      } finally {
        this.clearSession();
        this.isLoading = false;
        this.isBootstrapped = true;
      }
    },
    applyTokenResponse(response: AuthTokenResponse): void {
      this.user = response.user;
      this.accessToken = response.access_token;
      this.expiresAt = response.expires_at;
      setAuthToken(response.access_token);
      this.error = null;
    },
    clearSession(): void {
      this.user = null;
      this.accessToken = null;
      this.expiresAt = null;
      clearAuthToken();
    }
  }
});

function toApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof AxiosError) {
    return (error.response?.data as ApiErrorPayload | undefined)?.detail ?? fallback;
  }
  return error instanceof Error ? error.message : fallback;
}
