<script setup lang="ts">
import { computed } from "vue";
import { NButton, NConfigProvider, NMessageProvider } from "naive-ui";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";

import { useAuthStore } from "./stores/auth";
import { useProfileSessionStore } from "./stores/profileSession";
import { useResumeProfilesStore } from "./stores/resumeProfiles";
import { useSavedJobsStore } from "./stores/savedJobs";

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const profileSessionStore = useProfileSessionStore();
const resumeProfilesStore = useResumeProfilesStore();
const savedJobsStore = useSavedJobsStore();
const showAppNav = computed(() => route.name !== "login");

async function logout() {
  await authStore.logout();
  profileSessionStore.stopPollingJobSearchRun();
  profileSessionStore.$reset();
  resumeProfilesStore.$reset();
  savedJobsStore.$reset();
  await router.push({ name: "login" });
}
</script>

<template>
  <n-config-provider>
    <n-message-provider>
      <main class="app-shell">
        <header v-if="showAppNav" class="app-nav">
          <RouterLink class="app-brand" :to="{ name: 'home' }">JobAgent</RouterLink>
          <nav class="app-nav-links" aria-label="Primary">
            <RouterLink :to="{ name: 'home' }">Resume Intake</RouterLink>
            <RouterLink :to="{ name: 'resume-profiles' }">Profile Library</RouterLink>
            <RouterLink :to="{ name: 'search-history' }">Search History</RouterLink>
            <RouterLink :to="{ name: 'saved-jobs' }">Saved Jobs</RouterLink>
          </nav>
          <div class="app-nav-user">
            <span>{{ authStore.displayName }}</span>
            <n-button size="small" tertiary :loading="authStore.isLoading" @click="logout">
              Log out
            </n-button>
          </div>
        </header>
        <RouterView />
      </main>
    </n-message-provider>
  </n-config-provider>
</template>
