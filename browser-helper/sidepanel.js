const LOCAL_KEYS = ["selectedProfileSessionId", "selectedConversationId", "useLlm"];

const nodes = {
  status: document.getElementById("status"), pairing: document.getElementById("pairing"),
  assistant: document.getElementById("assistant"), conversation: document.getElementById("conversationSelect"),
  conversationContext: document.getElementById("conversationContext"),
  profile: document.getElementById("profileSessionSelect"), profileField: document.getElementById("profileField"),
  activeProfile: document.getElementById("activeProfile"), useLlm: document.getElementById("useLlm"),
  capture: document.getElementById("capture"), captureBadge: document.getElementById("captureBadge"),
  turns: document.getElementById("turns"), question: document.getElementById("question"),
  savedJob: document.getElementById("savedJobSelect"),
  captureButton: document.getElementById("captureButton"), sendButton: document.getElementById("sendButton"),
  analyzeButton: document.getElementById("analyzeButton"), analysisControls: document.getElementById("analysisControls"),
  newButton: document.getElementById("newConversationButton"), openButton: document.getElementById("openAssistantButton"),
  openPairingButton: document.getElementById("openPairingButton"),
  chatStage: document.getElementById("chatStage"),
  analysisReport: document.getElementById("analysisReport"),
  analysisScore: document.getElementById("analysisScore"),
  analysisRecommendation: document.getElementById("analysisRecommendation"),
  analysisStrengths: document.getElementById("analysisStrengths"),
  analysisGaps: document.getElementById("analysisGaps"),
  analysisActions: document.getElementById("analysisActions"),
  analysisWarnings: document.getElementById("analysisWarnings"),
  greetingControls: document.getElementById("greetingControls"),
  greetingDraft: document.getElementById("greetingDraft"),
  greetingContent: document.getElementById("greetingContent"),
  greetingEvidence: document.getElementById("greetingEvidence"),
  greetingAvoid: document.getElementById("greetingAvoid"),
  greetingAvoidSection: document.getElementById("greetingAvoidSection"),
  generateGreetingButton: document.getElementById("generateGreetingButton"),
  regenerateGreetingButton: document.getElementById("regenerateGreetingButton"),
  sendGreetingButton: document.getElementById("sendGreetingButton"),
  resumeControls: document.getElementById("resumeControls"),
  generateResumeButton: document.getElementById("generateResumeButton")
};

let currentCaptureRef = null;
let currentCaptureId = null;
let hasAnalysisProfile = false;
let hasCapturedJob = false;
let assistantStateRefresh = 0;
let currentGreetingDraft = null;
let profileBySessionId = new Map();

void init().catch(renderInitializationFailure);

async function init() {
  bindEvents();
  const saved = await chrome.storage.local.get(LOCAL_KEYS);
  nodes.useLlm.checked = saved.useLlm !== false;
  chrome.storage.onChanged.addListener(handleStorageChange);
  await refreshAssistantState();
}

function renderInitializationFailure(error) {
  const detail = error instanceof Error ? error.message : String(error || "Unknown error");
  nodes.assistant?.classList.add("hidden");
  nodes.pairing?.classList.remove("hidden");
  if (nodes.status) {
    nodes.status.textContent = `Browser Helper could not start: ${detail}`;
    nodes.status.classList.add("error");
  }
}

function handleStorageChange(changes, areaName) {
  if (areaName !== "session") return;
  if (!["accessToken", "expiresAt", "profileSessions", "appUrl", "backendUrl"].some((key) => key in changes)) return;
  void refreshAssistantState();
}

