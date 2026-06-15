<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import { NButton, NInput } from "naive-ui";

import StepProgress from "../components/StepProgress.vue";
import { useProfileSessionStore } from "../stores/profileSession";

const profileSessionStore = useProfileSessionStore();
const router = useRouter();
const resumeText = ref("");
const selectedFile = ref<File | null>(null);
const selectedFileName = computed(() => selectedFile.value?.name ?? "No file selected");
const resumePreview = computed(() => {
  if (selectedFile.value) {
    return `Selected file: ${selectedFile.value.name}`;
  }
  if (resumeText.value.trim()) {
    return `${resumeText.value.trim().length} characters ready to submit`;
  }
  return "Choose a txt/md file or paste your resume text.";
});

function onFileSelected(event: Event) {
  const target = event.target as HTMLInputElement;
  selectedFile.value = target.files?.[0] ?? null;
}

async function submitResume() {
  try {
    const session = selectedFile.value
      ? await profileSessionStore.submitFileResume(selectedFile.value)
      : await profileSessionStore.submitTextResume(resumeText.value);
    await router.push({
      name: "profile-review",
      params: { sessionId: session.session_id }
    });
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

      <StepProgress :active-index="0" />

      <div class="intake-actions" aria-label="Resume intake options">
        <div class="intake-choice">
          <div>
            <strong>Upload resume</strong>
            <p class="intake-helper">Supports .txt and .md files in v4.1.</p>
          </div>
          <label class="file-picker">
            <input
              accept=".txt,.md,text/plain,text/markdown"
              type="file"
              @change="onFileSelected"
            />
            <span>{{ selectedFile ? "Replace file" : "Choose file" }}</span>
          </label>
        </div>
        <div class="intake-choice">
          <div>
            <strong>Paste resume</strong>
            <p class="intake-helper">Paste plain text if you do not want to upload a file.</p>
          </div>
          <n-input
            v-model:value="resumeText"
            type="textarea"
            :autosize="{ minRows: 6, maxRows: 10 }"
            placeholder="Paste your resume text here"
          />
        </div>
      </div>

      <div class="resume-preview">
        <span class="preview-label">Current input</span>
        <strong>{{ selectedFileName }}</strong>
        <p>{{ resumePreview }}</p>
      </div>

      <div class="start-row">
        <n-button
          type="primary"
          size="large"
          :loading="profileSessionStore.isCreating || profileSessionStore.isSubmitting"
          :disabled="!selectedFile && !resumeText.trim()"
          @click="submitResume"
        >
          Start Profile Setup
        </n-button>
        <span v-if="profileSessionStore.session" class="session-note">
          Session {{ profileSessionStore.session.session_id }}
        </span>
        <span v-if="profileSessionStore.error" class="error-note">
          {{ profileSessionStore.error }}
        </span>
      </div>
    </div>
  </section>
</template>
