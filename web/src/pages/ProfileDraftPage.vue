<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NInput } from "naive-ui";

import StepProgress from "../components/StepProgress.vue";
import { useProfileSessionStore } from "../stores/profileSession";
import type { ProfileDraft } from "../types/profileSession";

const route = useRoute();
const router = useRouter();
const profileSessionStore = useProfileSessionStore();
const sessionId = computed(() => String(route.params.sessionId ?? ""));
const saveMessage = ref<string | null>(null);
const confirmMessage = ref<string | null>(null);
const sessionUnavailable = computed(
  () => profileSessionStore.hasLoadedSession && !profileSessionStore.session
);

const form = reactive({
  summary: "",
  target_roles: "",
  target_directions: "",
  core_skills: "",
  supporting_skills: "",
  search_keywords: "",
  preferred_locations: "",
  work_arrangements: "",
  strengths: "",
  risks: "",
  missing_info_questions: ""
});

function syncForm(draft: ProfileDraft) {
  form.summary = draft.summary;
  form.target_roles = draft.target_roles.join("\n");
  form.target_directions = draft.target_directions.join("\n");
  form.core_skills = draft.core_skills.join("\n");
  form.supporting_skills = draft.supporting_skills.join("\n");
  form.search_keywords = draft.search_keywords.join("\n");
  form.preferred_locations = draft.preferred_locations.join("\n");
  form.work_arrangements = draft.work_arrangements.join("\n");
  form.strengths = draft.strengths.join("\n");
  form.risks = draft.risks.join("\n");
  form.missing_info_questions = draft.missing_info_questions.join("\n");
}

