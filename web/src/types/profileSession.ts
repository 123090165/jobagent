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
  created_at: string;
  updated_at: string;
}

export interface ParsedResumeReviewResponse {
  parsed_review: ParsedResumeReview;
  profile_session: ProfileSession;
}
