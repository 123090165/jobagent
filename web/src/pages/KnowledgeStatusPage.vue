<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { NButton, NTag } from "naive-ui";

import { getRagStatus, type RagStatus } from "../api/rag";
import FlowPageHeader from "../components/FlowPageHeader.vue";

const status = ref<RagStatus | null>(null);
const error = ref<string | null>(null);
const isLoading = ref(false);

const serviceLabel = computed(() => {
  if (!status.value?.mcp_configured) return "Not configured";
  return status.value.reachable ? "Available" : "Unavailable";
});

function serviceTagType(): "success" | "warning" | "error" {
  if (!status.value?.mcp_configured) return "warning";
  return status.value.reachable ? "success" : "error";
}

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "Not available";
}

async function refresh() {
  isLoading.value = true;
  error.value = null;
  try {
    status.value = await getRagStatus();
  } catch {
    error.value = "Knowledge status could not be loaded.";
  } finally {
    isLoading.value = false;
  }
}

onMounted(() => void refresh());
</script>

<template>
  <section class="flow-page flow-page-wide">
    <FlowPageHeader
      eyebrow="Personal knowledge"
      title="Knowledge Status"
      description="See whether your confirmed profile and saved jobs are available to semantic retrieval."
      meta="Current user only"
      :active-step="2"
    />

    <div v-if="error" class="error-banner">{{ error }}</div>

    <div class="workspace-panel knowledge-service-panel">
      <div>
        <span class="knowledge-label">Modular RAG MCP</span>
        <h2>{{ status?.server_name || "Knowledge service" }}</h2>
        <p>
          {{ status?.server_version ? `Version ${status.server_version}` : "No service version reported" }}
        </p>
      </div>
      <div class="knowledge-service-actions">
        <n-tag :type="serviceTagType()" round>{{ serviceLabel }}</n-tag>
        <n-tag :type="status?.sync_enabled ? 'success' : 'warning'" round>
          Sync {{ status?.sync_enabled ? "enabled" : "disabled" }}
        </n-tag>
        <n-button secondary :loading="isLoading" @click="refresh">Refresh</n-button>
      </div>
    </div>

    <div v-if="status" class="metric-grid">
      <article class="metric-card">
        <span>Indexed resources</span>
        <strong>{{ status.overview.ready_count }}</strong>
      </article>
      <article class="metric-card">
        <span>Waiting</span>
        <strong>{{ status.overview.pending_resource_count }}</strong>
      </article>
      <article class="metric-card">
        <span>Failed</span>
        <strong>{{ status.overview.failed_resource_count }}</strong>
      </article>
      <article class="metric-card">
        <span>Total tracked</span>
        <strong>{{ status.overview.resource_count }}</strong>
      </article>
    </div>

    <div v-if="status" class="workspace-panel knowledge-detail-grid">
      <div>
        <span class="knowledge-label">Last successful sync</span>
        <strong>{{ formatDate(status.overview.last_synced_at) }}</strong>
      </div>
      <div>
        <span class="knowledge-label">Oldest queued event</span>
        <strong>{{ formatDate(status.overview.oldest_pending_at) }}</strong>
      </div>
      <div>
        <span class="knowledge-label">Outbox</span>
        <strong>
          {{ status.overview.pending_event_count }} pending ·
          {{ status.overview.processing_event_count }} processing
        </strong>
      </div>
    </div>

    <div v-if="status?.overview.recent_failures.length" class="workspace-panel">
      <div>
        <span class="knowledge-label">Recent failures</span>
        <h2>Resources needing attention</h2>
      </div>
      <ul class="knowledge-failure-list">
        <li v-for="failure in status.overview.recent_failures" :key="failure.event_id">
          <strong>{{ failure.resource_type }} · {{ failure.resource_id }}</strong>
          <span>{{ failure.last_error_code || "SYNC_FAILED" }} · attempt {{ failure.attempt_count }}</span>
        </li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.knowledge-service-panel,
.knowledge-service-actions,
.knowledge-detail-grid {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.knowledge-service-actions {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.knowledge-service-panel p {
  margin: 4px 0 0;
  color: var(--muted);
}

.knowledge-label {
  display: block;
  margin-bottom: 6px;
  color: var(--muted);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.knowledge-detail-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.knowledge-detail-grid strong {
  overflow-wrap: anywhere;
}

.knowledge-failure-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.knowledge-failure-list li {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  border-top: 1px solid var(--border);
  padding-top: 10px;
}

.knowledge-failure-list span {
  color: var(--muted);
}

@media (max-width: 760px) {
  .knowledge-service-panel,
  .knowledge-failure-list li {
    align-items: flex-start;
    flex-direction: column;
  }

  .knowledge-service-actions {
    justify-content: flex-start;
  }

  .knowledge-detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
