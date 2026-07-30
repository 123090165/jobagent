/**
 * 读取个人知识库及同步队列状态，供状态页判断索引是否可用、是否存在失败任务。
 */
import { client } from "./client";

export interface RagIndexEvent {
  event_id: string;
  resource_type: "resume_profile" | "saved_job";
  resource_id: string;
  attempt_count: number;
  last_error_code: string | null;
  last_error_message: string | null;
  created_at: string;
}

export interface RagStatus {
  sync_enabled: boolean;
  mcp_configured: boolean;
  reachable: boolean;
  server_name: string | null;
  server_version: string | null;
  reason: string | null;
  overview: {
    resource_count: number;
    ready_count: number;
    pending_resource_count: number;
    failed_resource_count: number;
    deleted_count: number;
    pending_event_count: number;
    processing_event_count: number;
    failed_event_count: number;
    oldest_pending_at: string | null;
    last_synced_at: string | null;
    recent_failures: RagIndexEvent[];
  };
}

export async function getRagStatus(): Promise<RagStatus> {
  const response = await client.get<RagStatus>("/api/v1/rag/status");
  return response.data;
}
