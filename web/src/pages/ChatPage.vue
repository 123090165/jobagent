<script setup lang="ts">
/**
 * 职业助手工作区：管理会话、上下文附件、引用、记忆状态和消息重试。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import {
  NButton,
  NEmpty,
  NInput,
  NPopconfirm,
  NSelect,
  NSpin,
  NTag,
  useMessage
} from "naive-ui";
import { RouterLink } from "vue-router";
import { useRoute, useRouter } from "vue-router";

import {
  clearChatMemory,
  createChatConversation,
  createChatTurn,
  deleteChatConversation,
  deleteChatTurn,
  getChatContextCatalog,
  getChatMemoryStatus,
  listChatConversations,
  listChatTurns,
  updateChatConversation
} from "../api/chat";
import { createBrowserHelperSession } from "../api/browserHelper";
import AppIcon from "../components/AppIcon.vue";
import {
  bindBrowserHelperSession,
  getBrowserHelperConnectionStatus,
  pingBrowserHelper
} from "../services/browserHelper";
import type {
  ChatContextCatalog,
  ChatConversation,
  ChatDataAccessMode,
  ChatMemoryStatus,
  ChatSource,
  ChatTurn
} from "../types/chat";

type ContextItem = {
  key: string;
  kind: "profile" | "search_run" | "search_result" | "saved_job" | "browser_capture";
  resourceId: string;
  runId?: string;
  label: string;
};

const message = useMessage();
const route = useRoute();
const router = useRouter();
const conversations = ref<ChatConversation[]>([]);
const activeConversationId = ref<string | null>(null);
const turns = ref<ChatTurn[]>([]);
const draft = ref("");
const loading = ref(true);
const sending = ref(false);
const pairingBrowserHelper = ref(false);
const browserHelperStatus = ref<"checking" | "available" | "connected" | "unavailable">("checking");
const messageList = ref<HTMLElement | null>(null);
const contextCatalog = ref<ChatContextCatalog>({ profiles: [], search_runs: [], saved_jobs: [] });
const contextPanelOpen = ref(false);
const memoryPanelOpen = ref(false);
const memoryStatus = ref<ChatMemoryStatus | null>(null);
const selectedProfileId = ref<string | null>(null);
const selectedRunIds = ref<string[]>([]);
const selectedSavedJobIds = ref<string[]>([]);

const activeConversation = computed(() =>
  conversations.value.find((item) => item.conversation_id === activeConversationId.value) ?? null
);
const browserHelperButtonLabel = computed(() => {
  if (browserHelperStatus.value === "connected") return "Browser Helper connected";
  if (browserHelperStatus.value === "unavailable") return "Connect Browser Helper";
  return "Pair Browser Helper";
});
const accessOptions = [
  { label: "Auto — ask only when needed", value: "auto" },
  { label: "Always use my data", value: "always" },
  { label: "Do not use my data", value: "off" }
];
const profileOptions = computed(() => contextCatalog.value.profiles.map((item) => ({
  label: `${item.label}${item.is_default ? " · default" : ""}`,
  value: item.resume_profile_id
})));
const searchRunOptions = computed(() => contextCatalog.value.search_runs.map((item) => ({
  label: item.label,
  value: item.job_search_run_id
})));
const savedJobOptions = computed(() => contextCatalog.value.saved_jobs.map((item) => ({
  label: `${item.label} · ${item.status}`,
  value: item.saved_job_id
})));
const contextItems = computed<ContextItem[]>(() => {
  const conversation = activeConversation.value;
  if (!conversation) return [];
  const items: ContextItem[] = [];
  const profile = contextCatalog.value.profiles.find(
    (item) => item.resume_profile_id === conversation.data_scope.resume_profile_id
  );
  if (conversation.data_scope.resume_profile_id) {
    items.push({
      key: `profile:${conversation.data_scope.resume_profile_id}`,
      kind: "profile",
      resourceId: conversation.data_scope.resume_profile_id,
      label: profile?.label ?? "Unavailable profile"
    });
  }
  for (const runId of conversation.data_scope.job_search_run_ids) {
    const run = contextCatalog.value.search_runs.find((item) => item.job_search_run_id === runId);
    items.push({ key: `run:${runId}`, kind: "search_run", resourceId: runId, label: run?.label ?? "Unavailable search run" });
  }
  for (const savedJobId of conversation.data_scope.saved_job_ids) {
    const job = contextCatalog.value.saved_jobs.find((item) => item.saved_job_id === savedJobId);
    items.push({ key: `saved:${savedJobId}`, kind: "saved_job", resourceId: savedJobId, label: job?.label ?? "Unavailable saved job" });
  }
  for (const ref of conversation.data_scope.job_search_result_refs) {
    const memoryItem = memoryStatus.value?.pinned_context.find(
      (item) => item.source_type === "search_results" && item.resource_id === ref.job_result_id
    );
    items.push({
      key: `result:${ref.job_search_run_id}:${ref.job_result_id}`,
      kind: "search_result",
      resourceId: ref.job_result_id,
      runId: ref.job_search_run_id,
      label: memoryItem?.label ?? "Pinned search result"
    });
  }
  for (const captureId of conversation.data_scope.browser_capture_ids) {
    const memoryItem = memoryStatus.value?.pinned_context.find(
      (item) => item.source_type === "search_results" && item.resource_id === captureId
    );
    items.push({
      key: `capture:${captureId}`,
      kind: "browser_capture",
      resourceId: captureId,
      label: memoryItem?.label ?? "Captured browser JD"
    });
  }
  return items;
});
const summaryFactCount = computed(() => {
  if (!memoryStatus.value) return 0;
  return Object.values(memoryStatus.value.summary).reduce<number>(
    (count, value) => count + (Array.isArray(value) ? value.length : 0),
    0
  );
});
const suggestions = [
  "比较我收藏的岗位，告诉我应该优先申请哪一个。",
  "根据我的 Profile，总结最适合我的岗位方向。",
  "最近搜索结果里有哪些值得关注的风险？"
];

onMounted(async () => {
  window.addEventListener("message", handleBrowserHelperContextUpdate);
  const shouldPairBrowserHelper = route.query.pair_browser_helper === "1";
  try {
    const [response, catalog] = await Promise.all([
      listChatConversations(),
      getChatContextCatalog()
    ]);
    conversations.value = response.items;
    contextCatalog.value = catalog;
    if (response.items.length) {
      const requestedId = String(route.query.conversation ?? "");
      const initial = response.items.find((item) => item.conversation_id === requestedId)
        ?? response.items[0];
      await selectConversation(initial.conversation_id);
    } else {
      await startConversation();
    }
    if (shouldPairBrowserHelper) {
      await pairBrowserHelper();
    } else {
      await refreshBrowserHelperStatus();
    }
  } catch {
    message.error("Could not load chat conversations.");
  } finally {
    loading.value = false;
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("message", handleBrowserHelperContextUpdate);
});

async function handleBrowserHelperContextUpdate(event: MessageEvent) {
  if (event.source !== window || event.data?.__jobagentHelper !== true) return;
  if (event.data?.type !== "JOBAGENT_HELPER_CONTEXT_UPDATED") return;
  const conversationId = String(event.data.conversationId || "");
  if (!conversationId) return;
  try {
    await refreshConversations();
    if (activeConversationId.value === conversationId) await refreshMemoryStatus();
  } catch {
    // The next normal conversation refresh will reconcile transient failures.
  }
}

async function refreshBrowserHelperStatus() {
  try {
    const helper = await pingBrowserHelper();
    if (!helper.installed) {
      browserHelperStatus.value = "unavailable";
      return;
    }
    const connection = await getBrowserHelperConnectionStatus();
    browserHelperStatus.value = connection.paired ? "connected" : "available";
  } catch {
    browserHelperStatus.value = "unavailable";
  }
}

async function startConversation() {
  const conversation = await createChatConversation();
  conversations.value.unshift(conversation);
  activeConversationId.value = conversation.conversation_id;
  turns.value = [];
  syncContextDraft(conversation);
  await refreshMemoryStatus();
  await router.replace({ name: "assistant", query: { conversation: conversation.conversation_id } });
}

async function pairBrowserHelper() {
  pairingBrowserHelper.value = true;
  try {
    const helper = await pingBrowserHelper();
    if (!helper.installed || !helper.capabilities.includes("bindJobAgentSession")) {
      browserHelperStatus.value = "unavailable";
      throw new Error("Browser Helper is not available on this page. Reload Assistant after enabling the extension.");
    }
    browserHelperStatus.value = "available";
    const session = await createBrowserHelperSession();
    const configuredBaseUrl = String(import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
    const backendUrl = configuredBaseUrl || "http://127.0.0.1:8000";
    await bindBrowserHelperSession({
      backendUrl,
      appUrl: window.location.origin,
      accessToken: session.access_token,
      expiresAt: session.expires_at,
      profileSessions: session.profile_sessions
    });
    browserHelperStatus.value = "connected";
    message.success("Browser Helper connected. An open side panel will refresh automatically.");
    await router.replace({
      name: "assistant",
      query: activeConversationId.value
        ? { conversation: activeConversationId.value }
        : undefined
    });
  } catch (error) {
    message.error(error instanceof Error ? error.message : "Could not pair Browser Helper.");
  } finally {
    pairingBrowserHelper.value = false;
  }
}

async function selectConversation(conversationId: string) {
  activeConversationId.value = conversationId;
  memoryStatus.value = null;
  turns.value = (await listChatTurns(conversationId)).items;
  await refreshMemoryStatus();
  const conversation = conversations.value.find((item) => item.conversation_id === conversationId);
  if (conversation) syncContextDraft(conversation);
  if (String(route.query.conversation ?? "") !== conversationId) {
    await router.replace({ name: "assistant", query: { conversation: conversationId } });
  }
  await scrollToBottom();
}

async function sendQuestion(question = draft.value, clearComposer = true, retryOfTurnId?: string) {
  const text = question.trim();
  if (!text || !activeConversationId.value || sending.value) return;
  if (clearComposer) draft.value = "";
  sending.value = true;
  try {
    const turn = await createChatTurn(activeConversationId.value, text, retryOfTurnId);
    const index = turns.value.findIndex((item) => item.turn_id === turn.turn_id);
    if (index >= 0) turns.value[index] = turn;
    else turns.value.push(turn);
    await refreshConversations();
    await refreshMemoryStatus();
    await scrollToBottom();
  } catch {
    if (clearComposer) draft.value = text;
    message.error("The assistant could not complete this turn.");
  } finally {
    sending.value = false;
  }
}

async function retryTurn(turn: ChatTurn) {
  await sendQuestion(turn.question, false, turn.turn_id);
}

async function changeAccessMode(value: ChatDataAccessMode) {
  if (!activeConversationId.value) return;
  try {
    const updated = await updateChatConversation(activeConversationId.value, {
      data_access_mode: value
    });
    const index = conversations.value.findIndex((item) => item.conversation_id === updated.conversation_id);
    if (index >= 0) conversations.value[index] = updated;
  } catch {
    message.error("Could not update data access settings.");
  }
}

async function saveContextSelection() {
  const conversation = activeConversation.value;
  if (!conversation) return;
  try {
    const selectedRuns = new Set(selectedRunIds.value.slice(0, 3));
    const retainedResultRefs = conversation.data_scope.job_search_result_refs.filter(
      (item) => selectedRuns.has(item.job_search_run_id)
    );
    const resultRunIds = new Set(retainedResultRefs.map((item) => item.job_search_run_id));
    const updated = await updateChatConversation(conversation.conversation_id, {
      data_scope: {
        ...conversation.data_scope,
        resume_profile_id: selectedProfileId.value,
        job_search_run_ids: [...selectedRuns].filter((runId) => !resultRunIds.has(runId)),
        job_search_result_refs: retainedResultRefs,
        saved_job_ids: selectedSavedJobIds.value.slice(0, 20)
      }
    });
    replaceConversation(updated);
    await refreshMemoryStatus();
    contextPanelOpen.value = false;
    message.success("Conversation context updated.");
  } catch {
    message.error("Could not update conversation context.");
  }
}

async function useAutomaticContext() {
  const conversation = activeConversation.value;
  if (!conversation) return;
  try {
    const updated = await updateChatConversation(conversation.conversation_id, {
      data_scope: {
        ...conversation.data_scope,
        resume_profile_id: null,
        job_search_run_ids: [],
        job_search_result_refs: [],
        saved_job_ids: [],
        browser_capture_ids: []
      }
    });
    replaceConversation(updated);
    syncContextDraft(updated);
    await refreshMemoryStatus();
    contextPanelOpen.value = false;
    message.success("This conversation now uses automatic context selection.");
  } catch {
    message.error("Could not reset conversation context.");
  }
}

async function removeTurn(turnId: string) {
  if (!activeConversationId.value) return;
  await deleteChatTurn(activeConversationId.value, turnId);
  turns.value = turns.value.filter((item) => item.turn_id !== turnId);
  await refreshConversations();
  await refreshMemoryStatus();
  message.success("This turn and its derived memory were deleted.");
}

async function clearMemory() {
  if (!activeConversationId.value) return;
  await clearChatMemory(activeConversationId.value);
  turns.value = [];
  await refreshConversations();
  await refreshMemoryStatus();
  message.success("Conversation memory was cleared.");
}

async function removeConversation() {
  if (!activeConversationId.value) return;
  const removedId = activeConversationId.value;
  await deleteChatConversation(removedId);
  conversations.value = conversations.value.filter((item) => item.conversation_id !== removedId);
  if (conversations.value.length) await selectConversation(conversations.value[0].conversation_id);
  else await startConversation();
}

async function refreshConversations() {
  conversations.value = (await listChatConversations()).items;
}

function replaceConversation(updated: ChatConversation) {
  const index = conversations.value.findIndex((item) => item.conversation_id === updated.conversation_id);
  if (index >= 0) conversations.value[index] = updated;
}

function syncContextDraft(conversation: ChatConversation) {
  selectedProfileId.value = conversation.data_scope.resume_profile_id ?? null;
  selectedRunIds.value = [...new Set([
    ...conversation.data_scope.job_search_run_ids,
    ...conversation.data_scope.job_search_result_refs.map((item) => item.job_search_run_id)
  ])];
  selectedSavedJobIds.value = [...conversation.data_scope.saved_job_ids];
}

async function removePinnedContext(item: ContextItem) {
  const conversation = activeConversation.value;
  if (!conversation) return;
  const scope = {
    ...conversation.data_scope,
    job_search_run_ids: [...conversation.data_scope.job_search_run_ids],
    job_search_result_refs: [...conversation.data_scope.job_search_result_refs],
    saved_job_ids: [...conversation.data_scope.saved_job_ids],
    browser_capture_ids: [...conversation.data_scope.browser_capture_ids]
  };
  if (item.kind === "profile") scope.resume_profile_id = null;
  if (item.kind === "search_run") {
    scope.job_search_run_ids = scope.job_search_run_ids.filter((runId) => runId !== item.resourceId);
  }
  if (item.kind === "search_result") {
    scope.job_search_result_refs = scope.job_search_result_refs.filter(
      (ref) => ref.job_search_run_id !== item.runId || ref.job_result_id !== item.resourceId
    );
  }
  if (item.kind === "saved_job") {
    scope.saved_job_ids = scope.saved_job_ids.filter((savedJobId) => savedJobId !== item.resourceId);
  }
  if (item.kind === "browser_capture") {
    scope.browser_capture_ids = scope.browser_capture_ids.filter((captureId) => captureId !== item.resourceId);
  }
  try {
    const updated = await updateChatConversation(conversation.conversation_id, { data_scope: scope });
    replaceConversation(updated);
    syncContextDraft(updated);
    await refreshMemoryStatus();
  } catch {
    message.error("Could not remove this context item.");
  }
}

async function refreshMemoryStatus() {
  if (!activeConversationId.value) {
    memoryStatus.value = null;
    return;
  }
  try {
    memoryStatus.value = await getChatMemoryStatus(activeConversationId.value);
  } catch {
    memoryStatus.value = null;
  }
}

function sourceLabel(source: ChatSource): string {
  return {
    profile: "profile",
    search_results: "search results",
    saved_jobs: "saved jobs",
    chat_history: "chat history"
  }[source];
}

function usageText(turn: ChatTurn): string {
  if (!turn.retrieval_used || !turn.citations.length) return "No personal context used";
  const sources = [...new Set(turn.citations.map((citation) => sourceLabel(citation.source_type)))];
  return `Used ${turn.citations.length} reference${turn.citations.length === 1 ? "" : "s"} · ${sources.join(", ")}`;
}

function fallbackReasonText(turn: ChatTurn): string | null {
  if (turn.analysis_mode !== "fallback" || !turn.fallback_reason) return null;
  const reasonParts = turn.fallback_reason.split(":");
  const category = reasonParts[reasonParts.length - 1] ?? "";
  const labels: Record<string, string> = {
    network_error: "Model network error",
    timeout: "Model request timed out",
    authentication_failed: "Model authentication failed",
    rate_limited: "Model rate limit reached",
    model_unavailable: "Configured model unavailable",
    provider_unavailable: "Model provider unavailable",
    invalid_response: "Model returned an invalid response",
    provider_error: "Model provider error",
    agent_answer_missing_citations: "Model answer could not be grounded"
  };
  return labels[category] ?? "Model temporarily unavailable";
}

async function scrollToBottom() {
  await nextTick();
  messageList.value?.scrollTo({ top: messageList.value.scrollHeight, behavior: "smooth" });
}
</script>

<template>
  <section class="chat-page">
    <aside class="chat-history-panel">
      <div class="panel-heading">
        <div><span class="eyebrow">Assistant</span><h1>Conversations</h1></div>
        <n-button circle secondary type="primary" aria-label="New conversation" @click="startConversation">+</n-button>
      </div>
      <n-spin :show="loading">
        <div class="conversation-list">
          <button
            v-for="conversation in conversations"
            :key="conversation.conversation_id"
            class="conversation-item"
            :class="{ active: conversation.conversation_id === activeConversationId }"
            @click="selectConversation(conversation.conversation_id)"
          >
            <AppIcon name="chat" />
            <span><strong>{{ conversation.title }}</strong><small>{{ conversation.last_completed_sequence }} turns</small></span>
          </button>
        </div>
      </n-spin>
    </aside>

    <div class="chat-workspace">
      <div class="chat-context-header">
        <header class="chat-toolbar">
          <div>
            <span class="eyebrow">Career Q&amp;A</span>
            <h2>{{ activeConversation?.title ?? "New conversation" }}</h2>
            <div class="active-context-row">
              <n-tag v-if="!contextItems.length" size="small" round>Automatic context</n-tag>
              <n-tag
                v-for="item in contextItems"
                :key="item.key"
                size="small"
                round
                closable
                @close="removePinnedContext(item)"
              >
                {{ item.label }}
              </n-tag>
            </div>
          </div>
          <div class="toolbar-actions" v-if="activeConversation">
            <n-button size="small" secondary :loading="pairingBrowserHelper" @click="pairBrowserHelper">
              {{ browserHelperButtonLabel }}
            </n-button>
            <n-button size="small" secondary @click="contextPanelOpen = !contextPanelOpen">
              Context
            </n-button>
            <n-button size="small" secondary @click="memoryPanelOpen = !memoryPanelOpen">
              Memory
            </n-button>
            <n-select
              class="access-select"
              size="small"
              :value="activeConversation.data_access_mode"
              :options="accessOptions"
              @update:value="changeAccessMode"
            />
            <n-popconfirm @positive-click="clearMemory">
              <template #trigger><n-button size="small" secondary>Clear memory</n-button></template>
              Delete every turn, summary and retrieval state in this conversation?
            </n-popconfirm>
            <n-popconfirm @positive-click="removeConversation">
              <template #trigger><n-button size="small" tertiary type="error">Delete</n-button></template>
              Permanently delete this conversation?
            </n-popconfirm>
          </div>
        </header>
        <section v-if="contextPanelOpen && activeConversation" class="context-panel">
          <div class="context-panel-copy">
            <strong>Conversation context</strong>
            <span>Pin resources for stable follow-up questions, or leave everything empty for automatic selection.</span>
          </div>
          <label>
            <span>Profile</span>
            <n-select v-model:value="selectedProfileId" clearable :options="profileOptions" placeholder="Automatic profile" />
          </label>
          <label>
            <span>Search runs (up to 3)</span>
            <n-select v-model:value="selectedRunIds" multiple :max-tag-count="2" :options="searchRunOptions" placeholder="Automatic recent searches" />
          </label>
          <label>
            <span>Saved jobs (up to 20)</span>
            <n-select v-model:value="selectedSavedJobIds" multiple :max-tag-count="2" :options="savedJobOptions" placeholder="Automatic active jobs" />
          </label>
          <div class="context-panel-actions">
            <n-button size="small" @click="useAutomaticContext">Use automatic</n-button>
            <n-button size="small" type="primary" @click="saveContextSelection">Save context</n-button>
          </div>
        </section>
        <section v-if="memoryPanelOpen && memoryStatus" class="memory-panel">
          <div class="memory-panel-heading">
            <div>
              <strong>Current memory</strong>
              <span>Composition only — business data remains in its original resources.</span>
            </div>
            <n-tag size="small" round>{{ memoryStatus.total_turn_count }} turns</n-tag>
          </div>
          <div class="memory-grid">
            <div class="memory-card">
              <span>Recent conversation</span>
              <strong>{{ memoryStatus.recent_turn_count }} turns</strong>
              <small>Turns after the current summary boundary</small>
            </div>
            <div class="memory-card">
              <span>Compressed summary</span>
              <strong>{{ summaryFactCount ? `${summaryFactCount} facts` : "Not created" }}</strong>
              <small v-if="memoryStatus.summary_through_sequence">
                Version {{ memoryStatus.summary_version }} · through turn {{ memoryStatus.summary_through_sequence }}
              </small>
              <small v-else>Created automatically when the conversation grows</small>
            </div>
            <div class="memory-card memory-resource-card">
              <span>Pinned context</span>
              <strong>{{ memoryStatus.pinned_context.length }} resources</strong>
              <div v-if="memoryStatus.pinned_context.length" class="memory-resource-list">
                <div v-for="item in memoryStatus.pinned_context" :key="`${item.source_type}:${item.resource_id}`">
                  <span>{{ item.label }}</span>
                  <n-tag size="tiny" :type="item.status === 'available' ? 'success' : 'error'">{{ item.status }}</n-tag>
                </div>
              </div>
              <small v-else>Automatic selection; nothing is pinned</small>
            </div>
            <div class="memory-card memory-resource-card">
              <span>Previous answer references</span>
              <strong>{{ memoryStatus.previous_references.length }} resources</strong>
              <div v-if="memoryStatus.previous_references.length" class="memory-resource-list">
                <div v-for="item in memoryStatus.previous_references" :key="`${item.source_type}:${item.resource_id}`">
                  <span>{{ item.label }}</span>
                  <n-tag size="tiny" :type="item.status === 'available' ? 'success' : 'error'">{{ item.status }}</n-tag>
                </div>
              </div>
              <small v-else>No resource references from the latest answer</small>
            </div>
          </div>
        </section>
        <section v-else-if="memoryPanelOpen" class="memory-panel memory-unavailable">
          Memory status is temporarily unavailable. Chat history and answers are unaffected.
        </section>
      </div>

      <div ref="messageList" class="message-list">
        <div v-if="!turns.length && !loading" class="chat-empty">
          <div class="assistant-orb"><AppIcon name="sparkles" /></div>
          <n-empty description="Ask about your profile, search results, saved jobs, applications, or interviews." />
          <div class="suggestions">
            <button v-for="item in suggestions" :key="item" @click="sendQuestion(item)">{{ item }}</button>
          </div>
        </div>

        <article v-for="turn in turns" :key="turn.turn_id" class="turn-group">
          <div class="message-row user-row"><div class="message-bubble user-bubble">{{ turn.question }}</div></div>
          <div class="message-row assistant-row">
            <div class="assistant-avatar"><AppIcon name="sparkles" /></div>
            <div class="assistant-content">
              <div class="message-bubble assistant-bubble">{{ turn.answer }}</div>
              <div v-if="turn.citations.length" class="citation-list">
                <template v-for="citation in turn.citations" :key="citation.citation_id">
                  <RouterLink v-if="citation.href" :to="citation.href" class="citation-chip">
                    {{ citation.label }}
                  </RouterLink>
                  <span v-else class="citation-chip">{{ citation.label }}</span>
                </template>
              </div>
              <div class="turn-meta">
                <n-tag size="small" :type="turn.analysis_mode === 'llm' ? 'success' : 'warning'">
                  {{ turn.analysis_mode }}
                </n-tag>
                <span>{{ usageText(turn) }}</span>
                <span v-if="fallbackReasonText(turn)" class="fallback-reason">
                  {{ fallbackReasonText(turn) }}
                </span>
                <button
                  v-if="turn.analysis_mode === 'fallback'"
                  class="retry-turn"
                  :disabled="sending"
                  @click="retryTurn(turn)"
                >Retry</button>
                <n-popconfirm @positive-click="removeTurn(turn.turn_id)">
                  <template #trigger><button class="delete-turn">Delete turn</button></template>
                  Delete this question, answer, citations, and derived summary memory?
                </n-popconfirm>
              </div>
            </div>
          </div>
        </article>

        <div v-if="sending" class="message-row assistant-row">
          <div class="assistant-avatar"><AppIcon name="sparkles" /></div>
          <div class="message-bubble assistant-bubble"><n-spin size="small" /> Checking the right context…</div>
        </div>
      </div>

      <footer class="composer">
        <n-input
          v-model:value="draft"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 6 }"
          maxlength="2000"
          show-count
          placeholder="Ask about your profile, searches, saved jobs, or career plan…"
          @keydown.enter.exact.prevent="sendQuestion()"
        />
        <div class="composer-footer">
          <span>Personal data is retrieved only when the conversation setting and router both allow it.</span>
          <n-button type="primary" :loading="sending" :disabled="!draft.trim()" @click="sendQuestion()">Send</n-button>
        </div>
      </footer>
    </div>
  </section>
</template>

<style scoped>
.chat-page { display: grid; grid-template-columns: clamp(220px, 19vw, 260px) minmax(0, 1fr); height: calc(100dvh - var(--topbar-height)); min-height: 0; overflow: hidden; background: #f6f8f5; }
.chat-history-panel { border-right: 1px solid #dfe7df; background: #fff; padding: 22px 16px; overflow: auto; }
.panel-heading, .chat-toolbar, .composer-footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.eyebrow { color: #2f7650; font-size: 11px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }
h1, h2 { margin: 3px 0 0; color: #173123; }
h1 { font-size: 20px; } h2 { font-size: 18px; }
.conversation-list { display: grid; gap: 6px; margin-top: 22px; }
.conversation-item { display: flex; gap: 10px; width: 100%; border: 0; border-radius: 12px; padding: 11px; text-align: left; color: #496052; background: transparent; cursor: pointer; }
.conversation-item:hover, .conversation-item.active { background: #edf5ef; color: #145f38; }
.conversation-item svg { width: 18px; flex: 0 0 auto; margin-top: 2px; }
.conversation-item span { min-width: 0; display: grid; gap: 3px; }
.conversation-item strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conversation-item small { color: #809087; }
.chat-workspace { min-width: 0; min-height: 0; display: grid; grid-template-rows: auto minmax(0, 1fr) auto; }
.chat-context-header { border-bottom: 1px solid #dfe7df; background: rgba(255,255,255,.94); }
.chat-toolbar { align-items: flex-start; flex-wrap: wrap; padding: 16px 24px; border-bottom: 1px solid #dfe7df; background: rgba(255,255,255,.92); }
.active-context-row { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 7px; }
.context-panel { display: grid; grid-template-columns: 1.1fr repeat(3, minmax(160px, 1fr)) auto; align-items: end; gap: 12px; padding: 14px 24px 18px; }
.context-panel-copy { display: grid; gap: 3px; color: #304a39; }
.context-panel-copy span { color: #728177; font-size: 12px; line-height: 1.4; }
.context-panel label { display: grid; gap: 6px; color: #52675a; font-size: 12px; font-weight: 700; }
.context-panel-actions { display: flex; gap: 7px; }
.memory-panel { padding: 15px 24px 18px; }
.memory-panel-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 12px; }
.memory-panel-heading > div { display: grid; gap: 3px; color: #304a39; }
.memory-panel-heading span { color: #728177; font-size: 12px; }
.memory-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.memory-card { min-width: 0; display: grid; align-content: start; gap: 5px; border: 1px solid #dfe7df; border-radius: 12px; padding: 12px; background: #f9fbf9; }
.memory-card > span { color: #6d7e72; font-size: 11px; font-weight: 800; text-transform: uppercase; }
.memory-card > strong { color: #284434; font-size: 15px; }
.memory-card small { color: #75847a; line-height: 1.4; }
.memory-resource-list { display: grid; gap: 5px; margin-top: 3px; }
.memory-resource-list > div { min-width: 0; display: flex; align-items: center; justify-content: space-between; gap: 6px; }
.memory-resource-list > div > span { overflow: hidden; color: #53695a; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.memory-unavailable { color: #75847a; font-size: 13px; }
.toolbar-actions { display: flex; max-width: min(780px, 100%); flex: 1 1 600px; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 8px; }
.access-select { width: 220px; }
.message-list { overflow-y: auto; padding: 28px max(24px, calc((100% - 850px) / 2)); }
.chat-empty { min-height: 55vh; display: grid; align-content: center; justify-items: center; gap: 18px; }
.assistant-orb, .assistant-avatar { display: grid; place-items: center; color: #fff; background: linear-gradient(145deg, #145f38, #178579); }
.assistant-orb { width: 52px; height: 52px; border-radius: 17px; box-shadow: 0 12px 28px rgba(20,95,56,.2); }
.assistant-orb svg { width: 26px; }
.suggestions { display: grid; width: min(620px, 100%); gap: 8px; }
.suggestions button { border: 1px solid #d7e4d9; border-radius: 12px; padding: 12px 15px; color: #365444; background: #fff; cursor: pointer; text-align: left; }
.suggestions button:hover { border-color: #58a174; background: #f4faf5; }
.turn-group { display: grid; gap: 16px; margin-bottom: 28px; }
.message-row { display: flex; gap: 11px; }
.user-row { justify-content: flex-end; }
.message-bubble { white-space: pre-wrap; line-height: 1.65; }
.user-bubble { max-width: 75%; border-radius: 18px 18px 4px 18px; padding: 12px 16px; color: #fff; background: #145f38; }
.assistant-avatar { width: 32px; height: 32px; border-radius: 10px; flex: 0 0 auto; }
.assistant-avatar svg { width: 17px; }
.assistant-content { min-width: 0; max-width: 85%; }
.assistant-bubble { color: #23382b; }
.citation-list, .turn-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 7px; margin-top: 12px; }
.citation-chip { border: 1px solid #cfe1d3; border-radius: 999px; padding: 5px 9px; color: #1e6840; background: #f4faf5; font-size: 12px; text-decoration: none; }
.turn-meta { color: #7a8b81; font-size: 12px; }
.retry-turn, .delete-turn { border: 0; padding: 0; background: none; cursor: pointer; }
.retry-turn { color: #1e6840; font-weight: 600; }
.retry-turn:disabled { color: #9aa69f; cursor: not-allowed; }
.fallback-reason { color: #9a6a22; }
.delete-turn { color: #8a5b5b; }
.composer { padding: 14px max(24px, calc((100% - 850px) / 2)) 18px; border-top: 1px solid #dfe7df; background: #fff; }
.composer-footer { margin-top: 8px; color: #77877d; font-size: 11px; }
@media (max-width: 850px) {
  .chat-page { grid-template-columns: 1fr; height: calc(100dvh - var(--topbar-height)); }
  .chat-history-panel { display: none; }
  .toolbar-actions { flex-wrap: wrap; justify-content: flex-end; }
  .access-select { width: 185px; }
  .chat-toolbar { align-items: flex-start; }
  .context-panel { grid-template-columns: 1fr; align-items: stretch; }
  .memory-grid { grid-template-columns: 1fr 1fr; }
  .message-list { min-height: 60vh; }
}
@media (max-width: 1320px) and (min-width: 851px) {
  .context-panel { grid-template-columns: 1fr 1fr; align-items: end; }
  .context-panel-copy, .context-panel-actions { grid-column: 1 / -1; }
  .memory-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 720px) {
  .memory-grid { grid-template-columns: 1fr; }
}
</style>
