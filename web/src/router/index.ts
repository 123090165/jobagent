import { createRouter, createWebHistory } from "vue-router";
import { useProfileSessionStore } from "../stores/profileSession";

import HomePage from "../pages/HomePage.vue";
import ProfileConfirmedPage from "../pages/ProfileConfirmedPage.vue";
import ProfileDraftPage from "../pages/ProfileDraftPage.vue";
import ProfileReviewPage from "../pages/ProfileReviewPage.vue";

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
    { path: "/", name: "home", component: HomePage },
    {
      path: "/profile/:sessionId/review",
      name: "profile-review",
      component: ProfileReviewPage,
      beforeEnter: async (to) =>
        requireSessionStep(String(to.params.sessionId), ["resume_ready", "resume_review"])
    },
    {
      path: "/profile/:sessionId/draft",
      name: "profile-draft",
      component: ProfileDraftPage,
      beforeEnter: async (to) =>
        requireSessionStep(String(to.params.sessionId), ["profile_draft"])
    },
    {
      path: "/profile/:sessionId/confirmed",
      name: "profile-confirmed",
      component: ProfileConfirmedPage,
      beforeEnter: async (to) =>
        requireSessionStep(String(to.params.sessionId), ["profile_confirmed", "job_search_ready"])
    }
  ]
});

export default router;
