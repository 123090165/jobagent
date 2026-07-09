export interface UserAccount {
  user_id: string;
  username: string;
  display_name: string | null;
  created_at: string;
  updated_at: string;
  disabled_at: string | null;
}

export interface AuthLoginPayload {
  username: string;
  password: string;
}

export interface AuthRegisterPayload extends AuthLoginPayload {
  display_name?: string | null;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  user: UserAccount;
}

export interface AuthMeResponse {
  user: UserAccount;
}
