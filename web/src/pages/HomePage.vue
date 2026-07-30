<script setup lang="ts">
/**
 * 简历录入页面：创建 ProfileSession，提交文本或文件，并进入解析审阅。
 */
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import { NButton, NInput, NRadioButton, NRadioGroup } from "naive-ui";

import FlowPageHeader from "../components/FlowPageHeader.vue";
import { useProfileSessionStore } from "../stores/profileSession";

const profileSessionStore = useProfileSessionStore();
const router = useRouter();
const intakeMode = ref<"file" | "text">("file");
const resumeText = ref("");
const selectedFile = ref<File | null>(null);
const isSubmitting = computed(
  () => profileSessionStore.isCreating || profileSessionStore.isSubmitting
);
const selectedFileName = computed(() => selectedFile.value?.name ?? "No file selected");
const canSubmit = computed(() => {
  if (intakeMode.value === "file") {
    return Boolean(selectedFile.value);
  }
  return Boolean(resumeText.value.trim());
});
const resumePreview = computed(() => {
  if (intakeMode.value === "file" && selectedFile.value) {
    return `Selected file: ${selectedFile.value.name}`;
  }
  if (intakeMode.value === "text" && resumeText.value.trim()) {
    return `${resumeText.value.trim().length} characters ready to submit`;
  }
  return intakeMode.value === "file"
    ? "Choose a PDF, DOCX, TXT, or Markdown resume file."
    : "Paste plain resume text.";
});

function onFileSelected(event: Event) {
  const target = event.target as HTMLInputElement;
  selectedFile.value = target.files?.[0] ?? null;
}

async function submitResume() {
  try {
    const session = intakeMode.value === "file" && selectedFile.value
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
  <section class="flow-page flow-page-wide home-page">
    <FlowPageHeader
      eyebrow="Profile workflow"
      title="JobAgent"
      description="Build a confirmed profile from a resume, preview the retrieval plan, then run provider-backed job search."
      meta="Resume intake"
      :active-step="0"
    />

    <div class="workspace-panel intake-panel">
      <div class="panel-heading">
        <div>
          <h2>Resume input</h2>
          <p>Choose one source for this session.</p>
        </div>
        <n-radio-group v-model:value="intakeMode" size="small">
          <n-radio-button value="file">Upload</n-radio-button>
          <n-radio-button value="text">Paste</n-radio-button>
        </n-radio-group>
      </div>

      <div v-if="intakeMode === 'file'" class="intake-choice">
        <div>
          <strong>Resume file</strong>
          <p class="intake-helper">Supported formats: .pdf, .docx, .txt, .md.</p>
        </div>
        <label class="file-picker">
          <input
            accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
            type="file"
            @change="onFileSelected"
          />
          <span>{{ selectedFile ? "Replace file" : "Choose file" }}</span>
        </label>
      </div>

      <div v-else class="intake-choice">
        <div>
          <strong>Resume text</strong>
          <p class="intake-helper">Plain text is sent through the same intake API.</p>
        </div>
        <n-input
          v-model:value="resumeText"
          type="textarea"
          :autosize="{ minRows: 8, maxRows: 14 }"
          placeholder="Paste resume text"
        />
      </div>

      <div class="intake-summary">
        <div>
          <span class="preview-label">Current input</span>
          <strong>{{ intakeMode === "file" ? selectedFileName : "Pasted resume text" }}</strong>
          <p>{{ resumePreview }}</p>
        </div>
        <n-button
          type="primary"
          size="large"
          :loading="isSubmitting"
          :disabled="!canSubmit"
          @click="submitResume"
        >
          Start Profile Setup
        </n-button>
      </div>

      <div class="status-row">
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
