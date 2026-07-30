<script setup lang="ts">
/**
 * 编辑并确认搜索意图；保存结果落到后端 mission，确认后通知父页面刷新搜索预览。
 */
import { computed, onMounted, ref, watch } from "vue";
import { AxiosError } from "axios";
import {
  NCard,
  NCheckbox,
  NCollapse,
  NCollapseItem,
  NInput,
  NSelect
} from "naive-ui";

import {
  confirmSearchMission,
  getSearchMission,
  interpretSearchMission,
  saveSearchMission
} from "../api/profileSessions";
import type {
  ConfirmedProfile,
  LlmProviderName,
  SearchMission,
  SearchMissionExplorationLevel,
  SearchMissionInput
} from "../types/profileSession";

type ListField = Exclude<
  keyof SearchMissionInput,
  "exploration_level" | "free_text" | "clarification_answers"
>;

const props = defineProps<{
  sessionId: string;
  profile: ConfirmedProfile | null;
}>();

const emit = defineEmits<{
  (event: "busy-change", value: boolean): void;
}>();

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
const mission = ref<SearchMission | null>(null);
const message = ref<string | null>(null);
const hasLoaded = ref(false);
const hasExistingMission = ref(false);
const acceptedConflictSignature = ref<string | null>(null);
const conflictSignature = computed(() => {
  const conflicts = mission.value?.mission.conflicts ?? [];
  return conflicts.length
    ? buildConflictSignature(buildPayload(), conflicts)
    : null;
});
const conflictsAccepted = computed({
  get: () => (
    conflictSignature.value !== null
    && acceptedConflictSignature.value === conflictSignature.value
  ),
  set: (accepted: boolean) => {
    acceptedConflictSignature.value = accepted ? conflictSignature.value : null;
  }
});

const explorationOptions = [
  { label: "Focused", value: "focused" },
  { label: "Balanced", value: "balanced" },
  { label: "Exploratory", value: "exploratory" }
];

onMounted(async () => {
  setBusy(true);
  try {
    applyMission(await getSearchMission(props.sessionId));
    hasExistingMission.value = true;
  } catch (error) {
    if (!(error instanceof AxiosError) || error.response?.status !== 404) {
      message.value = "Saved search preferences could not be loaded.";
    }
    applyProfileDefaults();
  } finally {
    hasLoaded.value = true;
    setBusy(false);
  }
});

watch(
  () => props.profile,
  () => {
    if (hasLoaded.value && !hasExistingMission.value) {
      applyProfileDefaults();
    }
  }
);

function setBusy(value: boolean): void {
  emit("busy-change", value);
}

function applyMission(value: SearchMission): void {
  mission.value = value;
  listText.value.target_roles = value.input.target_roles.join(", ");
  listText.value.excluded_roles = value.input.excluded_roles.join(", ");
  listText.value.preferred_industries = value.input.preferred_industries.join(", ");
  listText.value.locations = value.input.locations.join(", ");
  listText.value.work_arrangements = value.input.work_arrangements.join(", ");
  listText.value.employment_types = value.input.employment_types.join(", ");
  listText.value.must_have = value.input.must_have.join(", ");
  listText.value.nice_to_have = value.input.nice_to_have.join(", ");
  listText.value.ranking_priorities = value.input.ranking_priorities.join(", ");
  explorationLevel.value = value.input.exploration_level;
  freeText.value = value.input.free_text ?? "";
  clarificationAnswers.value = Object.fromEntries(
    value.input.clarification_answers.map((item) => [item.question, item.answer])
  );
  if (value.status === "confirmed" && value.mission.conflicts.length) {
    // 已确认的历史 mission 代表用户接受过这些冲突；字段一旦变化，签名会自动失效。
    acceptedConflictSignature.value = buildConflictSignature(
      buildPayload(),
      value.mission.conflicts
    );
  }
}

function applyProfileDefaults(): void {
  const profile = props.profile;
  if (!profile) {
    return;
  }
  listText.value.target_roles = profile.target_roles.join(", ");
  listText.value.locations = profile.preferred_locations.join(", ");
  listText.value.work_arrangements = profile.work_arrangements.join(", ");
  listText.value.nice_to_have = profile.search_keywords.join(", ");
}

