import { defineStore } from "pinia";
import { AxiosError } from "axios";

import {
  confirmProfileDraft,
  createProfileDraft,
  createProfileSession,
  getConfirmedProfile,
  getParsedResumeReview,
  getProfileDraft,
  getProfileSession,
  parseResumeForReview,
  submitResumeFile,
  submitResumeText,
  updateProfileDraft
} from "../api/profileSessions";
import type {
  ConfirmedProfile,
  ParsedResumeReview,
  ProfileDraft,
  ProfileSession,
  ResumeDocument,
  UpdateProfileDraftPayload
} from "../types/profileSession";

interface ProfileSessionState {
  session: ProfileSession | null;
  resumeDocument: ResumeDocument | null;
  parsedReview: ParsedResumeReview | null;
  profileDraft: ProfileDraft | null;
  confirmedProfile: ConfirmedProfile | null;
  isCreating: boolean;
  isSubmitting: boolean;
  isReviewLoading: boolean;
  isDraftLoading: boolean;
  isDraftSaving: boolean;
  isConfirming: boolean;
  isConfirmedLoading: boolean;
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
    profileDraft: null,
    confirmedProfile: null,
    isCreating: false,
    isSubmitting: false,
    isReviewLoading: false,
    isDraftLoading: false,
    isDraftSaving: false,
    isConfirming: false,
    isConfirmedLoading: false,
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
        if (!this.session.profile_draft_id) {
          this.profileDraft = null;
        }
        if (!this.session.confirmed_profile_id) {
          this.confirmedProfile = null;
        }
        return this.session;
      } catch (error) {
        this.session = null;
        this.resumeDocument = null;
        this.parsedReview = null;
        this.profileDraft = null;
        this.confirmedProfile = null;
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
        this.profileDraft = null;
        this.confirmedProfile = null;
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
        this.profileDraft = null;
        this.confirmedProfile = null;
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
        this.profileDraft = null;
        this.confirmedProfile = null;
        return response.parsed_review;
      } catch (error) {
        this.parsedReview = null;
        this.error = toApiErrorMessage(error, "Failed to analyze resume.");
        throw error;
      } finally {
        this.isReviewLoading = false;
      }
    },
    async createDraft(sessionId: string, regenerate = false): Promise<ProfileDraft> {
      this.isDraftLoading = true;
      this.error = null;
      try {
        const response = await createProfileDraft(sessionId, regenerate);
        this.session = response.profile_session;
        this.profileDraft = response.profile_draft;
        this.confirmedProfile = null;
        return response.profile_draft;
      } catch (error) {
        this.profileDraft = null;
        this.error = toApiErrorMessage(error, "Failed to create profile draft.");
        throw error;
      } finally {
        this.isDraftLoading = false;
      }
    },
    async loadDraft(draftId: string): Promise<ProfileDraft> {
      this.isDraftLoading = true;
      this.error = null;
      try {
        const response = await getProfileDraft(draftId);
        this.session = response.profile_session;
        this.profileDraft = response.profile_draft;
        return response.profile_draft;
      } catch (error) {
        this.profileDraft = null;
        this.error = toApiErrorMessage(error, "Failed to load profile draft.");
        throw error;
      } finally {
        this.isDraftLoading = false;
      }
    },
    async saveDraft(
      draftId: string,
      payload: UpdateProfileDraftPayload
    ): Promise<ProfileDraft> {
      this.isDraftSaving = true;
      this.error = null;
      try {
        const response = await updateProfileDraft(draftId, payload);
        this.session = response.profile_session;
        this.profileDraft = response.profile_draft;
        this.confirmedProfile = null;
        return response.profile_draft;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to save profile draft.");
        throw error;
      } finally {
        this.isDraftSaving = false;
      }
    },
    async confirmDraft(draftId: string): Promise<ConfirmedProfile> {
      this.isConfirming = true;
      this.error = null;
      try {
        const response = await confirmProfileDraft(draftId);
        this.session = response.profile_session;
        this.confirmedProfile = response.confirmed_profile;
        return response.confirmed_profile;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to confirm profile.");
        throw error;
      } finally {
        this.isConfirming = false;
      }
    },
    async loadConfirmedProfile(confirmedProfileId: string): Promise<ConfirmedProfile> {
      this.isConfirmedLoading = true;
      this.error = null;
      try {
        const response = await getConfirmedProfile(confirmedProfileId);
        this.session = response.profile_session;
        this.confirmedProfile = response.confirmed_profile;
        return response.confirmed_profile;
      } catch (error) {
        this.confirmedProfile = null;
        this.error = toApiErrorMessage(error, "Failed to load confirmed profile.");
        throw error;
      } finally {
        this.isConfirmedLoading = false;
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
