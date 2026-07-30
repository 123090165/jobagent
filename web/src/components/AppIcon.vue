<script setup lang="ts">
/**
 * 把项目内使用的图标名称映射到统一 SVG，页面只传语义名称和尺寸。
 */
defineProps<{
  name: "home" | "profile" | "history" | "bookmark" | "chat" | "menu" | "close" | "search" | "external" | "arrow-left" | "sparkles" | "check" | "alert" | "target" | "note";
}>();
</script>

<template>
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <template v-if="name === 'home'"><path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10M9 20v-6h6v6"/></template>
    <template v-else-if="name === 'profile'"><circle cx="12" cy="8" r="4"/><path d="M4.5 21a7.5 7.5 0 0 1 15 0"/></template>
    <template v-else-if="name === 'history'"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></template>
    <template v-else-if="name === 'bookmark'"><path d="M6 3h12v18l-6-4-6 4z"/></template>
    <template v-else-if="name === 'chat'"><path d="M4 5h16v11H8l-4 4z"/><path d="M8 9h8M8 12h5"/></template>
    <template v-else-if="name === 'menu'"><path d="M4 7h16M4 12h16M4 17h16"/></template>
    <template v-else-if="name === 'close'"><path d="m6 6 12 12M18 6 6 18"/></template>
    <template v-else-if="name === 'search'"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></template>
    <template v-else-if="name === 'external'"><path d="M14 4h6v6M20 4l-9 9"/><path d="M18 13v6H5V6h6"/></template>
    <template v-else-if="name === 'arrow-left'"><path d="m15 18-6-6 6-6"/></template>
    <template v-else-if="name === 'sparkles'"><path d="m12 3 1.2 3.8L17 8l-3.8 1.2L12 13l-1.2-3.8L7 8l3.8-1.2zM18 14l.7 2.3L21 17l-2.3.7L18 20l-.7-2.3L15 17l2.3-.7zM5 13l.6 1.8 1.9.7-1.9.6L5 18l-.6-1.9-1.9-.6 1.9-.7z"/></template>
    <template v-else-if="name === 'check'"><path d="m5 12 4 4L19 6"/></template>
    <template v-else-if="name === 'alert'"><path d="M12 3 2.5 20h19zM12 9v4M12 17h.01"/></template>
    <template v-else-if="name === 'target'"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="m14 10 6-6"/></template>
    <template v-else-if="name === 'note'"><path d="M5 3h14v18H5zM8 8h8M8 12h8M8 16h5"/></template>
  </svg>
</template>
