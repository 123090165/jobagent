<script setup lang="ts">
/**
 * 处理登录和注册，并在成功后返回原目标页面。
 */
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NInput, NRadioButton, NRadioGroup } from "naive-ui";

import { useAuthStore } from "../stores/auth";

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const mode = ref<"login" | "register">("login");
const username = ref("");
const password = ref("");
const displayName = ref("");
const localError = ref<string | null>(null);

const title = computed(() => (mode.value === "login" ? "Sign in to JobAgent" : "Create JobAgent Account"));
const submitLabel = computed(() => (mode.value === "login" ? "Sign in" : "Create account"));
const passwordHint = computed(() =>
  mode.value === "register" ? "Use at least 8 characters." : "Enter your account password."
);
const canSubmit = computed(() => {
  const hasUsername = username.value.trim().length >= 3;
  const hasPassword = mode.value === "register"
    ? password.value.length >= 8
    : password.value.length > 0;
  return hasUsername && hasPassword && !authStore.isLoading;
});

async function submit() {
  localError.value = null;
  try {
    if (mode.value === "register") {
      await authStore.register({
        username: username.value.trim(),
        password: password.value,
        display_name: displayName.value.trim() || null
      });
    } else {
      await authStore.login({
        username: username.value.trim(),
        password: password.value
      });
    }
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/";
    await router.push(redirect);
  } catch {
    localError.value = authStore.error;
  }
}
</script>

<template>
  <section class="auth-page">
    <div class="auth-panel">
      <div class="auth-heading">
        <p class="flow-kicker">JobAgent</p>
        <h1>{{ title }}</h1>
        <p class="flow-message">
          Use one account to keep resume profiles, saved jobs, and search analysis together.
        </p>
      </div>

      <n-radio-group v-model:value="mode" size="small">
        <n-radio-button value="login">Sign in</n-radio-button>
        <n-radio-button value="register">Register</n-radio-button>
      </n-radio-group>

      <div class="auth-form">
        <label class="draft-field">
          <span>Username</span>
          <n-input
            v-model:value="username"
            autocomplete="username"
            placeholder="username"
            @keyup.enter="submit"
          />
        </label>

        <label v-if="mode === 'register'" class="draft-field">
          <span>Display name</span>
          <n-input
            v-model:value="displayName"
            autocomplete="name"
            placeholder="Optional"
            @keyup.enter="submit"
          />
        </label>

        <label class="draft-field">
          <span>Password</span>
          <n-input
            v-model:value="password"
            type="password"
            show-password-on="click"
            autocomplete="current-password"
            placeholder="password"
            @keyup.enter="submit"
          />
          <small class="flow-meta">{{ passwordHint }}</small>
        </label>
      </div>

      <div v-if="localError || authStore.error" class="error-banner compact">
        {{ localError || authStore.error }}
      </div>

      <n-button
        type="primary"
        size="large"
        block
        :loading="authStore.isLoading"
        :disabled="!canSubmit"
        @click="submit"
      >
        {{ submitLabel }}
      </n-button>
    </div>
  </section>
</template>
