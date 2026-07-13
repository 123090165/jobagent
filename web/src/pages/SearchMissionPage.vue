<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { AxiosError } from "axios";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NCollapse, NCollapseItem, NInput, NSelect, NTag } from "naive-ui";

import {
  confirmSearchMission,
  getSearchMission,
  interpretSearchMission,
  saveSearchMission
} from "../api/profileSessions";
import FlowPageHeader from "../components/FlowPageHeader.vue";
import { useProfileSessionStore } from "../stores/profileSession";
import type {
  SearchMission,
  SearchMissionExplorationLevel,
  SearchMissionInput
} from "../types/profileSession";

type ListField = Exclude<keyof SearchMissionInput, "exploration_level" | "free_text" | "clarification_answers">;

const route = useRoute();
const router = useRouter();
const store = useProfileSessionStore();
const sessionId = computed(() => String(route.params.sessionId ?? ""));
const mission = ref<SearchMission | null>(null);
const isLoading = ref(true);
const isSaving = ref(false);
const message = ref<string | null>(null);
const listText = ref<Record<ListField, string>>({
  target_roles: "",
  excluded_roles: "",
  preferred_industries: "",
  locations: "",
  work_arrangements: "",
  employment_types: "",
  must_have: "",
  nice_to_have: "",
  ranking_priorities: ""
});
const explorationLevel = ref<SearchMissionExplorationLevel>("balanced");
const freeText = ref("");
const clarificationAnswers = ref<Record<string, string>>({});
const explorationOptions = [
  { label: "Focused", value: "focused" },
  { label: "Balanced", value: "balanced" },
  { label: "Exploratory", value: "exploratory" }
];
const highImpactFields: Array<{ key: ListField; label: string; placeholder: string }> = [
  { key: "target_roles", label: "Target Roles", placeholder: "AI Application Engineer, Backend Engineer" },
  { key: "excluded_roles", label: "Excluded Roles", placeholder: "Pure research, Sales" },
  { key: "locations", label: "Locations", placeholder: "Shenzhen, Remote" },
  { key: "must_have", label: "Must Have", placeholder: "LLM application work, Python" },
  { key: "ranking_priorities", label: "Ranking Priorities", placeholder: "Role fit, Learning opportunity, Location" }
];
const advancedFields: Array<{ key: ListField; label: string; placeholder: string }> = [
  { key: "preferred_industries", label: "Industries", placeholder: "Healthcare, Developer tools" },
  { key: "work_arrangements", label: "Work Arrangements", placeholder: "Hybrid, Remote" },
  { key: "employment_types", label: "Employment Types", placeholder: "Internship, Full-time" },
  { key: "nice_to_have", label: "Nice to Have", placeholder: "Healthcare data, FastAPI" }
];
const allFields = [...highImpactFields, ...advancedFields];
const needsConfirmation = computed(() => Boolean(
  mission.value?.mission.conflicts.length || unansweredQuestions.value.length
));
const unansweredQuestions = computed(() => (
  mission.value?.mission.clarification_questions.filter(
    (question) => !clarificationAnswers.value[question]?.trim()
  ) ?? []
));

onMounted(async () => {
  try {
    const session = await store.loadSession(sessionId.value);
    if (session.confirmed_profile_id) await store.loadConfirmedProfile(session.confirmed_profile_id);
    try {
      applyMission(await getSearchMission(sessionId.value));
    } catch (error) {
      if (!(error instanceof AxiosError) || error.response?.status !== 404) throw error;
      applyProfileDefaults();
    }
  } catch {
    message.value = "Search Mission could not be loaded.";
  } finally {
    isLoading.value = false;
  }
});

function applyMission(value: SearchMission) {
  mission.value = value;
  for (const field of allFields) listText.value[field.key] = value.input[field.key].join(", ");
  explorationLevel.value = value.input.exploration_level;
  freeText.value = value.input.free_text ?? "";
  clarificationAnswers.value = Object.fromEntries(
    value.input.clarification_answers.map((item) => [item.question, item.answer])
  );
}

function applyProfileDefaults() {
  const profile = store.confirmedProfile;
  if (!profile) return;
  listText.value.target_roles = profile.target_roles.join(", ");
  listText.value.locations = profile.preferred_locations.join(", ");
  listText.value.work_arrangements = profile.work_arrangements.join(", ");
  listText.value.nice_to_have = profile.search_keywords.join(", ");
}

function payload(): SearchMissionInput {
  return {
    target_roles: toList(listText.value.target_roles),
    excluded_roles: toList(listText.value.excluded_roles),
    preferred_industries: toList(listText.value.preferred_industries),
    locations: toList(listText.value.locations),
    work_arrangements: toList(listText.value.work_arrangements),
    employment_types: toList(listText.value.employment_types),
    must_have: toList(listText.value.must_have),
    nice_to_have: toList(listText.value.nice_to_have),
    ranking_priorities: toList(listText.value.ranking_priorities),
    exploration_level: explorationLevel.value,
    free_text: freeText.value.trim() || null,
    clarification_answers: Object.entries(clarificationAnswers.value)
      .filter(([, answer]) => answer.trim())
      .map(([question, answer]) => ({ question, answer: answer.trim() }))
  };
}

