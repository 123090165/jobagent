import { defineStore } from "pinia";
import { AxiosError } from "axios";

import {
  createProfileSession,
  getParsedResumeReview,
  getProfileSession,
  parseResumeForReview,
  submitResumeFile,
  submitResumeText
} from "../api/profileSessions";
import type {
  ParsedResumeReview,
  ProfileSession,
  ResumeDocument
} from "../types/profileSession";

interface ProfileSessionState {
  session: ProfileSession | null;
  resumeDocument: ResumeDocument | null;
  parsedReview: ParsedResumeReview | null;
  isCreating: boolean;
  isSubmitting: boolean;
  isReviewLoading: boolean;
  hasLoadedSession: boolean;
  error: string | null;
}

interface ApiErrorPayload {
  detail?: string;
}

export const useProfileSessionStore = defineStore("profileSession", {
  state: (): ProfileSessionState => ({
    session: null,
    resumeDocument: null,
    parsedReview: null,
    isCreating: false,
    isSubmitting: false,
    isReviewLoading: false,
    hasLoadedSession: false,
    error: null
  }),
  actions: {
    async createSession(): Promise<ProfileSession> {
      this.isCreating = true;
      this.error = null;

      try {
        this.session = await createProfileSession();
        this.hasLoadedSession = true;
        return this.session;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to create profile session.");
        throw error;
      } finally {
        this.isCreating = false;
      }
    },
    async loadSession(sessionId: string): Promise<ProfileSession> {
      try {
        this.session = await getProfileSession(sessionId);
        this.hasLoadedSession = true;
        this.error = null;
        if (this.session.current_step !== "resume_review") {
          this.parsedReview = null;
        }
        return this.session;
      } catch (error) {
        this.session = null;
        this.resumeDocument = null;
        this.parsedReview = null;
        this.error = toApiErrorMessage(error, "Failed to load profile session.");
        throw error;
      }
    },
    async submitTextResume(text: string): Promise<ProfileSession> {
      const session = await this.ensureSession();
      this.isSubmitting = true;
      this.error = null;
      try {
        const response = await submitResumeText(session.session_id, text);
        this.session = response.profile_session;
        this.resumeDocument = response.resume_document;
        this.parsedReview = null;
        return response.profile_session;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to submit resume text.");
        throw error;
      } finally {
        this.isSubmitting = false;
      }
    },
    async submitFileResume(file: File): Promise<ProfileSession> {
      const session = await this.ensureSession();
      this.isSubmitting = true;
      this.error = null;
      try {
        const response = await submitResumeFile(session.session_id, file);
        this.session = response.profile_session;
        this.resumeDocument = response.resume_document;
        this.parsedReview = null;
        return response.profile_session;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to submit resume file.");
        throw error;
      } finally {
        this.isSubmitting = false;
      }
    },
    async ensureSession(): Promise<ProfileSession> {
      if (this.session) {
        return this.session;
      }
      return this.createSession();
    },
    async loadParsedReview(sessionId: string): Promise<ParsedResumeReview> {
      this.isReviewLoading = true;
      this.error = null;
      try {
        const response = await getParsedResumeReview(sessionId);
        this.session = response.profile_session;
        this.parsedReview = response.parsed_review;
        return response.parsed_review;
      } catch (error) {
        this.parsedReview = null;
        this.error = toApiErrorMessage(error, "Failed to load parsed resume review.");
        throw error;
      } finally {
        this.isReviewLoading = false;
      }
    },
    async analyzeResume(sessionId: string, regenerate = false): Promise<ParsedResumeReview> {
      this.isReviewLoading = true;
      this.error = null;
      try {
        const response = await parseResumeForReview(sessionId, regenerate);
        this.session = response.profile_session;
        this.parsedReview = response.parsed_review;
        return response.parsed_review;
      } catch (error) {
        this.parsedReview = null;
        this.error = toApiErrorMessage(error, "Failed to analyze resume.");
        throw error;
      } finally {
        this.isReviewLoading = false;
      }
    }
  }
});

function toApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof AxiosError) {
    return (error.response?.data as ApiErrorPayload | undefined)?.detail ?? fallback;
  }
  return error instanceof Error ? error.message : fallback;
}
