export type ProfileSessionStatus = "active" | "completed" | "archived";

export type ProfileSessionStep =
  | "resume_intake"
  | "resume_review"
  | "profile_draft"
  | "profile_confirmed"
  | "job_search_ready";

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