async function refreshAssistantState() {
  const refreshId = ++assistantStateRefresh;
  setStatus("Loading Assistant...");
  try {
    const saved = await chrome.storage.local.get(LOCAL_KEYS);
    const state = await request({ action: "getAssistantState" });
    if (refreshId !== assistantStateRefresh) return;
    if (!state.paired) return showPairing();
    nodes.pairing.classList.add("hidden");
    nodes.assistant.classList.remove("hidden");
    configureAnalysisProfiles(state.profileSessions || [], saved.selectedProfileSessionId);
    fillSelect(nodes.conversation, state.conversations || [], "conversation_id", "title", saved.selectedConversationId, "No conversation");
    fillSavedJobSelect(state.savedJobs || []);
    setStatus("Connected. Capture the current JD to start chatting.");
  } catch (error) {
    if (refreshId !== assistantStateRefresh) return;
    showPairing(String(error));
  }
}

function bindEvents() {
  bindAsyncEvent(nodes.captureButton, "click", captureCurrentPage);
  bindAsyncEvent(nodes.analyzeButton, "click", analyzeCapturedJob);
  bindAsyncEvent(nodes.generateGreetingButton, "click", generateGreeting);
  bindAsyncEvent(nodes.regenerateGreetingButton, "click", generateGreeting);
  bindAsyncEvent(nodes.sendGreetingButton, "click", confirmAndSendGreeting);
  bindAsyncEvent(nodes.generateResumeButton, "click", generateTailoredResume);
  bindAsyncEvent(nodes.sendButton, "click", sendTurn);
  bindAsyncEvent(nodes.newButton, "click", createConversation);
  bindAsyncEvent(nodes.conversation, "change", async () => {
    await saveSettings();
    if (currentCaptureRef) await attachCaptureToConversation();
    await loadTurns();
  });
  bindAsyncEvent(nodes.profile, "change", saveSettings);
  bindAsyncEvent(nodes.useLlm, "change", saveSettings);
  bindAsyncEvent(nodes.openButton, "click", openFullAssistant);
  bindAsyncEvent(nodes.openPairingButton, "click", openAndPairAssistant);
  bindAsyncEvent(nodes.question, "keydown", async (event) => {
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    await sendTurn();
  });
}

function bindAsyncEvent(node, eventName, handler) {
  node.addEventListener(eventName, (...args) => {
    void Promise.resolve().then(() => handler(...args)).catch(renderActionFailure);
  });
}

function renderActionFailure(error) {
  const detail = error instanceof Error ? error.message : String(error || "Unknown error");
  setStatus(`Browser Helper action failed: ${detail}`, true);
}

async function createConversation() {
  setBusy(true);
  try {
    const response = await request({ action: "createAssistantConversation" });
    const option = new Option(response.conversation.title, response.conversation.conversation_id, true, true);
    nodes.conversation.prepend(option);
    await saveSettings();
    if (currentCaptureRef) await attachCaptureToConversation();
    renderTurns([]);
  } catch (error) { setStatus(String(error), true); }
  finally { setBusy(false); }
}

async function loadTurns() {
  if (!nodes.conversation.value) return renderTurns([]);
  try {
    const response = await request({ action: "loadAssistantTurns", conversationId: nodes.conversation.value });
    renderTurns(response.turns || []);
  } catch (error) { setStatus(String(error), true); }
}

async function captureCurrentPage() {
  setBusy(true); setStatus("Reading the current BOSS job page...");
  let permission = null;
  try {
    permission = await ensureBossPermission();
    const response = await request({ action: "captureCurrentJob" });
    const capture = response.capture || {};
    if (!response.captureId || !response.savedJobId) throw new Error("Capture succeeded but no job workspace reference was returned.");
    currentCaptureId = response.captureId;
    currentCaptureRef = { type: "saved_job", saved_job_id: response.savedJobId };
    hasCapturedJob = true;
    nodes.capture.textContent = [
      capture.title || capture.page_title || "Captured job",
      capture.company || "",
      capture.source_url || "",
      "",
      capture.jd_text || "No JD text was returned."
    ].filter((item, index) => item || index === 3).join("\n");
    nodes.capture.classList.remove("hidden");
    nodes.captureBadge.textContent = "Ready";
    nodes.chatStage.classList.remove("hidden");
    nodes.analysisControls.classList.remove("hidden");
    nodes.greetingControls.classList.remove("hidden");
    nodes.resumeControls.classList.remove("hidden");
    currentGreetingDraft = null;
    nodes.greetingDraft.classList.add("hidden");
    if (!nodes.conversation.value) await createConversation();
    else {
      await attachCaptureToConversation();
      await loadTurns();
    }
    nodes.question.focus();
    setStatus("JD captured and attached. Type a question below or open the full chat.");
  } catch (error) { setStatus(String(error), true); }
  finally {
    if (permission) await revokeTemporaryPermission(permission);
    setBusy(false);
  }
}

