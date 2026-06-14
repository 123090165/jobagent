<script setup lang="ts">
import { NButton } from "naive-ui";

import StepProgress from "../components/StepProgress.vue";
import { useProfileSessionStore } from "../stores/profileSession";

const profileSessionStore = useProfileSessionStore();

async function startProfileSession() {
  try {
    await profileSessionStore.createSession();
  } catch {
    // Error state is rendered from the store.
  }
}
</script>

<template>
  <section class="home-page">
    <div class="home-content">
      <p class="eyebrow">Search-ready profile</p>
      <h1>JobAgent</h1>
      <p class="subtitle">
        Upload or paste your resume to build a search-ready profile
      </p>

      <StepProgress />

      <div class="intake-actions" aria-label="Resume intake options">
        <div class="intake-choice">
          <strong>Upload resume</strong>
          <n-button secondary disabled>Upload</n-button>
        </div>
        <div class="intake-choice">
          <strong>Paste resume</strong>
          <n-button secondary disabled>Paste</n-button>
        </div>
      </div>

      <div class="start-row">
        <n-button
          type="primary"
          size="large"
          :loading="profileSessionStore.isCreating"
          @click="startProfileSession"
        >
          Start
        </n-button>
        <span v-if="profileSessionStore.session" class="session-note">
          Session {{ profileSessionStore.session.session_id }} started
        </span>
        <span v-if="profileSessionStore.error" class="error-note">
          {{ profileSessionStore.error }}
        </span>
      </div>
    </div>
  </section>
</template>
