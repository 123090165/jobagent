/**
 * 声明可复用简历画像库的列表、编辑和默认项契约。
 */
export interface ResumeProfile {
  resume_profile_id: string;
  user_id: string;
  source_session_id: string | null;
  source_confirmed_profile_id: string | null;
  name: string;
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
  profile: Record<string, unknown>;
  raw_resume_text: string | null;
  is_default: boolean;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ResumeProfileListResponse {
  items: ResumeProfile[];
}

export interface ResumeProfileUpdatePayload {
  name?: string | null;
  summary?: string | null;
  target_roles?: string[] | null;
  target_directions?: string[] | null;
  core_skills?: string[] | null;
  supporting_skills?: string[] | null;
  search_keywords?: string[] | null;
  preferred_locations?: string[] | null;
  work_arrangements?: string[] | null;
  strengths?: string[] | null;
  risks?: string[] | null;
  raw_resume_text?: string | null;
}
