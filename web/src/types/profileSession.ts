/**
 * 声明主流程会话及各阶段快照的前端类型，对齐后端 ProfileSession 聚合响应。
 */
export type ProfileSessionStatus = "active" | "completed" | "archived";

export type ProfileSessionStep =
  | "created"
  | "resume_empty"
  | "resume_ready"
  | "resume_review"
  | "profile_draft"
  | "profile_confirmed"
  | "job_search_ready"
  | "job_search_running"
  | "job_search_completed"
  | "brief_ready"
  | "archived";

export interface ProfileSession {
  session_id: string;
  status: ProfileSessionStatus;
  created_at: string;
  updated_at: string;
  resume_document_id: string | null;
  parsed_review_id: string | null;
  profile_draft_id: string | null;
  confirmed_profile_id: string | null;
  current_step: ProfileSessionStep;
}

export interface ResumeDocument {
  resume_document_id: string;
  session_id: string;
  source_type: "text" | "file";
  filename: string | null;
  file_type: string | null;
  text: string;
  text_length: number;
  created_at: string;
  updated_at: string;
}

export interface ResumeIntakeResponse {
  resume_document: ResumeDocument;
  profile_session: ProfileSession;
}

export interface ParsedResumeReview {
  parsed_review_id: string;
  session_id: string;
  resume_document_id: string;
  basic_info: {
    name?: string | null;
    highlights?: string[];
    certificates?: string[];
  };
  education: Array<Record<string, unknown>>;
  work_experience: Array<Record<string, unknown>>;
  projects: Array<Record<string, unknown>>;
  skills: {
    items: string[];
    count: number;
  };
  target_signals: string[];
  quality_warnings: string[];
  missing_info_questions: string[];
  raw_parser_output: Record<string, unknown> | null;
  analysis_mode: "deterministic" | "llm" | "llm_guided" | "fallback";
  analysis_provider: string | null;
  analysis_warnings: string[];
  created_at: string;
  updated_at: string;
}

export interface ParsedResumeReviewResponse {
  parsed_review: ParsedResumeReview;
  profile_session: ProfileSession;
}

export interface ProfileDraft {
  profile_draft_id: string;
  session_id: string;
  parsed_review_id: string;
  summary: string;
  target_roles: string[];
  target_directions: string[];
  core_skills: string[];
  supporting_skills: string[];
  search_keywords: string[];
  preferred_locations: string[];
  work_arrangements: string[];
  strengths: string[];
  risks: string[];
  missing_info_questions: string[];
  created_at: string;
  updated_at: string;
}

export interface ProfileDraftResponse {
  profile_draft: ProfileDraft;
  profile_session: ProfileSession;
}

export interface ConfirmedProfile {
  confirmed_profile_id: string;
  session_id: string;
  resume_document_id: string;
  parsed_review_id: string;
  profile_draft_id: string;
  summary: string;
  target_roles: string[];
  target_directions: string[];
  core_skills: string[];
  supporting_skills: string[];
  search_keywords: string[];
  preferred_locations: string[];
  work_arrangements: string[];
  strengths: string[];
  risks: string[];
  missing_info_questions: string[];
  created_at: string;
  updated_at: string;
}

export interface ConfirmedProfileResponse {
  confirmed_profile: ConfirmedProfile;
  profile_session: ProfileSession;
}

export interface JDRequirement {
  category:
    | "skill"
    | "experience"
    | "education"
    | "location"
    | "employment_type"
    | "work_authorization"
    | "other";
  name: string;
  necessity: "required" | "preferred" | "unknown";
  evidence_quote: string | null;
  confidence: number;
}

export interface JobSearchResult {
  job_result_id: string;
  title: string;
  company: string;
  location: string;
  source: "local_mock" | "live_search";
  source_provider: string | null;
  source_url: string | null;
  raw_snippet: string | null;
  description: string;
  matched_keywords: string[];
  match_reasons: string[];
  risks: string[];
  match_score: number;
  score_breakdown: Record<string, number>;
  evidence_quotes: string[];
  job_requirements: JDRequirement[];
  unknowns: string[];
  hard_constraint_status: "satisfied" | "unknown";
  recommended_action: string;
  analysis_mode: "deterministic" | "llm" | "fallback" | "mock";
  confidence_label: "strong" | "medium" | "limited" | "weak";
}