async function revokeTemporaryPermission(origin) {
  try {
    await chrome.permissions.remove({ origins: [origin] });
  } catch (_error) {
    // Capture is already complete; permission cleanup is best-effort.
  }
}

async function analyzeCapturedJob() {
  if (!currentCaptureRef) return setStatus("Capture a JD before running match analysis.", true);
  if (!nodes.profile.value) return setStatus("A confirmed Analysis profile is required for match analysis.", true);
  setBusy(true); setStatus("Analyzing the captured JD against your Profile...");
  try {
    const response = await request({
      action: "analyzeCapturedJob",
      captureId: currentCaptureId,
      sessionId: nodes.profile.value,
      useLlm: nodes.useLlm.checked,
      analysisMode: nodes.useLlm.checked ? "llm" : "deterministic",
      llmProvider: "deepseek"
    });
    renderAnalysisReport(response.analysis?.report, response.analysis?.warnings || []);
    setStatus("Match analysis complete. The captured JD remains available in Chat.");
  } catch (error) { setStatus(String(error), true); }
  finally { setBusy(false); }
}

async function generateGreeting() {
  if (!currentCaptureRef) return setStatus("Capture a JD before generating a greeting.", true);
  const selectedProfile = profileBySessionId.get(nodes.profile.value);
  if (!selectedProfile?.resume_profile_id) {
    return setStatus("A confirmed resume profile is required to generate a grounded greeting.", true);
  }
  setBusy(true); setStatus("Generating an evidence-grounded greeting...");
  try {
    const response = await request({
      action: "generateGreetingDraft",
      captureId: currentCaptureId,
      resumeProfileId: selectedProfile.resume_profile_id,
      llmProvider: "deepseek"
    });
    currentGreetingDraft = response.draft;
    nodes.greetingContent.value = currentGreetingDraft.generated_content || "";
    renderTextList(nodes.greetingEvidence, currentGreetingDraft.evidence_used, "No explicit evidence was selected.");
    const avoidClaims = uniqueText(currentGreetingDraft.avoid_claims);
    renderTextList(nodes.greetingAvoid, avoidClaims, "");
    nodes.greetingAvoidSection.classList.toggle("hidden", avoidClaims.length === 0);
    nodes.greetingDraft.classList.remove("hidden");
    setStatus("Greeting ready. Review every claim before sending.");
  } finally {
    setBusy(false);
  }
}

async function confirmAndSendGreeting() {
  const content = nodes.greetingContent.value.trim();
  if (!currentGreetingDraft || !content) return setStatus("Generate and review a greeting first.", true);
  const confirmed = window.confirm(
    `Send this exact message through the currently open BOSS page?\n\n${content}`
  );
  if (!confirmed) return;
  setBusy(true); setStatus("Sending and verifying the visible BOSS conversation...");
  try {
    const response = await request({
      action: "sendGreetingDraft",
      draftId: currentGreetingDraft.draft_id,
      content
    });
    currentGreetingDraft = response.draft;
    nodes.greetingContent.value = response.draft?.approved_content || content;
    setStatus("Greeting sent and saved. Application stage is now Contacted.");
    nodes.sendGreetingButton.disabled = true;
  } finally {
    setBusy(false);
  }
}

