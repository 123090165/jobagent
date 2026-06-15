import { createRouter, createWebHistory } from "vue-router";

import HomePage from "../pages/HomePage.vue";
import ProfileConfirmedPage from "../pages/ProfileConfirmedPage.vue";
import ProfileDraftPage from "../pages/ProfileDraftPage.vue";
import ProfileReviewPage from "../pages/ProfileReviewPage.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: HomePage },
    { path: "/profile-review", name: "profile-review", component: ProfileReviewPage },
    { path: "/profile-draft", name: "profile-draft", component: ProfileDraftPage },
    {
      path: "/profile-confirmed",
      name: "profile-confirmed",
      component: ProfileConfirmedPage
    }
  ]
});

export default router;
