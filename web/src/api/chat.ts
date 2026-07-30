/**
 * 封装Assistant 会话、消息与上下文的类型化 HTTP 请求；这里只处理传输，不复制后端规则。
 */
import { client } from "./client";
import type {
  ChatConversation,
  ChatConversationCreatePayload,
  ChatConversationListResponse,
  ChatConversationUpdatePayload,
  ChatContextCatalog,
  ChatMemoryStatus,
  ChatTurn,
  ChatTurnListResponse
} from "../types/chat";

export async function createChatConversation(
  payload: ChatConversationCreatePayload = {}
): Promise<ChatConversation> {
  const response = await client.post<ChatConversation>("/api/v1/chat/conversations", payload);
  return response.data;
}

export async function listChatConversations(): Promise<ChatConversationListResponse> {
  const response = await client.get<ChatConversationListResponse>("/api/v1/chat/conversations");
  return response.data;
}

export async function updateChatConversation(
  conversationId: string,
  payload: ChatConversationUpdatePayload
): Promise<ChatConversation> {
  const response = await client.patch<ChatConversation>(
    `/api/v1/chat/conversations/${conversationId}`,
    payload
  );
  return response.data;
}

export async function getChatContextCatalog(): Promise<ChatContextCatalog> {
  const response = await client.get<ChatContextCatalog>("/api/v1/chat/context-catalog");
  return response.data;
}

export async function listChatTurns(conversationId: string): Promise<ChatTurnListResponse> {
  const response = await client.get<ChatTurnListResponse>(
    `/api/v1/chat/conversations/${conversationId}/turns`
  );
  return response.data;
}

export async function getChatMemoryStatus(conversationId: string): Promise<ChatMemoryStatus> {
  const response = await client.get<ChatMemoryStatus>(
    `/api/v1/chat/conversations/${conversationId}/memory`
  );
  return response.data;
}

export async function createChatTurn(
  conversationId: string,
  question: string,
  retryOfTurnId?: string
): Promise<ChatTurn> {
  const clientTurnId = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
  const response = await client.post<ChatTurn>(
    `/api/v1/chat/conversations/${conversationId}/turns`,
    {
      client_turn_id: clientTurnId,
      question,
      ...(retryOfTurnId ? { retry_of_turn_id: retryOfTurnId } : {})
    }
  );
  return response.data;
}

export async function deleteChatTurn(conversationId: string, turnId: string): Promise<void> {
  await client.delete(`/api/v1/chat/conversations/${conversationId}/turns/${turnId}`);
}

export async function clearChatMemory(conversationId: string): Promise<void> {
  await client.delete(`/api/v1/chat/conversations/${conversationId}/memory`);
}

export async function deleteChatConversation(conversationId: string): Promise<void> {
  await client.delete(`/api/v1/chat/conversations/${conversationId}`);
}
