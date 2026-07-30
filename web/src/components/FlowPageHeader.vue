<script setup lang="ts">
/**
 * 统一流程页的返回入口、步骤提示、标题和操作区，避免各阶段重复布局。
 */
import StepProgress from "./StepProgress.vue";

withDefaults(
  defineProps<{
    eyebrow?: string;
    title: string;
    description: string;
    meta?: string;
    activeStep: number;
  }>(),
  {
    eyebrow: "",
    meta: ""
  }
);
</script>

<template>
  <header class="flow-header">
    <div class="flow-header-main">
      <p v-if="eyebrow" class="flow-kicker">{{ eyebrow }}</p>
      <div class="flow-title-row">
        <h1>{{ title }}</h1>
        <span v-if="meta" class="flow-header-meta">{{ meta }}</span>
      </div>
      <p class="flow-message">{{ description }}</p>
    </div>
    <StepProgress :active-index="activeStep" />
  </header>
</template>
