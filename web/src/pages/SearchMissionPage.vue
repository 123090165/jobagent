<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { AxiosError } from "axios";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NInput, NSelect, NSwitch, NTag } from "naive-ui";

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

type ListField = Exclude<keyof SearchMissionInput, "exploration_level" | "free_text">;

const route = useRoute();
const router = useRouter();
const store = useProfileSessionStore();
const sessionId = computed(() => String(route.params.sessionId ?? ""));
const mission = ref<SearchMission | null>(null);
const isLoading = ref(true);
const isSaving = ref(false);
const useLlm = ref(true);
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
const explorationOptions = [
  { label: "Focused", value: "focused" },
  { label: "Balanced", value: "balanced" },
  { label: "Exploratory", value: "exploratory" }
];
const fields: Array<{ key: ListField; label: string; placeholder: string }> = [
  { key: "target_roles", label: "Target Roles", placeholder: "AI Application Engineer, Backend Engineer" },
  { key: "excluded_roles", label: "Excluded Roles", placeholder: "Pure research, Sales" },
  { key: "preferred_industries", label: "Industries", placeholder: "Healthcare, Developer tools" },
  { key: "locations", label: "Locations", placeholder: "Shenzhen, Remote" },
  { key: "work_arrangements", label: "Work Arrangements", placeholder: "Hybrid, Remote" },
  { key: "employment_types", label: "Employment Types", placeholder: "Internship, Full-time" },
  { key: "must_have", label: "Must Have", placeholder: "LLM application work, Python" },
  { key: "nice_to_have", label: "Nice to Have", placeholder: "Healthcare data, FastAPI" },
  { key: "ranking_priorities", label: "Ranking Priorities", placeholder: "Role fit, Learning opportunity, Location" }
];

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
  for (const field of fields) listText.value[field.key] = value.input[field.key].join(", ");
  explorationLevel.value = value.input.exploration_level;
  freeText.value = value.input.free_text ?? "";
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
    free_text: freeText.value.trim() || null
  };
}

async function analyzeMission() {
  isSaving.value = true;
  message.value = null;
  try {
    await saveSearchMission(sessionId.value, payload());
    applyMission(await interpretSearchMission(sessionId.value, useLlm.value));
    message.value = "Mission interpreted. Review conflicts and questions before confirmation.";
  } catch {
    message.value = "Mission interpretation failed.";
  } finally {
    isSaving.value = false;
  }
}

async function confirmMission() {
  isSaving.value = true;
  message.value = null;
  try {
    await saveSearchMission(sessionId.value, payload());
    mission.value = await interpretSearchMission(sessionId.value, useLlm.value);
    mission.value = await confirmSearchMission(sessionId.value);
    await router.push({ name: "search-preview", params: { sessionId: sessionId.value } });
  } catch {
    message.value = "At least one interpreted target role is required before confirmation.";
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
      title="Search Mission"
      description="Define what you want now, separately from what your resume proves."
      :meta="`Session ${sessionId}`"
      :active-step="4"
    />

    <div v-if="message" class="flow-meta library-message">{{ message }}</div>
    <div v-if="isLoading" class="review-empty-state"><p class="flow-message">Loading mission...</p></div>
    <div v-else class="search-mission-layout">
      <div class="workspace-panel intake-panel">
        <div class="panel-heading">
          <div><h2>Current search intent</h2><p>Use commas or new lines for multiple values.</p></div>
          <div class="flow-toolbar-secondary">
            <span class="flow-meta">LLM interpretation</span>
            <n-switch v-model:value="useLlm" />
          </div>
        </div>
        <div class="search-mission-grid">
          <label v-for="field in fields" :key="field.key" class="draft-field">
            <span>{{ field.label }}</span>
            <n-input v-model:value="listText[field.key]" :placeholder="field.placeholder" />
          </label>
          <label class="draft-field">
            <span>Exploration Level</span>
            <n-select v-model:value="explorationLevel" :options="explorationOptions" />
          </label>
          <label class="draft-field search-mission-statement">
            <span>What are you trying to achieve?</span>
            <n-input v-model:value="freeText" type="textarea" :rows="4" maxlength="2000" />
          </label>
        </div>
        <div class="flow-toolbar">
          <n-button secondary @click="router.push({ name: 'profile-confirmed', params: { sessionId } })">Back to Profile</n-button>
          <div class="flow-toolbar-secondary">
            <n-button secondary :loading="isSaving" @click="analyzeMission">Interpret Mission</n-button>
            <n-button type="primary" :loading="isSaving" @click="confirmMission">Confirm and Preview</n-button>
          </div>
        </div>
      </div>

      <template v-if="mission?.status === 'review' || mission?.status === 'confirmed'">
        <n-card title="Agent Interpretation" size="small">
          <div class="job-chip-row">
            <n-tag round>{{ mission.analysis_mode }}</n-tag>
            <n-tag v-if="mission.analysis_provider" round>{{ mission.analysis_provider }}</n-tag>
            <n-tag :type="mission.status === 'confirmed' ? 'success' : 'warning'" round>{{ mission.status }}</n-tag>
          </div>
          <p v-if="mission.fallback_reason"><strong>Fallback:</strong> {{ mission.fallback_reason }}</p>
          <div class="mission-summary-grid">
            <div><strong>Target Roles</strong><p>{{ mission.mission.target_roles.join(", ") || "Not set" }}</p></div>
            <div><strong>Adjacent Roles</strong><p>{{ mission.mission.adjacent_roles.join(", ") || "None" }}</p></div>
            <div><strong>Hard Constraints</strong><p>{{ mission.mission.hard_constraints.join(", ") || "None" }}</p></div>
            <div><strong>Ranking Priorities</strong><p>{{ mission.mission.ranking_priorities.join(", ") || "Not set" }}</p></div>
          </div>
        </n-card>
        <n-card v-if="mission.mission.conflicts.length" title="Conflicts" size="small">
          <ul class="review-list"><li v-for="item in mission.mission.conflicts" :key="item">{{ item }}</li></ul>
        </n-card>
        <n-card v-if="mission.mission.clarification_questions.length" title="Questions to Resolve" size="small">
          <ul class="review-list"><li v-for="item in mission.mission.clarification_questions" :key="item">{{ item }}</li></ul>
        </n-card>
        <n-card v-if="mission.mission.assumptions.length" title="Assumptions" size="small">
          <ul class="review-list"><li v-for="item in mission.mission.assumptions" :key="item">{{ item }}</li></ul>
        </n-card>
      </template>
    </div>
  </section>
</template>
