<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    activeIndex?: number;
  }>(),
  {
    activeIndex: 0
  }
);

const steps = ["Resume", "Profile", "Search", "Brief"];
</script>

<template>
  <div class="step-progress" aria-label="Profile setup progress">
    <div
      v-for="(step, index) in steps"
      :key="step"
      class="step-item"
      :class="{
        'is-active': index === props.activeIndex,
        'is-complete': index < props.activeIndex
      }"
    >
      <span class="step-line" aria-hidden="true" />
      <span class="step-label">{{ step }}</span>
    </div>
  </div>
</template>
