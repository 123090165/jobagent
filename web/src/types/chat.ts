export type ChatDataAccessMode = "auto" | "always" | "off";
export type ChatSource = "profile" | "search_results" | "saved_jobs" | "chat_history";

export interface ChatSearchResultRef {
  job_search_run_id: string;
  job_result_id: string;
}

export type ChatTurnAttachment =
  | ({ type: "search_result" } & ChatSearchResultRef)
  | { type: "saved_job"; saved_job_id: string };

export interface ChatDataScope {
  allowed_sources: ChatSource[];
  resume_profile_id?: string | null;
  job_search_run_ids: string[];
  job_search_result_refs: ChatSearchResultRef[];
  saved_job_ids: string[];
}

export interface ChatConversationCreatePayload {
  title?: string;
  data_access_mode?: ChatDataAccessMode;
  data_scope?: Partial<ChatDataScope>;
}

export interface ChatConversationUpdatePayload {
  title?: string;
  data_access_mode?: ChatDataAccessMode;
  data_scope?: ChatDataScope;
}

export interface ChatConversation {
  conversation_id: string;
  user_id: string;
  title: string;
  data_access_mode: ChatDataAccessMode;
  data_scope: ChatDataScope;
  summary: Record<string, unknown>;
  summary_through_sequence: number;
  summary_version: number;
  last_retrieval_used: boolean;
  last_retrieval_sources: ChatSource[];
  last_completed_sequence: number;
  created_at: string;
  updated_at: string;
}

export interface ChatCitation {
  citation_id: string;
  source_type: ChatSource;
  resource_id: string;
  label: string;
  excerpt?: string | null;
  href?: string | null;
}

export interface ChatRouteDecision {
  domain: "in_scope" | "out_of_scope" | "unclear";
  retrieval: ChatSource[];
  relation_to_previous: "follow_up" | "new_topic" | "unclear";
  freshness: "reuse_allowed" | "refresh_required";
  confidence: number;
  reason?: string | null;
}

export interface ChatRetrievalRequest {
  source: ChatSource;
  strategy: "use_attachment" | "use_pinned" | "reuse_previous" | "load_recent";
  policy_reason: string;
}

export interface ChatRetrievalPlan {
  agent_sources: ChatSource[];
  requests: ChatRetrievalRequest[];
  freshness: "reuse_allowed" | "refresh_required";
  policy_reasons: string[];
}

export interface ChatTurn {
  turn_id: string;
  conversation_id: string;
  user_id: string;
  sequence: number;
  client_turn_id: string;
  question: string;
  answer?: string | null;
  status: "pending" | "completed" | "failed";
  route?: ChatRouteDecision | null;
  retrieval_plan?: ChatRetrievalPlan | null;
  retrieval_used: boolean;
  retrieved_refs: string[];
  citations: ChatCitation[];
  analysis_mode?: "llm" | "deterministic" | "fallback" | "refused" | null;
  analysis_provider?: string | null;
  fallback_reason?: string | null;
  quality_warnings: string[];
  context_attachments: ChatTurnAttachment[];
  retry_of_turn_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatConversationListResponse { items: ChatConversation[]; }
export interface ChatTurnListResponse { items: ChatTurn[]; }

export interface ChatProfileContextOption {
  resume_profile_id: string;
  label: string;
  summary: string;
  is_default: boolean;
}

export interface ChatSearchRunContextOption {
  job_search_run_id: string;
  label: string;
  query: string;
  result_count: number;
  created_at: string;
}

export interface ChatSavedJobContextOption {
  saved_job_id: string;
  label: string;
  title: string;
  company?: string | null;
  status: string;
  updated_at: string;
}

export interface ChatContextCatalog {
  profiles: ChatProfileContextOption[];
  search_runs: ChatSearchRunContextOption[];
  saved_jobs: ChatSavedJobContextOption[];
}

export interface ChatMemoryResource {
  source_type: ChatSource;
  resource_id: string;
  label: string;
  status: "available" | "unavailable";
}

export interface ChatMemoryStatus {
  conversation_id: string;
  total_turn_count: number;
  recent_turn_count: number;
  summary: Record<string, unknown>;
  summary_version: number;
  summary_through_sequence: number;
  pinned_context: ChatMemoryResource[];
  previous_references: ChatMemoryResource[];
  updated_at: string;
}
