import { api } from "@/api/http";
import type { AuthUser } from "@/stores/app";

export interface CaptchaPayload {
  captcha_id: string;
  image_data: string;
  expires_at: string;
}

export interface AuthPayload {
  email: string;
  password: string;
  captcha_id: string;
  captcha_code: string;
}

export interface AuthResult {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  user: AuthUser;
}

export async function getCaptcha() {
  const { data } = await api.get<CaptchaPayload>("/auth/captcha");
  return data;
}

export async function login(payload: AuthPayload) {
  const { data } = await api.post<AuthResult>("/auth/login", payload);
  return data;
}

export async function register(payload: AuthPayload) {
  const { data } = await api.post<AuthResult>("/auth/register", payload);
  return data;
}

export async function logout() {
  await api.post("/auth/logout");
}

export async function getCurrentUser() {
  const { data } = await api.get<AuthUser>("/auth/me");
  return data;
}