async function generateTailoredResume() {
  if (!currentCaptureRef) return setStatus("Capture a JD before generating a tailored resume.", true);
  const selectedProfile = profileBySessionId.get(nodes.profile.value);
  if (!selectedProfile?.resume_profile_id) {
    return setStatus("A confirmed resume profile is required to generate a tailored resume.", true);
  }
  setBusy(true); setStatus("Creating a fact-checked tailored resume version...");
  try {
    const response = await request({
      action: "generateTailoredResume",
      captureId: currentCaptureId,
      resumeProfileId: selectedProfile.resume_profile_id,
      llmProvider: "deepseek"
    });
    setStatus(`Tailored resume version ${response.resume?.version || 1} created. Opening the application workbench.`);
  } finally {
    setBusy(false);
  }
}

async function sendTurn() {
  const question = nodes.question.value.trim();
  if (!question || !nodes.conversation.value) return;
  setBusy(true); setStatus("Assistant is working...");
  try {
    const attachments = currentCaptureRef ? [currentCaptureRef] : [];
    if (nodes.savedJob.value) {
      attachments.push({ type: "saved_job", saved_job_id: nodes.savedJob.value });
    }
    await request({ action: "sendAssistantTurn", conversationId: nodes.conversation.value, question, contextAttachments: attachments });
    nodes.question.value = "";
    await loadTurns(); setStatus("Answer ready.");
  } catch (error) { setStatus(String(error), true); }
  finally { setBusy(false); }
}

async function attachCaptureToConversation() {
  if (!currentCaptureRef || !nodes.conversation.value) return;
  const response = await request({
    action: "attachAssistantSavedJob",
    conversationId: nodes.conversation.value,
    savedJobId: currentCaptureRef.saved_job_id
  });
  const title = response.conversation?.title || selectedConversationTitle();
  nodes.conversationContext.textContent = `JD attached to “${title}”. It is also visible as pinned context in the full chat.`;
}

function selectedConversationTitle() {
  return nodes.conversation.selectedOptions[0]?.textContent || "this conversation";
}

function renderTurns(turns) {
  nodes.turns.innerHTML = "";
  if (!turns.length) { nodes.turns.textContent = "Start a conversation, or capture this job and ask a question."; return; }
  for (const turn of turns) {
    nodes.turns.append(messageNode("You", turn.question), messageNode("Assistant", turn.answer || (turn.status === "pending" ? "Working..." : "No answer returned.")));
  }
  nodes.turns.scrollTop = nodes.turns.scrollHeight;
}

function messageNode(role, text) {
  const article = document.createElement("article"); article.className = `message ${role === "You" ? "user" : "assistant-message"}`;
  const label = document.createElement("strong"); label.textContent = role;
  const body = document.createElement("p"); body.textContent = text;
  article.append(label, body); return article;
}

async function ensureBossPermission() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = new URL(String(tab?.url || ""));
  if (url.protocol !== "https:" || url.hostname !== "www.zhipin.com" || !/^\/job_detail\//.test(url.pathname)) throw new Error("Open a BOSS job detail page first.");
  const origin = "https://www.zhipin.com/*";
  if (!await chrome.permissions.contains({ origins: [origin] }) && !await chrome.permissions.request({ origins: [origin] })) throw new Error("Page-read permission was not granted.");
  return origin;
}

function fillSelect(select, items, valueKey, labelKey, selected, emptyLabel) {
  select.innerHTML = "";
  if (!items.length) { select.add(new Option(emptyLabel, "")); return; }
  for (const item of items) select.add(new Option(item[labelKey] || "Untitled", item[valueKey], false, item[valueKey] === selected));
  if (!select.value) select.selectedIndex = 0;
}

