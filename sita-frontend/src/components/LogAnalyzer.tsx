import { useState } from 'react';
import type { AnalysisResult } from "../types";
import { analyzeLog } from "../api";

export default function LogAnalyzer({ onDone }: { onDone: (r?: AnalysisResult) => void }) {
  const [logText, setLogText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  const runAnalysis = async () => {
    if (!logText.trim()) return setError("Please paste a log entry first.");
    setLoading(true);
    setError("");
    try {
      const res = await analyzeLog(logText);
      const payload = res.data?.analysis ?? res.data;
      onDone(payload);
    } catch (e: any) {
      setError(e?.response?.data?.error || e?.message || "Network error");
      onDone(undefined);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-gray-900 p-4 rounded shadow border border-gray-700">
      <label className="block text-sm text-gray-300 mb-2">Paste one log entry</label>
      <textarea
        className="w-full h-36 p-3 rounded bg-gray-800 border border-gray-700 text-sm resize-none"
        placeholder="e.g. 2025-01-10 ERROR Failed login attempt from IP 123.45.67.89"
        value={logText}
        onChange={(e) => setLogText(e.target.value)}
      />
      <div className="flex gap-2 mt-3">
        <button
          onClick={runAnalysis}
          disabled={loading}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 rounded disabled:opacity-60"
        >
          {loading ? "Analyzing…" : "Analyze Log"}
        </button>
        <button
          onClick={() => { setLogText(""); setError(""); onDone(undefined); }}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded"
        >
          Reset
        </button>
      </div>

      {error && <div className="mt-3 text-sm text-red-400">{error}</div>}
    </div>
  );
}
