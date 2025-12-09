export type AgentId =
  | "collector"
  | "analyzer"
  | "triage"
  | "remediation"
  | "orchestrator"
  | "reporter"
  | "learning";

export type AgentStatusState = "idle" | "running" | "error";

export interface AgentStatus {
  id: AgentId;
  label: string;
  status: AgentStatusState;
  currentTask?: string;
  lastUpdated?: string;
  totalTasks?: number;
  errorMessage?: string;
}

export interface AgentActivityEvent {
  id: string;
  timestamp: string;
  description: string;
  details?: string;
}
