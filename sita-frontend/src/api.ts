import axios from "axios";

export const BACKEND = import.meta.env.VITE_BACKEND_URL ?? "https://sita-backend-310714690883.us-central1.run.app";

export function analyzeLog(log: string) {
  return axios.post(`${BACKEND}/analyze-log`, { logText: log });
}

export function fetchLogs() {
  return axios.get(`${BACKEND}/logs`);
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