function toList(value: string) {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

async function loadDraftPage() {
  saveMessage.value = null;
  confirmMessage.value = null;
  try {
    const session = await profileSessionStore.loadSession(sessionId.value);
    if (session.profile_draft_id) {
      syncForm(await profileSessionStore.loadDraft(session.profile_draft_id));
      return;
    }
    syncForm(await profileSessionStore.createDraft(sessionId.value, false));
  } catch {
    // Error state is rendered from the store.
  }
}

onMounted(() => {
  void loadDraftPage();
});

async function saveDraft() {
  const draftId = profileSessionStore.profileDraft?.profile_draft_id;
  if (!draftId) {
    return;
  }

  saveMessage.value = null;
  confirmMessage.value = null;
  try {
    const updated = await profileSessionStore.saveDraft(draftId, {
      summary: form.summary.trim(),
      target_roles: toList(form.target_roles),
      target_directions: toList(form.target_directions),
      core_skills: toList(form.core_skills),
      supporting_skills: toList(form.supporting_skills),
      search_keywords: toList(form.search_keywords),
      preferred_locations: toList(form.preferred_locations),
      work_arrangements: toList(form.work_arrangements),
      strengths: toList(form.strengths),
      risks: toList(form.risks),
      missing_info_questions: toList(form.missing_info_questions)
    });
    syncForm(updated);
    saveMessage.value = "Profile draft saved.";
  } catch {
    // Error state is rendered from the store.
  }
}

async function confirmProfile() {
  const draftId = profileSessionStore.profileDraft?.profile_draft_id;
  if (!draftId) {
    return;
  }

  saveMessage.value = null;
  confirmMessage.value = null;
  try {
    const updated = await profileSessionStore.saveDraft(draftId, {
      summary: form.summary.trim(),
      target_roles: toList(form.target_roles),
      target_directions: toList(form.target_directions),
      core_skills: toList(form.core_skills),
      supporting_skills: toList(form.supporting_skills),
      search_keywords: toList(form.search_keywords),
      preferred_locations: toList(form.preferred_locations),
      work_arrangements: toList(form.work_arrangements),
      strengths: toList(form.strengths),
      risks: toList(form.risks),
      missing_info_questions: toList(form.missing_info_questions)
    });
    syncForm(updated);
    await profileSessionStore.confirmDraft(draftId);
    await router.push({ name: "profile-confirmed", params: { sessionId: sessionId.value } });
  } catch {
    // Error state is rendered from the store.
  }
}

function goBackToReview() {
  void router.push({ name: "profile-review", params: { sessionId: sessionId.value } });
}
</script>

<template>
  <section class="flow-page">
    <h1>Profile Draft</h1>
    <p class="flow-message">
      Convert the parsed resume review into an editable candidate profile before downstream
      confirmation and job search.
    </p>
    <p class="flow-meta">Session {{ sessionId }}</p>
    <StepProgress :active-index="1" />

    <div v-if="profileSessionStore.error" class="error-banner">
      {{ profileSessionStore.error }}
    </div>

    <div v-if="sessionUnavailable" class="review-empty-state">
      <p class="flow-message">
        This profile session could not be loaded. Start from Resume Intake to create a new session.
      </p>
      <n-button type="primary" @click="goBackToReview">Back to Profile Review</n-button>
    </div>

    <div v-else class="draft-layout">
      <div class="review-actions">
        <n-button secondary @click="goBackToReview">Back to Review</n-button>
        <n-button
          type="primary"
          :loading="profileSessionStore.isDraftSaving"
          :disabled="profileSessionStore.isDraftLoading || !profileSessionStore.profileDraft"
          @click="saveDraft"
        >
          Save Draft
        </n-button>
        <n-button
          tertiary
          :loading="profileSessionStore.isConfirming"
          :disabled="profileSessionStore.isDraftLoading || !profileSessionStore.profileDraft"
          @click="confirmProfile"
        >
          Confirm Profile
        </n-button>
      </div>

      <p v-if="saveMessage" class="flow-meta">{{ saveMessage }}</p>
      <p v-if="confirmMessage" class="flow-meta">{{ confirmMessage }}</p>

      <div
        v-if="profileSessionStore.isDraftLoading && !profileSessionStore.profileDraft"
        class="review-empty-state"
      >
        <p class="flow-message">Preparing profile draft...</p>
      </div>

      <div v-else-if="profileSessionStore.profileDraft" class="draft-grid">
        <n-card title="Narrative" size="small">
          <label class="draft-field">
            <span>Summary</span>
            <n-input v-model:value="form.summary" type="textarea" :rows="4" />
          </label>
        </n-card>

        <n-card title="Role Targeting" size="small">
          <label class="draft-field">
            <span>Target Roles</span>
            <n-input v-model:value="form.target_roles" type="textarea" :rows="4" />
          </label>
          <label class="draft-field">
            <span>Target Directions</span>
            <n-input v-model:value="form.target_directions" type="textarea" :rows="4" />
          </label>
        </n-card>

        <n-card title="Skills and Search" size="small">
          <label class="draft-field">
            <span>Core Skills</span>
            <n-input v-model:value="form.core_skills" type="textarea" :rows="4" />
          </label>
          <label class="draft-field">
            <span>Supporting Skills</span>
            <n-input v-model:value="form.supporting_skills" type="textarea" :rows="4" />
          </label>
          <label class="draft-field">
            <span>Search Keywords</span>
            <n-input v-model:value="form.search_keywords" type="textarea" :rows="4" />
          </label>
        </n-card>

        <n-card title="Preferences" size="small">
          <label class="draft-field">
            <span>Preferred Locations</span>
            <n-input v-model:value="form.preferred_locations" type="textarea" :rows="3" />
          </label>
          <label class="draft-field">
            <span>Work Arrangements</span>
            <n-input v-model:value="form.work_arrangements" type="textarea" :rows="3" />
          </label>
        </n-card>

        <n-card title="Signals to Carry Forward" size="small">
          <label class="draft-field">
            <span>Strengths</span>
            <n-input v-model:value="form.strengths" type="textarea" :rows="4" />
          </label>
          <label class="draft-field">
            <span>Risks</span>
            <n-input v-model:value="form.risks" type="textarea" :rows="4" />
          </label>
          <label class="draft-field">
            <span>Missing Info Questions</span>
            <n-input
              v-model:value="form.missing_info_questions"
              type="textarea"
              :rows="4"
            />
          </label>
        </n-card>
      </div>

    </div>
  </section>
</template>
