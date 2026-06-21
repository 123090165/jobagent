<script setup lang="ts">
import { computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard } from "naive-ui";

import StepProgress from "../components/StepProgress.vue";
import { useProfileSessionStore } from "../stores/profileSession";

const route = useRoute();
const router = useRouter();
const profileSessionStore = useProfileSessionStore();
const sessionId = computed(() => String(route.params.sessionId ?? ""));
const sessionUnavailable = computed(
  () => profileSessionStore.hasLoadedSession && !profileSessionStore.session
);

onMounted(async () => {
  try {
    const session = await profileSessionStore.loadSession(sessionId.value);
    if (session.confirmed_profile_id) {
      await profileSessionStore.loadConfirmedProfile(session.confirmed_profile_id);
    }
  } catch {
    // Error state is rendered from the store.
  }
});

function goBackToDraft() {
  void router.push({ name: "profile-draft", params: { sessionId: sessionId.value } });
}

async function startJobSearch() {
  if (!profileSessionStore.session?.confirmed_profile_id) {
    return;
  }
  void router.push({ name: "search-preview", params: { sessionId: sessionId.value } });
}
</script>

<template>
  <section class="flow-page">
    <h1>Profile Confirmed</h1>
    <p class="flow-message">
      Review the final confirmed profile, choose between the CUHKSZ live board and the local demo path, and launch the next job search run.
    </p>
    <p class="flow-meta">Session {{ sessionId }}</p>
    <StepProgress :active-index="2" />

    <div v-if="profileSessionStore.error" class="error-banner">
      {{ profileSessionStore.error }}
    </div>

    <div v-if="sessionUnavailable" class="review-empty-state">
      <p class="flow-message">
        This profile session could not be loaded. Start from Resume Intake to create a new session.
      </p>
      <n-button type="primary" @click="goBackToDraft">Back to Draft</n-button>
    </div>

    <div v-else-if="!profileSessionStore.session?.confirmed_profile_id" class="review-empty-state">
      <p class="flow-message">
        This session does not have a confirmed profile yet. Confirm the draft first.
      </p>
      <n-button type="primary" @click="goBackToDraft">Back to Draft</n-button>
    </div>

    <div v-else class="confirmed-layout">
      <div class="review-actions">
        <n-button secondary @click="goBackToDraft">Back to Draft</n-button>
        <n-button
          type="primary"
          :disabled="!profileSessionStore.confirmedProfile"
          @click="startJobSearch"
        >
          Preview Job Search
        </n-button>
      </div>

      <div
        v-if="profileSessionStore.isConfirmedLoading && !profileSessionStore.confirmedProfile"
        class="review-empty-state"
      >
        <p class="flow-message">Loading confirmed profile...</p>
      </div>

      <template v-else-if="profileSessionStore.confirmedProfile">
        <div class="confirmed-grid">
          <n-card title="Summary" size="small">
            <p class="confirmed-summary">{{ profileSessionStore.confirmedProfile.summary }}</p>
          </n-card>

          <n-card title="Target Roles" size="small">
            <ul class="review-list">
              <li v-for="role in profileSessionStore.confirmedProfile.target_roles" :key="role">
                {{ role }}
              </li>
            </ul>
          </n-card>

          <n-card title="Target Directions" size="small">
            <ul class="review-list">
              <li
                v-for="direction in profileSessionStore.confirmedProfile.target_directions"
                :key="direction"
              >
                {{ direction }}
              </li>
            </ul>
          </n-card>

          <n-card title="Core Skills" size="small">
            <ul class="review-list inline">
              <li v-for="skill in profileSessionStore.confirmedProfile.core_skills" :key="skill">
                {{ skill }}
              </li>
            </ul>
          </n-card>

          <n-card title="Supporting Skills" size="small">
            <ul class="review-list inline">
              <li
                v-for="skill in profileSessionStore.confirmedProfile.supporting_skills"
                :key="skill"
              >
                {{ skill }}
              </li>
            </ul>
          </n-card>

          <n-card title="Search Keywords" size="small">
            <ul class="review-list inline">
              <li
                v-for="keyword in profileSessionStore.confirmedProfile.search_keywords"
                :key="keyword"
              >
                {{ keyword }}
              </li>
            </ul>
          </n-card>

          <n-card title="Preferences" size="small">
            <p>
              <strong>Preferred Locations:</strong>
              {{ profileSessionStore.confirmedProfile.preferred_locations.join(", ") || "Not set" }}
            </p>
            <p>
              <strong>Work Arrangements:</strong>
              {{ profileSessionStore.confirmedProfile.work_arrangements.join(", ") || "Not set" }}
            </p>
          </n-card>

          <n-card title="Strengths" size="small">
            <ul class="review-list">
              <li v-for="strength in profileSessionStore.confirmedProfile.strengths" :key="strength">
                {{ strength }}
              </li>
            </ul>
          </n-card>

          <n-card title="Risks" size="small">
            <ul class="review-list">
              <li v-for="risk in profileSessionStore.confirmedProfile.risks" :key="risk">
                {{ risk }}
              </li>
            </ul>
          </n-card>
        </div>
      </template>
    </div>
  </section>
</template>
