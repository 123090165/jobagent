<script setup lang="ts">
const steps = ["Resume", "Profile", "Search", "Brief"];
const activeIndex = 0;
</script>

<template>
  <div class="step-progress" aria-label="Profile setup progress">
    <div
      v-for="(step, index) in steps"
      :key="step"
      class="step-item"
      :class="{ 'is-active': index === activeIndex, 'is-complete': index < activeIndex }"
    >
      <span class="step-line" aria-hidden="true" />
      <span class="step-label">{{ step }}</span>
    </div>
  </div>
</template>