export type JobSearchItemStage = "recalled" | "filtered" | "analyzed" | "final";

export interface JobSearchCandidateSnapshot {
  title: string;
  company: string | null;
  location: string | null;
  source_provider: string;
  source_url: string | null;
  snippet: string | null;
  raw_description: string | null;
  discovery_query: string | null;
  discovery_rank: number | null;
  detail_status: string | null;
  provider_warnings: string[];
}

export interface JobSearchItem {
  job_search_item_id: string;
  job_search_run_id: string;
  stable_candidate_key: string;
  rank: number;
  stage: JobSearchItemStage;
  candidate: JobSearchCandidateSnapshot;
  result: JobSearchResult | null;
  created_at: string;
  updated_at: string;
}

export interface JobSearchItemListResponse {
  items: JobSearchItem[];
  total: number;
}

export interface JobSearchTraceStep {
  step_id: string;
  job_search_run_id: string;
  step_index: number;
  name: string;
  status: "pending" | "running" | "completed" | "failed";
  mode: "deterministic" | "llm" | "provider" | "fallback" | "mock";
  summary: string;
  fallback_reason: string | null;
  guardrails: string[];
  quality_warnings: string[];
  details: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
}

export interface JobSearchRun {
  job_search_run_id: string;
  session_id: string;
  confirmed_profile_id: string;
  resume_profile_id: string | null;
  query: string;
  locations: string[];
  target_roles: string[];
  keywords: string[];
  search_mode: "local_mock" | "live_search" | "browser_helper";
  llm_enabled: boolean;
  search_provider: string | null;
  selected_sources: string[];
  search_mission_id: string | null;
  search_mission_revision: number | null;
  mission_constraints: string[];
  mission_excluded_roles: string[];
  mission_ranking_priorities: string[];
  status: "pending" | "running" | "completed" | "failed";
  error_message: string | null;
  results: JobSearchResult[];
  created_at: string;
  updated_at: string;
}

export interface JobSearchRunResponse {
  job_search_run: JobSearchRun;
  profile_session: ProfileSession;
  steps: JobSearchTraceStep[];
}

export type JobSearchFeedbackType =
  | "relevant"
  | "irrelevant"
  | "duplicate"
  | "stale"
  | "insufficient_jd";

