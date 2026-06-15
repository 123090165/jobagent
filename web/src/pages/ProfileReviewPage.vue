<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

import StepProgress from "../components/StepProgress.vue";

const route = useRoute();
const sessionId = computed(() => String(route.params.sessionId ?? ""));
</script>

<template>
  <section class="flow-page">
    <h1>Profile Review</h1>
    <p class="flow-message">
      Resume received. Resume Review will be implemented in v4.2.
    </p>
    <p class="flow-meta">Session {{ sessionId }}</p>
    <StepProgress :active-index="0" />
  </section>
</template>
