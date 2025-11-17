import type { AnalysisResult } from "../types";

export default function LogsTable({ items }: { items: AnalysisResult[] }) {
  return (
    <div className="space-y-3">
      {items.length === 0 ? (
        <div className="text-sm text-gray-400">No incidents yet.</div>
      ) : (
        items.map((it) => (
          <div key={it._id ?? it.timestamp} className="bg-gray-800 border border-gray-700 rounded p-3">
            <div className="flex justify-between items-start">
              <div>
                <div className="text-sm text-gray-400">{it.timestamp ? new Date(it.timestamp).toLocaleString() : ""}</div>
                <div className="mt-1 font-semibold">{it.summary ?? "No summary"}</div>
                <div className="text-xs text-gray-300 mt-1">Category: {it.category ?? "—"} • Severity: {it.severity ?? "—"}</div>
              </div>
            </div>

            {it.recommended_actions && it.recommended_actions.length > 0 && (
              <ul className="mt-2 list-disc list-inside text-sm text-gray-300">
                {it.recommended_actions.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            )}
          </div>
        ))
      )}
    </div>
  );
}
