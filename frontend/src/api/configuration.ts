import { api } from "@/api/http";

export type RuleType = "AI语义审查" | "条款完整性" | "合规校验" | "金额与支付";
export type RiskLevel = "high" | "medium" | "low";

export interface ReviewRule {
  id: number;
  rule_id: string;
  rule_name: string;
  business_type: string;
  rule_type: RuleType;
  risk_level: RiskLevel;
  review_requirement: string;
  description: string | null;
  status: boolean;
  update_time: string;
}

export interface RulePayload {
  rule_name: string;
  business_type: "合同审查";
  rule_type: RuleType;
  risk_level: RiskLevel;
  review_requirement: string;
  description: string | null;
  status: boolean;
}

export interface ReviewScene {
  id: number;
  scene_name: string;
  business_type: string;
  description: string | null;
  system_prompt: string;
  status: boolean;
  display_order: number;
  update_time: string;
  rules: Array<Pick<ReviewRule, "id" | "rule_id" | "rule_name" | "rule_type" | "risk_level" | "status">>;
  rule_count: number;
  active_rule_count: number;
}

export interface AvailableScene {
  id: number;
  scene_name: string;
  description: string | null;
}

export interface ScenePayload {
  scene_name: string;
  business_type: "合同审查";
  description: string | null;
  system_prompt: string;
  rule_ids: number[];
  status: boolean;
  display_order: number;
}

export async function listRules(params: Record<string, string | boolean | undefined> = {}) {
  const { data } = await api.get<ReviewRule[]>("/rules", { params });
  return data;
}

export async function createRule(payload: RulePayload) {
  const { data } = await api.post<ReviewRule>("/rules", payload);
  return data;
}

export async function updateRule(id: number, payload: RulePayload) {
  const { data } = await api.put<ReviewRule>(`/rules/${id}`, payload);
  return data;
}

export async function setRuleStatus(id: number, status: boolean) {
  const { data } = await api.patch<ReviewRule>(`/rules/${id}/status`, { status });
  return data;
}

export async function deleteRule(id: number) {
  await api.delete(`/rules/${id}`);
}

export async function listScenes(params: Record<string, string | boolean | undefined> = {}) {
  const { data } = await api.get<ReviewScene[]>("/scenes", { params });
  return data;
}

export async function listAvailableScenes() {
  const { data } = await api.get<AvailableScene[]>("/scenes/available");
  return data;
}

export async function createScene(payload: ScenePayload) {
  const { data } = await api.post<ReviewScene>("/scenes", payload);
  return data;
}

export async function updateScene(id: number, payload: ScenePayload) {
  const { data } = await api.put<ReviewScene>(`/scenes/${id}`, payload);
  return data;
}

export async function setSceneStatus(id: number, status: boolean) {
  const { data } = await api.patch<ReviewScene>(`/scenes/${id}/status`, { status });
  return data;
}

export async function deleteScene(id: number) {
  await api.delete(`/scenes/${id}`);
}
