import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { useProfileSessionStore } from "../stores/profileSession";

import HomePage from "../pages/HomePage.vue";
import JobSearchPage from "../pages/JobSearchPage.vue";
import JobSearchHistoryPage from "../pages/JobSearchHistoryPage.vue";
import LoginPage from "../pages/LoginPage.vue";
import ProfileConfirmedPage from "../pages/ProfileConfirmedPage.vue";
import ProfileDraftPage from "../pages/ProfileDraftPage.vue";
import ProfileReviewPage from "../pages/ProfileReviewPage.vue";
import ResumeProfilesPage from "../pages/ResumeProfilesPage.vue";
import SavedJobsPage from "../pages/SavedJobsPage.vue";
import SavedJobDetailPage from "../pages/SavedJobDetailPage.vue";
import SearchPreviewPage from "../pages/SearchPreviewPage.vue";
import SearchMissionPage from "../pages/SearchMissionPage.vue";
import ChatPage from "../pages/ChatPage.vue";
import KnowledgeStatusPage from "../pages/KnowledgeStatusPage.vue";

async function requireSessionStep(sessionId: string, allowedSteps: string[]) {
  const profileSessionStore = useProfileSessionStore();
  try {
    const session = await profileSessionStore.loadSession(sessionId);
    if (allowedSteps.includes(session.current_step)) {
      return true;
    }
    return { name: "home" };
  } catch {
    return { name: "home" };
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "login",
      component: LoginPage,
      meta: { public: true }
    },
    { path: "/", name: "home", component: HomePage },
    {
      path: "/resume-profiles",
      name: "resume-profiles",
      component: ResumeProfilesPage
    },
    {
      path: "/search-history",
      name: "search-history",
      component: JobSearchHistoryPage
    },
    {
      path: "/saved-jobs",
      name: "saved-jobs",
      component: SavedJobsPage
    },
    {
      path: "/saved-jobs/:savedJobId",
      name: "saved-job-detail",
      component: SavedJobDetailPage
    },
    {
      path: "/assistant",
      name: "assistant",
      component: ChatPage
    },
    {
      path: "/knowledge-status",
      name: "knowledge-status",
      component: KnowledgeStatusPage
    },
    {
      path: "/profile/:sessionId/review",
      name: "profile-review",
      component: ProfileReviewPage
    },
    {
      path: "/profile/:sessionId/draft",
      name: "profile-draft",
      component: ProfileDraftPage,
      beforeEnter: async (to) =>
        requireSessionStep(String(to.params.sessionId), [
          "resume_review",
          "profile_draft",
          "job_search_ready"
        ])
    },
    {
      path: "/profile/:sessionId/confirmed",
      name: "profile-confirmed",
      component: ProfileConfirmedPage,
      beforeEnter: async (to) =>
        requireSessionStep(String(to.params.sessionId), [
          "profile_draft",
          "profile_confirmed",
          "job_search_ready",
          "job_search_running",
          "job_search_completed"
        ])
    },
    {
      path: "/profile/:sessionId/search-mission",
      name: "search-mission",
      component: SearchMissionPage,
      beforeEnter: async (to) =>
        requireSessionStep(String(to.params.sessionId), [
          "profile_confirmed",
          "job_search_ready",
          "job_search_running",
          "job_search_completed"
        ])
    },
    {
      path: "/profile/:sessionId/search-preview",
      name: "search-preview",
      component: SearchPreviewPage,
      beforeEnter: async (to) =>
        requireSessionStep(String(to.params.sessionId), [
          "profile_confirmed",
          "job_search_ready",
          "job_search_running",
          "job_search_completed"
        ])
    },
    {
      path: "/jobs/:runId",
      name: "job-search",
      component: JobSearchPage
    }
  ]
});

router.beforeEach(async (to) => {
  const authStore = useAuthStore();
  await authStore.bootstrap();

  if (to.meta.public) {
    if (to.name === "login" && authStore.isAuthenticated) {
      return { name: "home" };
    }
    return true;
  }

  if (!authStore.isAuthenticated) {
    return {
      name: "login",
      query: { redirect: to.fullPath }
    };
  }

  return true;
});

export default router;
