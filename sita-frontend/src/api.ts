import axios from "axios";
import type { AgentId } from "./types/agent";

export const BACKEND = import.meta.env.VITE_BACKEND_URL ?? "https://sita-backend-310714690883.us-central1.run.app";

export function analyzeLog(log: string) {
  return axios.post(`${BACKEND}/analyze-log`, { logText: log });
}

export function fetchLogs() {
  return axios.get(`${BACKEND}/logs`);
}

export function connectToCloud() {
  return axios.post(`${BACKEND}/connect-gcp`);
}

export function disconnectFromCloud() {
  return axios.post(`${BACKEND}/disconnect-gcp`);
}

export function fetchAnalysisResults() {
  return axios.get(`${BACKEND}/analysis-results`);
}

export function deleteLog(id: string) {
  return axios.delete(`${BACKEND}/logs/${id}`);
}

export function deleteAnalysisResult(id: string) {
  return axios.delete(`${BACKEND}/analysis-results/${id}`);
}

// Temporary stub for remediation approval.
// The frontend expects this function (see AlertsTable), but the backend
// does not yet expose a remediation approval endpoint.
// This keeps the app compiling and running; when a real endpoint exists,
// update the implementation below to call it.
export async function approveRemediation(remediationId: string) {
  // eslint-disable-next-line no-console
  console.warn(
    "approveRemediation called with id, but no backend endpoint is implemented yet:",
    remediationId,
  );
  return Promise.resolve();
}

export type AgentActivitySummary = {
  status: "idle" | "running" | "error";
  lastUpdated: string;
  recentEvents: string[];
};

export type AgentsActivityResponse = Record<AgentId, AgentActivitySummary>;

export async function fetchAgentsActivity(): Promise<AgentsActivityResponse> {
  try {
    const res = await axios.get<AgentsActivityResponse>(`${BACKEND}/agents/activity`);
    return res.data ?? {};
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error("Failed to fetch agents activity", err);
    return {};
  }
}