function buildPayload(): SearchMissionInput {
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

async function prepareForSearch(
  useLlm: boolean,
  llmProvider: LlmProviderName
): Promise<SearchMission> {
  message.value = null;
  const input = buildPayload();
  if (!input.target_roles.length) {
    message.value = "Add at least one target role before starting the search.";
    throw new Error(message.value);
  }

  setBusy(true);
  try {
    // 依次保存原始输入、生成结构化解释并确认，run 因而只消费稳定的 mission revision。
    await saveSearchMission(props.sessionId, input);
    const interpreted = await interpretSearchMission(
      props.sessionId,
      useLlm,
      llmProvider
    );
    applyMission(interpreted);
    const unansweredQuestions = interpreted.mission.clarification_questions.filter(
      (question) => !clarificationAnswers.value[question]?.trim()
    );
    if (unansweredQuestions.length) {
      // 先把问题留在当前页面，用户补充后再次启动；不能静默确认含歧义的 mission。
      message.value = "Answer the required clarifications before starting the search.";
      throw new Error(message.value);
    }
    if (interpreted.mission.conflicts.length && !conflictsAccepted.value) {
      message.value = "Review the detected conflicts and confirm that you want to continue.";
      throw new Error(message.value);
    }
    const confirmed = await confirmSearchMission(props.sessionId);
    applyMission(confirmed);
    hasExistingMission.value = true;
    return confirmed;
  } catch (error) {
    if (!message.value) {
      message.value = error instanceof Error
        ? error.message
        : "Search preferences could not be prepared.";
    }
    throw error;
  } finally {
    setBusy(false);
  }
}

function toList(value: string): string[] {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildConflictSignature(
  input: SearchMissionInput,
  conflicts: string[]
): string {
  return JSON.stringify({ input, conflicts });
}

defineExpose({ prepareForSearch });
</script>

<template>
  <n-card title="What are you looking for?" size="small" class="job-search-intent-card">
    <p class="flow-meta">
      Defaults come from the confirmed profile. Changes here apply only to this search.
    </p>

    <div class="search-mission-grid">
      <label class="draft-field">
        <span>Target Roles *</span>
        <n-input
          v-model:value="listText.target_roles"
          placeholder="AI Application Engineer, Backend Engineer"
        />
      </label>
      <label class="draft-field">
        <span>Locations</span>
        <n-input v-model:value="listText.locations" placeholder="Shenzhen, Remote" />
      </label>
      <label class="draft-field">
        <span>Must Have</span>
        <n-input v-model:value="listText.must_have" placeholder="Python, LLM applications" />
      </label>
      <label class="draft-field">
        <span>Exclude</span>
        <n-input v-model:value="listText.excluded_roles" placeholder="Sales, Pure research" />
      </label>
    </div>

    <n-collapse class="job-search-advanced">
      <n-collapse-item title="More preferences" name="more-preferences">
        <div class="search-mission-grid">
          <label class="draft-field">
            <span>Industries</span>
            <n-input
              v-model:value="listText.preferred_industries"
              placeholder="Healthcare, Developer tools"
            />
          </label>
          <label class="draft-field">
            <span>Work Arrangements</span>
            <n-input
              v-model:value="listText.work_arrangements"
              placeholder="Hybrid, Remote"
            />
          </label>
          <label class="draft-field">
            <span>Employment Types</span>
            <n-input
              v-model:value="listText.employment_types"
              placeholder="Internship, Full-time"
            />
          </label>
          <label class="draft-field">
            <span>Nice to Have</span>
            <n-input
              v-model:value="listText.nice_to_have"
              placeholder="FastAPI, Healthcare data"
            />
          </label>
          <label class="draft-field">
            <span>Ranking Priorities</span>
            <n-input
              v-model:value="listText.ranking_priorities"
              placeholder="Role fit, Learning opportunity, Location"
            />
          </label>
          <label class="draft-field">
            <span>Exploration</span>
            <n-select v-model:value="explorationLevel" :options="explorationOptions" />
          </label>
          <label class="draft-field search-mission-statement">
            <span>Additional Context</span>
            <n-input v-model:value="freeText" type="textarea" :rows="3" maxlength="2000" />
          </label>
        </div>
      </n-collapse-item>
    </n-collapse>

    <div v-if="mission?.mission.conflicts.length" class="search-mission-questions">
      <strong>Review detected conflicts</strong>
      <ul class="flow-list">
        <li v-for="conflict in mission.mission.conflicts" :key="conflict">
          {{ conflict }}
        </li>
      </ul>
      <n-checkbox v-model:checked="conflictsAccepted">
        I understand these conflicts and want to continue.
      </n-checkbox>
    </div>

    <div
      v-if="mission?.mission.clarification_questions.length"
      class="search-mission-questions"
    >
      <strong>Required clarifications</strong>
      <div class="search-mission-grid">
        <label
          v-for="question in mission.mission.clarification_questions"
          :key="question"
          class="draft-field"
        >
          <span>{{ question }}</span>
          <n-input
            v-model:value="clarificationAnswers[question]"
            type="textarea"
            :rows="2"
          />
        </label>
      </div>
    </div>

    <p v-if="message" class="error-note">{{ message }}</p>
  </n-card>
</template>
