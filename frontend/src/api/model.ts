import { api } from "@/api/http";

export type ModelProvider = "openai" | "deepseek" | "qwen";

export interface ModelConfig {
  id: number;
  provider: ModelProvider;
  model_name: string;
  api_base: string | null;
  api_key_masked: string;
  api_key_configured: boolean;
  api_key_source: "encrypted" | "environment" | "missing";
  temperature: number;
  max_tokens: number;
  status: boolean;
  create_time: string;
  update_time: string;
}

export interface ModelConfigPayload {
  provider: ModelProvider;
  model_name: string;
  api_base: string;
  api_key?: string;
  temperature: number;
  max_tokens: number;
  status: boolean;
}

export interface ModelConnectionResult {
  provider: ModelProvider;
  model_name: string;
  api_base: string;
  success: boolean;
  http_status: number | null;
  message: string;
}

export async function listModelConfigs(params: Record<string, string | boolean | undefined> = {}) {
  const { data } = await api.get<ModelConfig[]>("/models", { params });
  return data;
}

export async function createModelConfig(payload: ModelConfigPayload & { api_key: string }) {
  const { data } = await api.post<ModelConfig>("/models", payload);
  return data;
}

export async function updateModelConfig(id: number, payload: ModelConfigPayload) {
  const { data } = await api.put<ModelConfig>(`/models/${id}`, payload);
  return data;
}

export async function setModelConfigStatus(id: number, status: boolean) {
  const { data } = await api.patch<ModelConfig>(`/models/${id}/status`, { status });
  return data;
}

export async function testModelConnection(id: number) {
  const { data } = await api.post<ModelConnectionResult>(`/models/${id}/test`);
  return data;
}
