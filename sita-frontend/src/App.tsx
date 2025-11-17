import { useEffect, useState, type JSX } from "react";
import LogAnalyzer from "./components/LogAnalyzer";
import LogsTable from "./components/LogsTable";
import type { AnalysisResult } from "./types";
import { fetchLogs } from "./api";

export default function App(): JSX.Element {
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [history, setHistory] = useState<AnalysisResult[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const loadHistory = async () => {
    setLoadingHistory(true);
    try {
      const res = await fetchLogs();
      setHistory(res.data || []);
    } catch {
      setHistory([]);
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    loadHistory();
    // poll once every 30s to keep UI fresh during demos (optional)
    const t = setInterval(loadHistory, 30000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 to-gray-900 text-white p-6">
      <div className="max-w-6xl mx-auto">
        <header className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 mb-6">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold">SITA — Security Incident Triage Agent</h1>
            <p className="text-sm text-gray-400 mt-1">Cloud Run • Gemini LLM • MongoDB • BigQuery</p>
          </div>
          <div className="text-sm text-gray-400">Backend: <code className="text-xs">{import.meta.env.VITE_BACKEND_URL}</code></div>
        </header>

        <main className="grid md:grid-cols-2 gap-6">
          <section>
            <LogAnalyzer onDone={(r) => { setAnalysis(r ?? null); loadHistory(); }} />
            {analysis && (
              <div className="mt-4 bg-gray-800 p-4 rounded border border-gray-700">
                <h2 className="font-semibold mb-2">Analysis Result</h2>
                <div><strong>Severity:</strong> {analysis.severity ?? "—"}</div>
                <div><strong>Category:</strong> {analysis.category ?? "—"}</div>
                <div className="mt-2"><strong>Summary:</strong> {analysis.summary ?? "—"}</div>
                {analysis.recommended_actions && (
                  <div className="mt-2">
                    <strong>Recommendations:</strong>
                    <ul className="list-disc list-inside mt-1 text-sm">
                      {analysis.recommended_actions.map((a, i) => <li key={i}>{a}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </section>

          <aside>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-semibold">Incident History</h3>
              <button onClick={loadHistory} className="text-sm text-blue-400">Refresh</button>
            </div>

            {loadingHistory ? (
              <div className="text-sm text-gray-400">Loading…</div>
            ) : (
              <LogsTable items={history} />
            )}
          </aside>
        </main>

        <footer className="mt-8 text-sm text-gray-400">
          <div>Tip: Paste sample logs and click Analyze. Use Refresh to update history.</div>
        </footer>
      </div>
    </div>
  );
}
