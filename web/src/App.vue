<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { NButton, NConfigProvider, NMessageProvider } from "naive-ui";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";

import AppIcon from "./components/AppIcon.vue";
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
const mobileNavOpen = ref(false);

const navigation = [
  { name: "home", label: "Resume Intake", icon: "home" as const },
  { name: "resume-profiles", label: "Profile Library", icon: "profile" as const },
  { name: "search-history", label: "Search History", icon: "history" as const },
  { name: "saved-jobs", label: "Saved Jobs", icon: "bookmark" as const },
  { name: "assistant", label: "Assistant", icon: "chat" as const }
];

const routeLabel = computed(() => {
  if (route.name === "saved-job-detail") return "Job Workspace";
  if (route.name === "job-search") return "Search Results";
  return navigation.find((item) => item.name === route.name)?.label ?? "JobAgent";
});
const userInitial = computed(() => authStore.displayName.trim().charAt(0).toUpperCase() || "J");
const themeOverrides = {
  common: {
    primaryColor: "#145f38",
    primaryColorHover: "#1f7548",
    primaryColorPressed: "#0f4d2d",
    primaryColorSuppl: "#087266",
    borderRadius: "12px",
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
  },
  Button: { borderRadiusMedium: "12px", borderRadiusSmall: "10px", fontWeight: "700" },
  Input: { borderRadius: "12px", borderHover: "1px solid #2e8051", borderFocus: "1px solid #145f38", boxShadowFocus: "0 0 0 3px rgba(20, 95, 56, .14)" },
  Select: { peers: { InternalSelection: { borderRadius: "12px", borderFocus: "1px solid #145f38", boxShadowFocus: "0 0 0 3px rgba(20, 95, 56, .14)" } } },
  Tag: { borderRadius: "999px" }
};

watch(() => route.fullPath, () => { mobileNavOpen.value = false; });

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
  <n-config-provider :theme-overrides="themeOverrides">
    <n-message-provider>
      <div class="app-shell" :class="{ 'app-shell-auth': !showAppNav }">
        <template v-if="showAppNav">
          <button class="mobile-nav-scrim" :class="{ visible: mobileNavOpen }" aria-label="Close navigation" @click="mobileNavOpen = false" />
          <aside class="app-sidebar" :class="{ open: mobileNavOpen }">
            <div class="app-brand-row">
              <RouterLink class="app-brand" :to="{ name: 'home' }">
                <span class="app-brand-mark">JA</span>
                <span><strong>JobAgent</strong><small>AI career workspace</small></span>
              </RouterLink>
              <button class="icon-button sidebar-close" aria-label="Close navigation" @click="mobileNavOpen = false"><AppIcon name="close" /></button>
            </div>
            <p class="nav-group-label">Workspace</p>
            <nav class="app-nav-links" aria-label="Primary navigation">
              <RouterLink v-for="item in navigation" :key="item.name" :to="{ name: item.name }">
                <span class="app-nav-icon"><AppIcon :name="item.icon" /></span>
                <span>{{ item.label }}</span>
              </RouterLink>
            </nav>
            <div class="app-nav-user">
              <div class="user-avatar">{{ userInitial }}</div>
              <div class="user-copy"><strong>{{ authStore.displayName }}</strong><small>Your private workspace</small></div>
              <n-button size="tiny" quaternary :loading="authStore.isLoading" @click="logout">Log out</n-button>
            </div>
          </aside>
          <header class="app-topbar">
            <button class="icon-button mobile-menu-button" aria-label="Open navigation" :aria-expanded="mobileNavOpen" @click="mobileNavOpen = true"><AppIcon name="menu" /></button>
            <div class="app-breadcrumb"><span>Workspace</span><b>/</b><strong>{{ routeLabel }}</strong></div>
            <RouterLink class="topbar-jobs-link" :to="{ name: 'saved-jobs' }"><AppIcon name="bookmark" /> Saved Jobs</RouterLink>
          </header>
        </template>
        <main class="app-content"><RouterView /></main>
      </div>
    </n-message-provider>
  </n-config-provider>
</template>
