export type SavedJobStatus =
  | "saved"
  | "interested"
  | "applied"
  | "interviewing"
  | "rejected"
  | "closed"
  | "archived";

export interface SavedJobAnalysis {
  saved_job_analysis_id: string;
  saved_job_id: string;
  user_id: string;
  resume_profile_id: string | null;
  source_job_search_run_id: string | null;
  source_job_result_id: string | null;
  match_score: number | null;
  confidence_label: string | null;
  recommendation: string | null;
  matched_strengths: string[];
  critical_gaps: string[];
  resume_actions: string[];
  interview_questions: string[];
  analysis: Record<string, unknown>;
  analysis_mode: string;
  created_at: string;
}

export interface SavedJob {
  saved_job_id: string;
  user_id: string;
  source_provider: string | null;
  source_url: string | null;
  normalized_source_key: string | null;
  title: string;
  company: string | null;
  location: string | null;
  salary: string | null;
  employment_type: string | null;
  raw_jd_text: string;
  structured_jd: Record<string, unknown>;
  tags: string[];
  status: SavedJobStatus;
  notes: string | null;
  first_seen_at: string;
  saved_at: string;
  updated_at: string;
  archived_at: string | null;
  latest_analysis: SavedJobAnalysis | null;
}

export interface SavedJobListResponse {
  items: SavedJob[];
}

export interface SavedJobAnalysisListResponse {
  items: SavedJobAnalysis[];
}

export interface JobBriefContent {
  decision_summary: string;
  fit_signals: string[];
  evidence_gaps: string[];
  resume_actions: string[];
  interview_focus: string[];
  next_actions: string[];
}

export interface JobBrief {
  job_brief_id: string;
  saved_job_id: string;
  user_id: string;
  resume_profile_id: string | null;
  source_analysis_id: string | null;
  version: number;
  content: JobBriefContent;
  analysis_mode: string;
  analysis_provider: string | null;
  fallback_reason: string | null;
  created_at: string;
}

export interface JobBriefListResponse {
  items: JobBrief[];
}

export interface JobBriefGeneratePayload {
  resume_profile_id?: string | null;
  llm_provider?: string | null;
}

export interface PreparationSkillGap {
  skill: string;
  importance: "high" | "medium" | "low";
  evidence_status: "supported" | "partial" | "unknown" | "missing";
  skill_type: "knowledge" | "experience";
  jd_evidence: string;
  profile_evidence: string[];
  rationale: string;
  evidence_origin: "resume" | "user_reported" | "none";
}

export type PreparationExperienceLevel =
  | "work_experience"
  | "project_experience"
  | "practice_only"
  | "conceptual_only"
  | "no_experience"
  | "uncertain";

export interface PreparationAnswerOption {
  option_id: string;
  value: PreparationExperienceLevel;
  label: string;
  description: string;
  evidence_transition: "supported" | "partial" | "unknown" | "missing";
  route: "ask_evidence" | "learning" | "capability_gap" | "clarify" | "next_skill";
  detail_policy: "required" | "optional" | "not_needed";
  follow_up_prompt: string | null;
}

export interface PreparationQuestion {
  question_id: string;
  skill: string;
  prompt: string;
  why_asked: string;
  options: PreparationAnswerOption[];
  free_text_allowed: boolean;
  free_text_prompt: string;
}

export interface PreparationAnswer {
  question_id: string;
  response_mode: "option" | "free_text";
  selected_option_id?: string | null;
  free_text?: string | null;
  experience_level?: PreparationExperienceLevel | null;
  detail?: string | null;
  detail_quality?: "not_provided" | "specific" | "vague";
  evidence_transition?: "supported" | "partial" | "unknown" | "missing" | null;
  route?: "ask_evidence" | "learning" | "capability_gap" | "clarify" | "next_skill" | null;
  resolution_source?: "option" | "llm_classified" | "fallback_uncertain" | "legacy" | null;
}

export interface LearningResource {
  topic: string;
  title: string;
  url: string;
  source: string;
  level: string;
  reason: string;
}

export interface PreparationRecommendation {
  title: string;
  action: string;
  action_type: "learning" | "experience_inventory" | "interview_story" | "capability_gap";
  skill: string | null;
  evidence_basis: string[];
}

export interface PreparationGenerationStage {
  mode: "deterministic" | "llm" | "fallback";
  provider: string | null;
  prompt_version: string;
  attempts: number;
  fallback_reason: string | null;
  attempt_errors: string[];
}

export interface InterviewPreparationWorkspace {
  preparation_id: string;
  saved_job_id: string;
  user_id: string;
  resume_profile_id: string | null;
  source_analysis_id: string | null;
  status: "questions_ready" | "paused" | "completed" | "stopped";
  skill_gaps: PreparationSkillGap[];
  questions: PreparationQuestion[];
  answers: PreparationAnswer[];
  learning_resources: LearningResource[];
  recommendations: PreparationRecommendation[];
  analysis_mode: string;
  analysis_provider: string | null;
  fallback_reason: string | null;
  question_generation: PreparationGenerationStage | null;
  recommendation_generation: PreparationGenerationStage | null;
  resource_mode: string;
  resource_warning: string | null;
  created_at: string;
  updated_at: string;
}

export interface SavedJobStatusEvent {
  saved_job_status_event_id: string;
  saved_job_id: string;
  user_id: string;
  from_status: SavedJobStatus | null;
  to_status: SavedJobStatus;
  reason: string | null;
  changed_at: string;
}

export interface SavedJobStatusEventListResponse {
  items: SavedJobStatusEvent[];
}

export interface SavedJobCreatePayload {
  source_provider?: string | null;
  source_url?: string | null;
  title: string;
  company?: string | null;
  location?: string | null;
  salary?: string | null;
  employment_type?: string | null;
  raw_jd_text: string;
  structured_jd?: Record<string, unknown>;
  tags?: string[];
  status?: SavedJobStatus;
  notes?: string | null;
}

export interface SavedJobUpdatePayload {
  status?: SavedJobStatus | null;
  notes?: string | null;
  tags?: string[] | null;
}

export interface SavedJobFromSearchResultPayload {
  job_search_run_id: string;
  job_result_id: string;
  resume_profile_id?: string | null;
  tags?: string[];
  status?: SavedJobStatus;
  notes?: string | null;
}
