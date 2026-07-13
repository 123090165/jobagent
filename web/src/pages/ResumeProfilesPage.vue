<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { NButton, NCard, NPopconfirm, NSwitch, NTag } from "naive-ui";

import FlowPageHeader from "../components/FlowPageHeader.vue";
import { useResumeProfilesStore } from "../stores/resumeProfiles";
import type { ResumeProfile } from "../types/resumeProfile";

const router = useRouter();
const resumeProfilesStore = useResumeProfilesStore();
const includeArchived = ref(false);
const actionMessage = ref<string | null>(null);

const activeProfiles = computed(() => resumeProfilesStore.items.filter((item) => !item.archived_at));
const archivedCount = computed(() => resumeProfilesStore.items.filter((item) => item.archived_at).length);
const profileStats = computed(() => ({
  total: resumeProfilesStore.items.length,
  active: activeProfiles.value.length,
  defaults: resumeProfilesStore.items.filter((item) => item.is_default).length,
  archived: archivedCount.value
}));

onMounted(() => {
  void loadProfiles();
});

watch(includeArchived, () => {
  void loadProfiles();
});

async function loadProfiles() {
  actionMessage.value = null;
  try {
    await resumeProfilesStore.loadProfiles(includeArchived.value);
  } catch {
    // Error state is rendered from the store.
  }
}

async function makeDefault(profile: ResumeProfile) {
  actionMessage.value = null;
  try {
    await resumeProfilesStore.makeDefault(profile.resume_profile_id);
    actionMessage.value = `${profile.name} is now the default profile.`;
  } catch {
    // Error state is rendered from the store.
  }
}

async function archiveProfile(profile: ResumeProfile) {
  actionMessage.value = null;
  try {
    await resumeProfilesStore.archiveProfile(profile.resume_profile_id);
    actionMessage.value = `${profile.name} archived.`;
  } catch {
    // Error state is rendered from the store.
  }
}

async function restoreProfile(profile: ResumeProfile) {
  actionMessage.value = null;
  try {
    await resumeProfilesStore.restoreProfile(profile.resume_profile_id);
    actionMessage.value = `${profile.name} restored.`;
  } catch {
    // Error state is rendered from the store.
  }
}

async function deleteProfile(profile: ResumeProfile) {
  actionMessage.value = null;
  try {
    await resumeProfilesStore.deleteProfile(profile.resume_profile_id);
    actionMessage.value = `${profile.name} deleted. Search and saved-job records remain.`;
  } catch {
    // Error state is rendered from the store.
  }
}

function startNewProfile() {
  void router.push({ name: "home" });
}

function openSourceProfile(profile: ResumeProfile) {
  if (!profile.source_session_id) {
    return;
  }
  void router.push({
    name: "profile-confirmed",
    params: { sessionId: profile.source_session_id }
  });
}

function formatDate(value: string | null): string {
  if (!value) {
    return "Not set";
  }
  return new Date(value).toLocaleString();
}
</script>

