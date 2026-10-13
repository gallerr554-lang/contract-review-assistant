import { api } from "./http.ts";

export { apiErrorMessage } from "./http.ts";

export type ReviewStatus = "PROCESSING" | "SUCCESS" | "FAILED";

export interface ReviewTask {
  id: number;
  task_no: string;
  contract_name: string;
  scene_name: string;
  scale: string;
  position: string;
  status: ReviewStatus;
  progress: number;
  current_step: number;
  current_message: string;
  error_message: string | null;
  create_time: string;
}

export interface ReviewRisk {
  id: number;
  risk_name: string;
  risk_level: "high" | "medium" | "low";
  rule_id: string;
  rule_name: string;
  original_text: string | null;
  source: string | null;
  locatable: boolean;
  description: string;
  suggestion: string;
  feedback_submitted: boolean;
  page_number: number | null;
  source_file_id: string | null;
  block_id: string | null;
  start_offset: number | null;
  end_offset: number | null;
  anchor_text: string | null;
  anchor_hash: string | null;
  location_spans: RiskLocationSpan[];
}

export interface RiskLocationSpan {
  source_file_id: string;
  page_number: number;
  block_id: string;
  start_offset: number;
  end_offset: number;
  anchor_text: string;
  anchor_hash: string;
}

export interface DocumentMeta {
  file_id: string;
  file_name: string;
  file_extension: string;
  mime_type: string;
  page_count: number;
  ocr_used: boolean;
  ocr_status: "not_required" | "success" | "partial" | "failed" | "unavailable";
  ocr_message: string | null;
  text_source: "native" | "ocr" | "mixed" | "unavailable";
  preview_available: boolean;
}

export interface DocumentBlock {
  block_id: string;
  type: "paragraph" | "table";
  text: string;
  style?: string;
  rows?: string[][];
}

export interface DocumentPage {
  file_id: string;
  page_number: number;
  page_count: number;
  text: string;
  blocks: DocumentBlock[];
  ocr_used: boolean;
  text_source: "native" | "ocr" | "unavailable";
  risk_ids: number[];
}

export interface ReviewResult {
  task: ReviewTask;
  summary: string;
  document: DocumentMeta;
  documents: DocumentMeta[];
  statistics: { total: number; high: number; medium: number; low: number };
  risks: ReviewRisk[];
}

export interface ReviewHistoryItem {
  id: number;
  task_no: string;
  contract_name: string;
  scene_name: string;
  scale: string;
  position: string;
  status: ReviewStatus;
  risk_total: number;
  high_risk_count: number;
  medium_risk_count: number;
  low_risk_count: number;
  error_message: string | null;
  create_time: string;
}

export interface ReviewHistoryResponse {
  items: ReviewHistoryItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface RiskFeedback {
  id: number;
  task_id: number;
  risk_id: number;
  rule_id: string;
  content: string;
  create_time: string;
}

export async function uploadContract(mainFile: File, attachments: File[]) {
  const formData = new FormData();
  formData.append("main_file", mainFile);
  attachments.forEach((file) => formData.append("attachments", file));
  const { data } = await api.post<{ upload_id: string; main_file: DocumentMeta & { character_count: number }; attachments: Array<DocumentMeta & { character_count: number }> }>("/contracts/upload", formData);
  return data;
}

export async function getDocumentPage(taskId: number, fileId: string, pageNumber: number) {
  const { data } = await api.get<DocumentPage>(`/review/${taskId}/documents/${encodeURIComponent(fileId)}/pages/${pageNumber}`);
  return data;
}

export async function getDocumentPageImage(taskId: number, fileId: string, pageNumber: number) {
  const { data } = await api.get<Blob>(`/review/${taskId}/documents/${encodeURIComponent(fileId)}/pages/${pageNumber}/image`, { responseType: "blob" });
  return data;
}

export async function downloadMarkedDocument(taskId: number, format: "original" | "pdf" = "original") {
  const response = await api.get<Blob>(`/review/${taskId}/download`, {
    params: { format },
    responseType: "blob"
  });
  return {
    blob: response.data,
    disposition: String(response.headers["content-disposition"] || ""),
    contentType: String(response.headers["content-type"] || response.data.type || "")
  };
}

export async function createReview(
  payload: { upload_id: string; scene_id: number; scale: string; position: string },
  idempotencyKey: string
) {
  const { data } = await api.post<ReviewTask>("/review/create", payload, {
    headers: { "Idempotency-Key": idempotencyKey }
  });
  return data;
}

export async function getReviewStatus(taskId: number) {
  const { data } = await api.get<ReviewTask>(`/review/${taskId}/status`);
  return data;
}

export async function getReviewResult(taskId: number) {
  const { data } = await api.get<ReviewResult>(`/review/${taskId}/result`);
  return data;
}

export async function retryReview(taskId: number) {
  const { data } = await api.post<ReviewTask>(`/review/${taskId}/retry`);
  return data;
}

export async function listReviewHistory(params: {
  keyword?: string;
  status?: ReviewStatus;
  page?: number;
  page_size?: number;
}) {
  const { data } = await api.get<ReviewHistoryResponse>("/review/history", { params });
  return data;
}

export async function submitRiskFeedback(taskId: number, riskId: number, content: string) {
  const { data } = await api.post<RiskFeedback>(`/review/${taskId}/risks/${riskId}/feedback`, { content });
  return data;
}
