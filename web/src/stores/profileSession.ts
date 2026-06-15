import { defineStore } from "pinia";

import { createProfileSession } from "../api/profileSessions";
import type { ProfileSession } from "../types/profileSession";

interface ProfileSessionState {
  session: ProfileSession | null;
  isCreating: boolean;
  error: string | null;
}

export const useProfileSessionStore = defineStore("profileSession", {
  state: (): ProfileSessionState => ({
    session: null,
    isCreating: false,
    error: null
  }),
  actions: {
    async createSession(): Promise<ProfileSession> {
      this.isCreating = true;
      this.error = null;

      try {
        this.session = await createProfileSession();
        return this.session;
      } catch (error) {
        this.error =
          error instanceof Error ? error.message : "Failed to create profile session.";
        throw error;
      } finally {
        this.isCreating = false;
      }
    }
  }
});