function configureAnalysisProfiles(profiles, storedSessionId) {
  profileBySessionId = new Map(profiles.map((item) => [item.session_id, item]));
  hasAnalysisProfile = profiles.length > 0;
  const defaultProfile = profiles.find((item) => item.is_default) || profiles[0];
  const selectedSessionId = profiles.some((item) => item.session_id === storedSessionId)
    ? storedSessionId
    : defaultProfile?.session_id;
  const displayProfiles = profiles.map((item) => ({
    ...item,
    display_label: item.is_default ? `${item.label} (Default)` : item.label
  }));
  fillSelect(
    nodes.profile,
    displayProfiles,
    "session_id",
    "display_label",
    selectedSessionId,
    "No confirmed Profile"
  );
  const hasSingleProfile = profiles.length === 1;
  nodes.profileField.classList.toggle("hidden", hasSingleProfile);
  nodes.activeProfile.classList.toggle("hidden", !hasSingleProfile);
  nodes.activeProfile.textContent = hasSingleProfile
    ? `Analysis profile: ${displayProfiles[0].display_label}`
    : "";
  nodes.analyzeButton.disabled = !hasAnalysisProfile || !hasCapturedJob;
}

function fillSavedJobSelect(items) {
  nodes.savedJob.innerHTML = "";
  nodes.savedJob.add(new Option("Let the agent search automatically", ""));
  for (const item of items) {
    const company = item.company ? ` · ${item.company}` : "";
    nodes.savedJob.add(new Option(`${item.title}${company}`, item.saved_job_id));
  }
}

function renderAnalysisReport(report, warnings) {
  const value = report || {};
  nodes.analysisScore.textContent = Number.isFinite(value.overall_score)
    ? `${Math.round(value.overall_score)} / 100`
    : "Completed";
  nodes.analysisRecommendation.textContent = value.recommendation || "Analysis completed without a recommendation.";
  renderTextList(nodes.analysisStrengths, value.matched_strengths, "No matched strengths returned.");
  renderTextList(nodes.analysisGaps, value.critical_gaps, "No critical gaps returned.");
  renderTextList(nodes.analysisActions, value.resume_actions, "No resume actions returned.");
  const warningValues = uniqueText(warnings);
  nodes.analysisWarnings.textContent = warningValues.length ? `Warnings: ${warningValues.join(" · ")}` : "";
  nodes.analysisWarnings.classList.toggle("hidden", !warningValues.length);
  nodes.analysisReport.classList.remove("hidden");
}

function renderTextList(node, values, emptyText) {
  node.innerHTML = "";
  const items = uniqueText(values);
  for (const text of items.length ? items : [emptyText]) {
    const item = document.createElement("li");
    item.textContent = text;
    node.append(item);
  }
}

function uniqueText(values) {
  return [...new Set((values || []).map((item) => String(item || "").trim()).filter(Boolean))];
}

async function saveSettings() {
  await chrome.storage.local.set({ selectedProfileSessionId: nodes.profile.value, selectedConversationId: nodes.conversation.value, useLlm: nodes.useLlm.checked });
}

async function openFullAssistant() { await chrome.runtime.sendMessage({ action: "openAssistantConversation", conversationId: nodes.conversation.value || null }); }
async function openAndPairAssistant() { await chrome.runtime.sendMessage({ action: "openAssistantConversation", requestPair: true }); }
async function request(payload) { const response = await chrome.runtime.sendMessage(payload); if (!response?.ok) throw new Error(response?.error || "Extension request failed."); return response; }
function showPairing(detail = "") { nodes.assistant.classList.add("hidden"); nodes.pairing.classList.remove("hidden"); setStatus(detail || "Browser Helper is not paired.", Boolean(detail)); }
function setStatus(text, error = false) { nodes.status.textContent = text; nodes.status.classList.toggle("error", error); }
function setBusy(value) {
  nodes.captureButton.disabled = value;
  nodes.analyzeButton.disabled = value || !hasAnalysisProfile || !hasCapturedJob;
  nodes.sendButton.disabled = value;
  nodes.newButton.disabled = value;
  nodes.generateGreetingButton.disabled = value || !hasAnalysisProfile || !hasCapturedJob;
  nodes.generateResumeButton.disabled = value || !hasAnalysisProfile || !hasCapturedJob;
  nodes.regenerateGreetingButton.disabled = value;
  nodes.sendGreetingButton.disabled = value || currentGreetingDraft?.status === "sent";
}