async function continueToSources() {
  isSaving.value = true;
  message.value = null;
  try {
    await saveSearchMission(sessionId.value, payload());
    applyMission(await interpretSearchMission(sessionId.value, true));
    if (needsConfirmation.value) {
      message.value = unansweredQuestions.value.length
        ? "Answer the highlighted preferences before continuing."
        : "Review the remaining search conflict before continuing.";
      return;
    }
    await confirmAndOpenPreview();
  } catch {
    message.value = "Search setup could not be prepared.";
  } finally {
    isSaving.value = false;
  }
}

async function confirmAndOpenPreview() {
  mission.value = await confirmSearchMission(sessionId.value);
  await router.push({ name: "search-preview", params: { sessionId: sessionId.value } });
}

async function acceptAndContinue() {
  isSaving.value = true;
  message.value = null;
  try {
    await confirmAndOpenPreview();
  } catch {
    message.value = "At least one target role is required before continuing.";
  } finally {
    isSaving.value = false;
  }
}

function toList(value: string): string[] {
  return value.split(/\r?\n|,/).map((item) => item.trim()).filter(Boolean);
}
</script>

<template>
  <section class="flow-page flow-page-wide">
    <FlowPageHeader
      eyebrow="Intent"
      title="Search Setup"
      description="Confirm the few preferences that materially change search recall and ranking."
      :meta="`Session ${sessionId}`"
      :active-step="1"
    />

    <div v-if="message" class="flow-meta library-message">{{ message }}</div>
    <div v-if="isLoading" class="review-empty-state"><p class="flow-message">Loading mission...</p></div>
    <div v-else class="search-mission-layout">
      <div class="workspace-panel intake-panel">
        <div class="panel-heading">
          <div><h2>Search priorities</h2><p>Use commas or new lines for multiple values.</p></div>
        </div>
        <div class="search-mission-grid">
          <label v-for="field in highImpactFields" :key="field.key" class="draft-field">
            <span>{{ field.label }}</span>
            <n-input v-model:value="listText[field.key]" :placeholder="field.placeholder" />
          </label>
          <label class="draft-field">
            <span>Exploration Level</span>
            <n-select v-model:value="explorationLevel" :options="explorationOptions" />
          </label>
        </div>
        <div v-if="mission?.mission.clarification_questions.length" class="search-clarification-fields">
          <div class="panel-heading">
            <div><h2>Preferences to clarify</h2><p>These answers directly update how your search direction is interpreted.</p></div>
          </div>
          <div class="search-mission-grid">
            <label
              v-for="(question, index) in mission.mission.clarification_questions"
              :key="question"
              class="draft-field search-mission-statement"
            >
              <span>{{ index + 1 }}. {{ question }}</span>
              <n-input
                v-model:value="clarificationAnswers[question]"
                type="textarea"
                :rows="2"
                maxlength="2000"
                placeholder="Enter your preference or explain the constraint"
              />
            </label>
          </div>
        </div>
        <n-collapse class="search-setup-advanced">
          <n-collapse-item title="Optional preferences" name="optional-preferences">
            <div class="search-mission-grid">
              <label v-for="field in advancedFields" :key="field.key" class="draft-field">
                <span>{{ field.label }}</span>
                <n-input v-model:value="listText[field.key]" :placeholder="field.placeholder" />
              </label>
              <label class="draft-field search-mission-statement">
                <span>Additional context</span>
                <n-input v-model:value="freeText" type="textarea" :rows="3" maxlength="2000" />
              </label>
            </div>
          </n-collapse-item>
        </n-collapse>
        <div class="flow-toolbar">
          <n-button secondary @click="router.push({ name: 'profile-confirmed', params: { sessionId } })">Back to Profile</n-button>
          <n-button type="primary" :loading="isSaving" @click="continueToSources">
            {{ unansweredQuestions.length ? "Apply Answers & Continue" : "Continue to Sources" }}
          </n-button>
        </div>
      </div>

      <template v-if="needsConfirmation && mission">
        <n-card title="Confirm Search Direction" size="small">
          <div class="job-chip-row">
            <n-tag type="warning" round>Review needed</n-tag>
          </div>
          <div class="mission-summary-grid">
            <div><strong>Target Roles</strong><p>{{ mission.mission.target_roles.join(", ") || "Not set" }}</p></div>
            <div><strong>Adjacent Roles</strong><p>{{ mission.mission.adjacent_roles.join(", ") || "None" }}</p></div>
            <div><strong>Hard Constraints</strong><p>{{ mission.mission.hard_constraints.join(", ") || "None" }}</p></div>
            <div><strong>Ranking Priorities</strong><p>{{ mission.mission.ranking_priorities.join(", ") || "Not set" }}</p></div>
          </div>
          <div class="flow-toolbar">
            <span class="flow-meta">Edit the setup above, or continue with these assumptions.</span>
            <n-button type="primary" :loading="isSaving" @click="acceptAndContinue">Accept and Continue</n-button>
          </div>
        </n-card>
        <n-card v-if="mission.mission.conflicts.length" title="Conflicts" size="small">
          <ul class="review-list"><li v-for="item in mission.mission.conflicts" :key="item">{{ item }}</li></ul>
        </n-card>
      </template>
    </div>
  </section>
</template>