<template>
  <section class="flow-page flow-page-wide">
    <FlowPageHeader
      eyebrow="Library"
      title="Resume Profile Library"
      description="Manage confirmed resume profiles saved under the current account."
      meta="User data"
      :active-step="0"
    />

    <div v-if="resumeProfilesStore.error" class="error-banner">
      {{ resumeProfilesStore.error }}
    </div>

    <div class="workspace-panel">
      <div class="panel-heading">
        <div>
          <h2>Stored profiles</h2>
          <p>{{ activeProfiles.length }} active profiles available for search workflows.</p>
        </div>
        <div class="flow-toolbar-secondary">
          <div class="setting-control">
            <span class="flow-meta">Archived</span>
            <n-switch v-model:value="includeArchived" />
          </div>
          <n-button secondary :loading="resumeProfilesStore.isLoading" @click="loadProfiles">
            Refresh
          </n-button>
          <n-button type="primary" @click="startNewProfile">New Profile</n-button>
        </div>
      </div>
    </div>

    <div class="metric-grid">
      <div class="metric-card">
        <span>Total</span>
        <strong>{{ profileStats.total }}</strong>
      </div>
      <div class="metric-card">
        <span>Active</span>
        <strong>{{ profileStats.active }}</strong>
      </div>
      <div class="metric-card">
        <span>Default</span>
        <strong>{{ profileStats.defaults }}</strong>
      </div>
      <div class="metric-card">
        <span>Archived</span>
        <strong>{{ profileStats.archived }}</strong>
      </div>
    </div>

    <p v-if="actionMessage" class="flow-meta library-message">{{ actionMessage }}</p>

    <div
      v-if="resumeProfilesStore.isLoading && resumeProfilesStore.items.length === 0"
      class="review-empty-state"
    >
      <p class="flow-message">Loading resume profiles...</p>
    </div>

    <div v-else-if="resumeProfilesStore.items.length === 0" class="review-empty-state">
      <p class="flow-message">
        No resume profile has been confirmed yet. Start with resume intake and confirm a profile.
      </p>
      <n-button type="primary" @click="startNewProfile">Create First Profile</n-button>
    </div>

    <div v-else class="library-grid">
      <n-card
        v-for="profile in resumeProfilesStore.items"
        :key="profile.resume_profile_id"
        size="small"
        class="library-card"
      >
        <div class="job-card-header">
          <div>
            <h2 class="job-card-title">{{ profile.name }}</h2>
            <p class="job-card-company">Updated {{ formatDate(profile.updated_at) }}</p>
          </div>
          <div class="trace-step-tags">
            <n-tag v-if="profile.is_default" type="success" round>Default</n-tag>
            <n-tag v-if="profile.archived_at" type="warning" round>Archived</n-tag>
          </div>
        </div>

        <p class="confirmed-summary">{{ profile.summary || "No summary saved." }}</p>

        <div class="job-card-section">
          <strong>Target Roles</strong>
          <div class="job-chip-row">
            <n-tag v-for="role in profile.target_roles" :key="role" size="small" round>
              {{ role }}
            </n-tag>
            <span v-if="!profile.target_roles.length" class="flow-meta">Not set</span>
          </div>
        </div>

        <div class="job-card-section">
          <strong>Core Skills</strong>
          <div class="job-chip-row">
            <n-tag v-for="skill in profile.core_skills" :key="skill" size="small" round>
              {{ skill }}
            </n-tag>
            <span v-if="!profile.core_skills.length" class="flow-meta">Not set</span>
          </div>
        </div>

        <div class="job-card-section">
          <strong>Search Keywords</strong>
          <div class="job-chip-row">
            <n-tag v-for="keyword in profile.search_keywords" :key="keyword" size="small" round>
              {{ keyword }}
            </n-tag>
            <span v-if="!profile.search_keywords.length" class="flow-meta">Not set</span>
          </div>
        </div>

        <div class="job-card-footer">
          <span>{{ profile.resume_profile_id }}</span>
          <div class="flow-toolbar-secondary">
            <n-popconfirm @positive-click="deleteProfile(profile)">
              <template #trigger>
                <n-button size="small" tertiary type="error" :loading="resumeProfilesStore.isSaving">
                  Delete
                </n-button>
              </template>
              Permanently delete this profile library entry? Searches and saved jobs will remain.
            </n-popconfirm>
            <n-button
              size="small"
              secondary
              :disabled="profile.is_default || Boolean(profile.archived_at)"
              :loading="resumeProfilesStore.isSaving"
              @click="makeDefault(profile)"
            >
              Set Default
            </n-button>
            <n-button
              size="small"
              secondary
              :disabled="!profile.source_session_id"
              @click="openSourceProfile(profile)"
            >
              Open Source
            </n-button>
            <n-button
              v-if="!profile.archived_at"
              size="small"
              tertiary
              :loading="resumeProfilesStore.isSaving"
              @click="archiveProfile(profile)"
            >
              Archive
            </n-button>
            <n-button
              v-if="profile.archived_at"
              size="small"
              secondary
              :loading="resumeProfilesStore.isSaving"
              @click="restoreProfile(profile)"
            >
              Restore
            </n-button>
          </div>
        </div>
      </n-card>
    </div>
  </section>
</template>
