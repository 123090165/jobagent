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
