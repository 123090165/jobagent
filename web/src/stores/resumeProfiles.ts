/**
 * 管理可复用简历画像库的加载、编辑、默认项、归档和删除。
 */
import { defineStore } from "pinia";
import { AxiosError } from "axios";

import {
  archiveResumeProfile,
  deleteResumeProfile,
  getResumeProfile,
  listResumeProfiles,
  restoreResumeProfile,
  setDefaultResumeProfile,
  updateResumeProfile
} from "../api/resumeProfiles";
import type { ResumeProfile, ResumeProfileUpdatePayload } from "../types/resumeProfile";

interface ResumeProfileState {
  items: ResumeProfile[];
  selected: ResumeProfile | null;
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
}

interface ApiErrorPayload {
  detail?: string;
}

export const useResumeProfilesStore = defineStore("resumeProfiles", {
  state: (): ResumeProfileState => ({
    items: [],
    selected: null,
    isLoading: false,
    isSaving: false,
    error: null
  }),
  getters: {
    activeItems: (state) => state.items.filter((item) => !item.archived_at),
    defaultProfile: (state) => state.items.find((item) => item.is_default) ?? null
  },
  actions: {
    async loadProfiles(includeArchived = false): Promise<ResumeProfile[]> {
      this.isLoading = true;
      this.error = null;
      try {
        const response = await listResumeProfiles(includeArchived);
        this.items = response.items;
        return response.items;
      } catch (error) {
        this.items = [];
        this.error = toApiErrorMessage(error, "Failed to load resume profiles.");
        throw error;
      } finally {
        this.isLoading = false;
      }
    },
    async loadProfile(resumeProfileId: string): Promise<ResumeProfile> {
      this.isLoading = true;
      this.error = null;
      try {
        const profile = await getResumeProfile(resumeProfileId);
        this.selected = profile;
        this.mergeProfile(profile);
        return profile;
      } catch (error) {
        this.selected = null;
        this.error = toApiErrorMessage(error, "Failed to load resume profile.");
        throw error;
      } finally {
        this.isLoading = false;
      }
    },
    async saveProfile(
      resumeProfileId: string,
      payload: ResumeProfileUpdatePayload
    ): Promise<ResumeProfile> {
      this.isSaving = true;
      this.error = null;
      try {
        const profile = await updateResumeProfile(resumeProfileId, payload);
        this.mergeProfile(profile);
        if (this.selected?.resume_profile_id === resumeProfileId) {
          this.selected = profile;
        }
        return profile;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to save resume profile.");
        throw error;
      } finally {
        this.isSaving = false;
      }
    },
    async makeDefault(resumeProfileId: string): Promise<ResumeProfile> {
      this.isSaving = true;
      this.error = null;
      try {
        const profile = await setDefaultResumeProfile(resumeProfileId);
        this.items = this.items.map((item) => ({
          ...item,
          is_default: item.resume_profile_id === resumeProfileId
        }));
        this.mergeProfile(profile);
        return profile;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to set default resume profile.");
        throw error;
      } finally {
        this.isSaving = false;
      }
    },
    async archiveProfile(resumeProfileId: string): Promise<ResumeProfile> {
      this.isSaving = true;
      this.error = null;
      try {
        const profile = await archiveResumeProfile(resumeProfileId);
        this.mergeProfile(profile);
        return profile;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to archive resume profile.");
        throw error;
      } finally {
        this.isSaving = false;
      }
    },
    async restoreProfile(resumeProfileId: string): Promise<ResumeProfile> {
      this.isSaving = true;
      this.error = null;
      try {
        const profile = await restoreResumeProfile(resumeProfileId);
        this.mergeProfile(profile);
        return profile;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to restore resume profile.");
        throw error;
      } finally {
        this.isSaving = false;
      }
    },
    async deleteProfile(resumeProfileId: string): Promise<void> {
      this.isSaving = true;
      this.error = null;
      try {
        await deleteResumeProfile(resumeProfileId);
        this.items = this.items.filter((item) => item.resume_profile_id !== resumeProfileId);
        if (this.selected?.resume_profile_id === resumeProfileId) this.selected = null;
      } catch (error) {
        this.error = toApiErrorMessage(error, "Failed to delete resume profile.");
        throw error;
      } finally {
        this.isSaving = false;
      }
    },
    mergeProfile(profile: ResumeProfile): void {
      const index = this.items.findIndex(
        (item) => item.resume_profile_id === profile.resume_profile_id
      );
      if (index === -1) {
        this.items = [profile, ...this.items];
        return;
      }
      this.items.splice(index, 1, profile);
    }
  }
});

function toApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof AxiosError) {
    return (error.response?.data as ApiErrorPayload | undefined)?.detail ?? fallback;
  }
  return error instanceof Error ? error.message : fallback;
}