export interface JobSearchResultFeedback {
  feedback_id: string;
  user_id: string;
  job_search_run_id: string;
  job_result_id: string;
  confirmed_profile_id: string;
  resume_profile_id: string | null;
  source_provider: string | null;
  feedback_type: JobSearchFeedbackType;
  note: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobSearchResultFeedbackListResponse {
  items: JobSearchResultFeedback[];
}

export interface JobSearchIntent {
  role_titles: string[];
  role_families: string[];
  industry_domains: string[];
  evidence_skills: string[];
  generic_tools: string[];
  constraints: string[];
  negative_signals: string[];
  broad_queries: string[];
  domain_queries: string[];
  evidence_queries: string[];
  tool_queries: string[];
  mode: "deterministic" | "llm" | "fallback";
  fallback_reason: string | null;
  quality_warnings: string[];
}

export interface JobSearchPreview {
  session_id: string;
  confirmed_profile_id: string;
  search_mode: "local_mock" | "live_search";
  search_provider: string | null;
  llm_enabled: boolean;
  llm_provider: string | null;
  analysis_mode: "deterministic" | "llm";
  query: string;
  locations: string[];
  target_roles: string[];
  keywords: string[];
  provider_queries: string[];
  search_intent: JobSearchIntent | null;
  selected_sources: string[];
  search_source_kind: "mock" | "native_job_board" | "native_api" | "search_engine" | "direct_crawler" | "browser_helper" | "hybrid";
  search_source_notes: string[];
  recall_queries: string[];
  ranking_signals: string[];
  provider_search_terms: string[];
  provider_search_urls: string[];
  provider_query_count: number;
  estimated_provider_requests: number;
  estimated_candidate_pool_size: number;
  estimated_llm_planning_requests: number;
  estimated_llm_filtering_requests: number;
  estimated_llm_analysis_requests: number;
  estimated_total_llm_requests: number;
  query_strategy_notes: string[];
  search_signal_terms: string[];
  excluded_signals: string[];
  ranking_policy: string;
  planning_mode: "deterministic" | "llm" | "fallback";
  fallback_reason: string | null;
  quality_warnings: string[];
  search_mission_id: string | null;
  search_mission_revision: number | null;
  mission_constraints: string[];
  mission_excluded_roles: string[];
}

export type SearchMissionExplorationLevel = "focused" | "balanced" | "exploratory";

export interface SearchMissionClarificationAnswer {
  question: string;
  answer: string;
}

export interface SearchMissionInput {
  target_roles: string[];
  excluded_roles: string[];
  preferred_industries: string[];
  locations: string[];
  work_arrangements: string[];
  employment_types: string[];
  must_have: string[];
  nice_to_have: string[];
  ranking_priorities: string[];
  exploration_level: SearchMissionExplorationLevel;
  free_text: string | null;
  clarification_answers: SearchMissionClarificationAnswer[];
}

export interface SearchMissionInterpretation extends Omit<SearchMissionInput, "free_text" | "clarification_answers"> {
  adjacent_roles: string[];
  hard_constraints: string[];
  soft_preferences: string[];
  conflicts: string[];
  assumptions: string[];
  clarification_questions: string[];
}

export interface SearchMission {
  search_mission_id: string;
  user_id: string;
  session_id: string;
  confirmed_profile_id: string;
  status: "draft" | "review" | "confirmed";
  input: SearchMissionInput;
  mission: SearchMissionInterpretation;
  analysis_mode: "deterministic" | "llm" | "fallback";
  analysis_provider: string | null;
  fallback_reason: string | null;
  revision: number;
  created_at: string;
  updated_at: string;
  confirmed_at: string | null;
}

export interface JobSearchRunListResponse {
  items: JobSearchRun[];
}

export interface JobSearchTraceStepListResponse {
  items: JobSearchTraceStep[];
}

export interface LlmStatus {
  provider: string;
  configured: boolean;
  model: string | null;
  base_url: string | null;
  reason: string | null;
}

export type LlmProviderName = "deepseek" | "ollama" | "mock";

export interface CreateJobSearchRunPayload {
  session_id: string;
  query?: string | null;
  search_mode?: "local_mock" | "live_search";
  search_provider?: "mock" | "cuhksz_career" | "linkedin" | "remoteok" | "serper_web" | "browser_helper" | "multi_source";
  selected_sources?: Array<"cuhksz_career" | "linkedin" | "remoteok">;
  analysis_mode?: "deterministic" | "llm";
  llm_provider?: LlmProviderName | null;
  use_llm?: boolean;
  locations?: string[];
  target_roles?: string[];
  keywords?: string[];
  max_results?: number;
}

export interface BrowserHelperJobCandidate {
  title: string;
  company?: string | null;
  location?: string | null;
  source_url?: string | null;
  source_provider: string;
  snippet: string;
  raw_description?: string | null;
  discovery_query?: string | null;
  discovery_rank?: number | null;
  detail_status?: string | null;
  provider_warnings?: string[];
}

export interface CreateBrowserHelperJobSearchPayload {
  session_id: string;
  query?: string | null;
  helper_version?: string | null;
  platforms?: string[];
  selected_sources?: Array<"cuhksz_career" | "linkedin" | "remoteok">;
  analysis_mode?: "deterministic" | "llm";
  llm_provider?: LlmProviderName | null;
  use_llm?: boolean;
  locations?: string[];
  target_roles?: string[];
  keywords?: string[];
  max_results?: number;
  candidates: BrowserHelperJobCandidate[];
}

export interface UpdateProfileDraftPayload {
  summary?: string;
  target_roles?: string[];
  target_directions?: string[];
  core_skills?: string[];
  supporting_skills?: string[];
  search_keywords?: string[];
  preferred_locations?: string[];
  work_arrangements?: string[];
  strengths?: string[];
  risks?: string[];
  missing_info_questions?: string[];
}
