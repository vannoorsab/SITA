import React from "react";
import type { AgentStatus } from "../types/agent";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  agent: AgentStatus | null;
  recentEvents: string[];
};

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

function formatTime(value?: string) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString();
}

function formatEventTime(value: string) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function AgentDetailsModal({ isOpen, onClose, agent, recentEvents }: Props) {
  if (!isOpen || !agent) return null;

  const styles = statusStyles[agent.status];

  const handleOverlayClick = () => {
    onClose();
  };

  const handleCardClick: React.MouseEventHandler<HTMLDivElement> = (e) => {
    e.stopPropagation();
  };

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 px-4"
      onClick={handleOverlayClick}
    >
      <div
        className="w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-900 shadow-lg p-6 relative"
        onClick={handleCardClick}
      >
        <header className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-50 flex items-center gap-2">
              {agent.label}
            </h2>
            <p className="mt-1 text-xs text-slate-400">Agent ID: {agent.id}</p>
          </div>

          <div className="flex items-start gap-3">
            <span
              className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium ${styles.badge}`}
            >
              <span className={`h-2 w-2 rounded-full ${styles.dot}`} />
              {styles.label}
            </span>
            <button
              type="button"
              onClick={onClose}
              className="ml-1 inline-flex h-7 w-7 items-center justify-center rounded-full border border-slate-600 text-slate-300 hover:bg-slate-800 hover:text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/70"
              aria-label="Close agent details"
            >
              <span className="text-sm">×</span>
            </button>
          </div>
        </header>

        <div className="mb-4 text-xs text-slate-400">
          <p>
            Last updated: <span className="text-slate-200">{formatTime(agent.lastUpdated)}</span>
          </p>
        </div>

        <section className="mt-2">
          <h3 className="text-sm font-semibold text-slate-100 mb-2">Recent activity</h3>

          {recentEvents.length === 0 ? (
            <p className="text-sm text-slate-400">No recent activity for this agent yet.</p>
          ) : (
            <ul className="mt-1 space-y-2 max-h-72 overflow-y-auto pr-1 text-sm text-slate-100">
              {recentEvents.map((msg, idx) => (
                <li
                  key={`${agent.id}-${idx}`}
                  className="rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2"
                >
                  {msg}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
