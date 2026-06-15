<script setup lang="ts">
import { NConfigProvider, NMessageProvider } from "naive-ui";
import { RouterView } from "vue-router";
</script>

<template>
  <n-config-provider>
    <n-message-provider>
      <main class="app-shell">
        <RouterView />
      </main>
    </n-message-provider>
  </n-config-provider>
</template>
