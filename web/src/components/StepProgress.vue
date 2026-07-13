<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    activeIndex?: number;
  }>(),
  {
    activeIndex: 0
  }
);

const steps = [
  { label: "Profile", detail: "Resume" },
  { label: "Search Setup", detail: "Sources" },
  { label: "Results", detail: "Jobs" }
];
</script>

<template>
  <div class="step-progress" aria-label="Profile setup progress">
    <div
      v-for="(step, index) in steps"
      :key="step.label"
      class="step-item"
      :class="{
        'is-active': index === props.activeIndex,
        'is-complete': index < props.activeIndex
      }"
      :aria-current="index === props.activeIndex ? 'step' : undefined"
    >
      <span class="step-line" aria-hidden="true" />
      <span class="step-marker" aria-hidden="true">{{ index + 1 }}</span>
      <span class="step-copy">
        <span class="step-label">{{ step.label }}</span>
        <span class="step-detail">{{ step.detail }}</span>
      </span>
    </div>
  </div>
</template>
