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
  recommended_action: string;
  analysis_mode: "deterministic" | "llm" | "fallback" | "mock";
  confidence_label: "strong" | "medium" | "limited" | "weak";
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
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
}

export interface JobSearchRun {
  job_search_run_id: string;
  session_id: string;
  confirmed_profile_id: string;
  query: string;
  locations: string[];
  target_roles: string[];
  keywords: string[];
  search_mode: "local_mock" | "live_search";
  llm_enabled: boolean;
  search_provider: string | null;
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

export interface JobSearchPreview {
  session_id: string;
  confirmed_profile_id: string;
  search_mode: "local_mock" | "live_search";
  search_provider: string | null;
  llm_enabled: boolean;
  llm_provider: string | null;
  query: string;
  locations: string[];
  target_roles: string[];
  keywords: string[];
  provider_queries: string[];
  provider_search_terms: string[];
  provider_search_urls: string[];
  search_signal_terms: string[];
  excluded_signals: string[];
  ranking_policy: string;
  planning_mode: "deterministic" | "llm" | "fallback";
  fallback_reason: string | null;
  quality_warnings: string[];
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

export interface JobSearchProviderStatus {
  provider: "mock" | "cuhksz_career" | string;
  configured: boolean;
  available_providers: string[];
  reason: string | null;
  base_url: string | null;
  search_url: string | null;
  allowlisted_domains: string[];
}

export interface CreateJobSearchRunPayload {
  session_id: string;
  query?: string | null;
  search_mode?: "local_mock" | "live_search";
  search_provider?: "mock" | "cuhksz_career";
  use_llm?: boolean;
  locations?: string[];
  target_roles?: string[];
  keywords?: string[];
  max_results?: number;
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
