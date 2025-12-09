import React from "react";
import type { AgentStatus } from "../types/agent";

type Props = {
  agents: AgentStatus[];
  onAgentClick?: (agent: AgentStatus) => void;
};

function formatTime(value?: string) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

const statusStyles: Record<
  AgentStatus["status"],
  { badge: string; dot: string; label: string }
> = {
  idle: {
    badge: "bg-slate-700 text-slate-100",
    dot: "bg-slate-400",
    label: "Idle",
  },
  running: {
    badge: "bg-emerald-600 text-white",
    dot: "bg-emerald-400",
    label: "Running",
  },
  error: {
    badge: "bg-rose-600 text-white",
    dot: "bg-rose-400",
    label: "Error",
  },
};

export default function AgentStatusPanel({ agents, onAgentClick }: Props) {
  return (
    <section>
      <header className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wide">
          Agent Status
        </h2>
        <p className="text-xs text-slate-400">
          Realtime view of backend agents
        </p>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
        {agents.map((agent) => {
          const styles = statusStyles[agent.status];

          return (
            <button
              key={agent.id}
              type="button"
              onClick={() => onAgentClick?.(agent)}
              className="relative text-left rounded-md border border-slate-700 bg-slate-900/80 p-3 shadow-sm transition hover:border-slate-500 hover:bg-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500/70"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-sm font-semibold text-slate-100">
                    {agent.label}
                  </div>
                  <div className="mt-1 inline-flex items-center gap-1">
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${styles.badge}`}
                    >
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${styles.dot}`}
                      />
                      {styles.label}
                    </span>
                    {typeof agent.totalTasks === "number" && (
                      <span className="text-[11px] text-slate-400">
                        • {agent.totalTasks} tasks
                      </span>
                    )}
                  </div>
                </div>

                {agent.status === "running" && (
                  <div
                    aria-label="Agent running"
                    className="flex items-center justify-center"
                  >
                    <span className="relative flex h-3 w-3">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400/70" />
                      <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-400" />
                    </span>
                  </div>
                )}
              </div>

              {agent.currentTask && (
                <p className="mt-2 text-xs text-slate-300 line-clamp-2">
                  {agent.currentTask}
                </p>
              )}

              {agent.errorMessage && agent.status === "error" && (
                <p className="mt-2 rounded bg-rose-950/60 px-2 py-1 text-[11px] text-rose-300 border border-rose-700/60">
                  {agent.errorMessage}
                </p>
              )}

              <p className="mt-2 text-[11px] text-slate-500">
                Last updated: {formatTime(agent.lastUpdated)}
              </p>
            </button>
          );
        })}
      </div>
    </section>
  );
}
