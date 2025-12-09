import React, { useState } from "react";
import { approveRemediation } from "../api";

export type AgentTraceEntry = {
  message?: string;
  status?: string;
  task_id?: string;
  timestamp?: string;
};

export type AlertItem = {
  id?: string;
  time?: string;
  timestamp?: string;
  category?: string;
  severity?: string;
  summary?: string;
  log?: string;
  plan_trace?: AgentTraceEntry[];
  remediation_id?: string;
  agent_confidence?: number;
  agent_rationale?: string;
  // allow additional fields from backend without losing type-safety completely
  [key: string]: unknown;
};

function sevClass(sev?: string) {
  if (!sev) return "bg-gray-500/30 text-gray-100";
  const s = sev.toLowerCase();
  if (s.includes("error") || s.includes("high")) return "bg-red-600 text-white";
  if (s.includes("warn") || s.includes("medium")) return "bg-amber-500 text-black";
  if (s.includes("info") || s.includes("informational")) return "bg-blue-600 text-white";
  return "bg-gray-600 text-white";
}

const PAGE_SIZE = 10;

export default function AlertsTable({ alerts }: { alerts: AlertItem[] }) {
  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({});
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [page, setPage] = useState(0);

  const pageCount = Math.max(1, Math.ceil((alerts?.length || 0) / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount - 1);
  const startIndex = currentPage * PAGE_SIZE;
  const endIndex = Math.min(startIndex + PAGE_SIZE, alerts.length);
  const visibleAlerts = alerts.slice(startIndex, endIndex);

  const toggleExpanded = (rowKey: string) => {
    setExpandedIds((prev) => ({ ...prev, [rowKey]: !prev[rowKey] }));
  };

  const goPrev = () => {
    setPage((p) => Math.max(0, p - 1));
  };

  const goNext = () => {
    setPage((p) => Math.min(pageCount - 1, p + 1));
  };

  const handleApprove = async (alert: AlertItem) => {
    const remediationId = (alert.remediation_id as string) || "";
    if (!remediationId) return;
    try {
      setApprovingId(remediationId);
      await approveRemediation(remediationId);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error("Failed to approve remediation", e);
    } finally {
      setApprovingId(null);
    }
  };

  return (
    <div className="overflow-auto rounded-md shadow bg-slate-900 text-slate-100">
      <table className="min-w-full divide-y divide-slate-700">
        <thead className="bg-slate-800">
          <tr>
            <th className="px-3 py-2 text-left">Time</th>
            <th className="px-3 py-2 text-left">Category</th>
            <th className="px-3 py-2 text-left">Severity</th>
            <th className="px-3 py-2 text-left">Agent confidence</th>
            <th className="px-3 py-2 text-left">Summary</th>
            <th className="px-3 py-2 text-left">Agent Trace</th>
          </tr>
        </thead>
        <tbody>
          {visibleAlerts && visibleAlerts.length ? (
            visibleAlerts.map((a, i) => {
              const rowKey = String(a.id ?? startIndex + i);
              const hasTrace = Array.isArray(a.plan_trace) && a.plan_trace.length > 0;
              const awaitingApproval = hasTrace && (a.plan_trace as AgentTraceEntry[]).some((t) => (t.status || "").toLowerCase() === "awaiting_approval");
              const confidence = typeof a.agent_confidence === "number" ? a.agent_confidence : undefined;
              const rationale = (a.agent_rationale as string) || "";

              return (
                <React.Fragment key={rowKey}>
                  <tr className="odd:bg-slate-900 even:bg-slate-800">
                    <td className="px-3 py-2 align-top">
                      {a.time ?? a.timestamp ?? "-"}
                    </td>
                    <td className="px-3 py-2 align-top">{a.category ?? "-"}</td>
                    <td className="px-3 py-2 align-top">
                      <span className={`px-2 py-1 rounded text-xs ${sevClass(a.severity)}`}>
                        {a.severity ?? "-"}
                      </span>
                    </td>
                    <td className="px-3 py-2 align-top">
                      {confidence !== undefined ? (
                        <span
                          className="inline-flex items-center px-2 py-1 rounded text-xs bg-slate-700 text-slate-50"
                          title={rationale || "LLM rationale not available"}
                        >
                          {Math.round(confidence)}%
                        </span>
                      ) : (
                        <span className="text-xs text-slate-500">n/a</span>
                      )}
                    </td>
                    <td className="px-3 py-2 align-top max-w-xl">
                      {a.summary ?? a.log ?? "-"}
                    </td>
                    <td className="px-3 py-2 align-top">
                      {hasTrace ? (
                        <button
                          type="button"
                          className="text-xs px-2 py-1 rounded bg-slate-700 hover:bg-slate-600"
                          onClick={() => toggleExpanded(rowKey)}
                        >
                          {expandedIds[rowKey] ? "Hide" : "Show"} trace
                        </button>
                      ) : (
                        <span className="text-xs text-slate-500">—</span>
                      )}
                    </td>
                  </tr>
                  {hasTrace && expandedIds[rowKey] && (
                    <tr className="bg-slate-950/60">
                      <td className="px-3 pb-3" colSpan={6}>
                        <div className="border border-slate-700 rounded p-3 space-y-2 text-xs">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-slate-200">Agent Trace</span>
                            {awaitingApproval && a.remediation_id && (
                              <button
                                type="button"
                                className="text-xs px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 disabled:cursor-not-allowed"
                                onClick={() => handleApprove(a)}
                                disabled={approvingId === a.remediation_id}
                              >
                                {approvingId === a.remediation_id ? "Approving..." : "Approve"}
                              </button>
                            )}
                          </div>
                          <ol className="mt-2 space-y-1 list-decimal list-inside">
                            {(a.plan_trace as AgentTraceEntry[]).map((step, idx) => {
                              const status = (step.status || "").toLowerCase();
                              let badgeClass = "bg-slate-700";
                              if (status === "succeeded" || status === "success") badgeClass = "bg-emerald-600";
                              else if (status === "failed" || status === "error") badgeClass = "bg-rose-600";
                              else if (status === "awaiting_approval") badgeClass = "bg-amber-500 text-black";

                              return (
                                <li key={step.task_id || idx} className="flex items-start gap-2">
                                  <span className="flex-1 text-slate-200">
                                    {step.message || "Step"} {step.status ? `(${step.status})` : ""}
                                  </span>
                                  {step.status && (
                                    <span className={`px-2 py-0.5 rounded text-[10px] uppercase tracking-wide ${badgeClass}`}>
                                      {step.status}
                                    </span>
                                  )}
                                </li>
                              );
                            })}
                          </ol>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })
          ) : (
            <tr>
              <td className="px-3 py-6 text-center" colSpan={6}>
                No alerts yet
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {alerts && alerts.length > PAGE_SIZE && (
        <div className="flex items-center justify-between px-3 py-2 text-xs text-slate-300 border-t border-slate-800 bg-slate-900/80">
          <div>
            Showing <span className="font-mono">{startIndex + 1}</span>–
            <span className="font-mono">{endIndex}</span> of
            <span className="font-mono"> {alerts.length}</span>
          </div>
          <div className="inline-flex items-center gap-2">
            <button
              type="button"
              onClick={goPrev}
              disabled={currentPage === 0}
              className="px-2 py-1 rounded border border-slate-600 bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-700"
            >
              Prev
            </button>
            <span>
              Page <span className="font-mono">{currentPage + 1}</span> / {pageCount}
            </span>
            <button
              type="button"
              onClick={goNext}
              disabled={currentPage >= pageCount - 1}
              className="px-2 py-1 rounded border border-slate-600 bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-700"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
