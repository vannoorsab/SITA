import { useEffect, useState, type JSX } from "react";
import LogAnalyzer from "./components/LogAnalyzer";
import LogsTable from "./components/LogsTable";
import Dashboard from "./components/Dashboard";
import CloudAnalytics from "./components/CloudAnalytics";
import type { AnalysisResult } from "./types";
import { fetchLogs, connectToCloud, disconnectFromCloud } from "./api";

type Page = "home" | "cloud";
type CloudTab = "dashboard" | "analytics";

function getInitialPage(): Page {
  if (typeof window === "undefined") return "home";
  const saved = window.localStorage.getItem("sita_page");
  return saved === "cloud" ? "cloud" : "home";
}

function getInitialCloudTab(): CloudTab {
  if (typeof window === "undefined") return "dashboard";
  const saved = window.localStorage.getItem("sita_cloudTab");
  return saved === "analytics" ? "analytics" : "dashboard";
}

function getInitialCloudConnected(): boolean {
  if (typeof window === "undefined") return false;
  const saved = window.localStorage.getItem("sita_cloudConnected");
  return saved === "true";
}

export default function App(): JSX.Element {
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [history, setHistory] = useState<AnalysisResult[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [page, setPage] = useState<Page>(getInitialPage);
  const [cloudTab, setCloudTab] = useState<CloudTab>(getInitialCloudTab);
  const [cloudConnected, setCloudConnected] = useState(getInitialCloudConnected);
  const [connectingCloud, setConnectingCloud] = useState(false);
  const [cloudError, setCloudError] = useState<string | null>(null);
  const [cloudSuccess, setCloudSuccess] = useState<string | null>(null);

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

  // Persist page, cloudTab, and cloudConnected so refresh keeps you on same view
  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("sita_page", page);
  }, [page]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("sita_cloudTab", cloudTab);
  }, [cloudTab]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("sita_cloudConnected", cloudConnected ? "true" : "false");
  }, [cloudConnected]);

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 to-gray-900 text-white p-6">
      <div className="max-w-6xl mx-auto">
        <header className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 mb-6">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold">SITA — Security Incident Triage Agent</h1>
            <p className="text-sm text-gray-400 mt-1">Cloud Run • Gemini LLM • MongoDB • BigQuery</p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <div className="text-sm text-gray-400">
              Backend: <code className="text-xs">{import.meta.env.VITE_BACKEND_URL}</code>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={async () => {
                  setConnectingCloud(true);
                  setCloudError(null);
                  setCloudSuccess(null);

                  try {
                    if (cloudConnected) {
                      const res = await disconnectFromCloud();
                      if (res.data?.connected === false || res.status === 200) {
                        setCloudConnected(false);
                        setPage("home");
                        setCloudTab("dashboard");
                        setCloudSuccess("Disconnected from Cloud successfully.");
                      }
                    } else {
                      const res = await connectToCloud();
                      if (res.data?.connected) {
                        setCloudConnected(true);
                        setPage("cloud");
                        setCloudTab("dashboard");
                        setCloudSuccess("Connected to Cloud successfully.");
                      } else {
                        setCloudError(res.data?.error || "Failed to connect to Cloud");
                      }
                    }
                  } catch (e: any) {
                    setCloudError(e?.response?.data?.error || e?.message || "Cloud operation failed");
                  } finally {
                    setConnectingCloud(false);
                  }
                }}
                disabled={connectingCloud}
                className={`px-3 py-1 rounded text-xs ${
                  cloudConnected ? "bg-rose-700 hover:bg-rose-800 text-white" : "bg-indigo-600 hover:bg-indigo-700 text-white"
                } disabled:opacity-60`}
              >
                {cloudConnected ? "Disconnect from Cloud" : connectingCloud ? "Connecting…" : "Connect to Cloud"}
              </button>
            </div>
            {cloudError && <div className="text-xs text-red-400 text-right max-w-xs">{cloudError}</div>}
            {cloudSuccess && !cloudError && (
              <div className="text-xs text-emerald-400 text-right max-w-xs">{cloudSuccess}</div>
            )}
          </div>
        </header>

        {page === "home" ? (
          <>
            <main className="grid md:grid-cols-2 gap-6">
              <section>
                <LogAnalyzer
                  onDone={(r) => {
                    setAnalysis(r ?? null);
                    loadHistory();
                  }}
                />
                {analysis && (
                  <div className="mt-4 bg-gray-800 p-4 rounded border border-gray-700">
                    <h2 className="font-semibold mb-2">Analysis Result</h2>
                    <div>
                      <strong>Severity:</strong> {analysis.severity ?? "—"}
                    </div>
                    <div>
                      <strong>Category:</strong> {analysis.category ?? "—"}
                    </div>
                    <div className="mt-2">
                      <strong>Summary:</strong> {analysis.summary ?? "—"}
                    </div>
                    {analysis.recommended_actions && (
                      <div className="mt-2">
                        <strong>Recommendations:</strong>
                        <ul className="list-disc list-inside mt-1 text-sm">
                          {analysis.recommended_actions.map((a, i) => (
                            <li key={i}>{a}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </section>

              <aside>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-lg font-semibold">Incident History</h3>
                  <button onClick={loadHistory} className="text-sm text-blue-400">
                    Refresh
                  </button>
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
          </>
        ) : (
          <div className="mt-4">
            <div className="flex items-center gap-2 mb-4 justify-end">
              <div className="inline-flex rounded bg-slate-800 p-1 text-xs">
                <button
                  type="button"
                  onClick={() => setCloudTab("dashboard")}
                  className={`px-3 py-1 rounded ${
                    cloudTab === "dashboard" ? "bg-slate-700 text-white" : "text-gray-300"
                  }`}
                >
                  Dashboard
                </button>
                <button
                  type="button"
                  onClick={() => setCloudTab("analytics")}
                  className={`px-3 py-1 rounded ${
                    cloudTab === "analytics" ? "bg-slate-700 text-white" : "text-gray-300"
                  }`}
                >
                  Analytics
                </button>
              </div>
            </div>

            {cloudTab === "dashboard" ? <Dashboard /> : <CloudAnalytics />}
          </div>
        )}
      </div>
    </div>
  );
}
