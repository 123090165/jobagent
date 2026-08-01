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
  platform_job_id: string | null;
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
  dimensions: Array<{
    dimension_id: string;
    label: string;
    state: "unresolved" | "supported" | "demonstrated" | "partial" | "knowledge_gap" | "missing" | "unknown";
    evidence: string[];
  }>;
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
  answer_kind?: "evidence_claim" | "partial_practice" | "knowledge_gap" | "explicit_absence" | "unclear" | null;
  value: PreparationExperienceLevel;
  label: string;
  description: string;
  evidence_transition: "supported" | "partial" | "unknown" | "missing";
  route: "ask_evidence" | "learning" | "capability_gap" | "clarify" | "next_skill";
  detail_policy: "required" | "optional" | "not_needed";
  follow_up_prompt: string | null;
  decision_dimension: string;
  state_effects: Array<{
    dimension_id: string;
    state: "unresolved" | "supported" | "demonstrated" | "partial" | "knowledge_gap" | "missing" | "unknown";
  }>;
  next_question_signal: string;
}

export interface PreparationQuestion {
  question_id: string;
  skill: string;
  prompt: string;
  why_asked: string;
  options: PreparationAnswerOption[];
  free_text_allowed: boolean;
  free_text_prompt: string;
  decision_objective: {
    dimension_id: string;
    uncertainty: string;
    why_now: string;
  } | null;
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
  input_mode?: "option_only" | "option_with_detail" | "free_text" | null;
  follow_up_count?: number;
  pending_prompt?: string | null;
  committed?: boolean;
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
  resource_urls: string[];
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

export type ApplicationStage =
  | "not_started"
  | "contacted"
  | "recruiter_replied"
  | "resume_requested"
  | "resume_ready"
  | "resume_sent"
  | "interview"
  | "closed";

export type ApplicationNextAction =
  | "generate_greeting"
  | "review_greeting"
  | "wait_for_reply"
  | "review_reply"
  | "generate_resume"
  | "review_resume"
  | "send_resume"
  | "prepare_interview"
  | "none";

export interface JobApplication {
  application_id: string;
  user_id: string;
  saved_job_id: string;
  stage: ApplicationStage;
  next_action: ApplicationNextAction;
  last_activity_at: string;
  contacted_at: string | null;
  replied_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationEvent {
  event_id: string;
  application_id: string;
  user_id: string;
  event_type: string;
  source: "web" | "browser_helper" | "system" | "user";
  detail: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface CommunicationDraft {
  draft_id: string;
  application_id: string | null;
  browser_capture_id: string | null;
  generated_content: string;
  approved_content: string | null;
  status: "generated" | "approved" | "sent" | "failed" | "dismissed";
  evidence_used: string[];
  avoid_claims: string[];
  analysis_provider: string | null;
  created_at: string;
  updated_at: string;
  sent_at: string | null;
}

export interface TailoredResumeVersion {
  tailored_resume_id: string;
  user_id: string;
  saved_job_id: string;
  resume_profile_id: string;
  version: number;
  content: string;
  validation: {
    is_valid: boolean;
    issues: string[];
    warnings: string[];
  };
  status: "needs_review" | "approved";
  analysis_provider: string | null;
  created_at: string;
  updated_at: string;
  approved_at: string | null;
}

export interface SavedJobWorkspace {
  job: SavedJob;
  application: JobApplication | null;
  latest_analysis: SavedJobAnalysis | null;
  communication_draft: CommunicationDraft | null;
  tailored_resume: TailoredResumeVersion | null;
  allowed_stage_transitions: ApplicationStage[];
  events: ApplicationEvent[];
}

export interface SavedJobCreatePayload {
  source_provider?: string | null;
  platform_job_id?: string | null;
  source_url?: string | null;
  title: string;
  company?: string | null;
  location?: string | null;
  salary?: string | null;
  employment_type?: string | null;
  raw_jd_text: string;
  structured_jd?: Record<string, unknown>;
  tags?: string[];
  notes?: string | null;
}

export interface SavedJobUpdatePayload {
  notes?: string | null;
  tags?: string[] | null;
}

export interface SavedJobFromSearchResultPayload {
  job_search_run_id: string;
  job_result_id: string;
  resume_profile_id?: string | null;
  tags?: string[];
  notes?: string | null;
}
