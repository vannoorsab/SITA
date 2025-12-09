import React, { useEffect, useMemo, useState } from "react";
import { BACKEND } from "../api";
import { io } from "socket.io-client";

const FORCE_POLLING = import.meta.env.VITE_FORCE_POLLING === "true";

type CloudAlert = {
  time?: string;
  category?: string;
  severity?: string;
  summary?: string;
  log?: string;
};

export default function CloudAnalytics() {
  const [alerts, setAlerts] = useState<CloudAlert[]>([]);
  const [socketConnected, setSocketConnected] = useState(false);

  useEffect(() => {
    const url = (BACKEND || "").replace(/\/+$/, "");
    const socket = io(url, {
      path: "/socket.io",
      transports: FORCE_POLLING ? ["polling"] : ["websocket", "polling"],
    });

    socket.on("connect", () => setSocketConnected(true));
    socket.on("disconnect", () => setSocketConnected(false));

    socket.on("cloud-alert", (a: any) => {
      const item: CloudAlert = {
        time: a.time || a.timestamp || new Date().toISOString(),
        category: a.category,
        severity: a.severity,
        summary: a.summary,
        log: a.log,
      };
      setAlerts((prev) => [item, ...prev].slice(0, 500));
    });

    return () => {
      try {
        socket.disconnect();
      } catch {}
    };
  }, []);

  const totalEvents = alerts.length;

  const severityCounts = useMemo(() => {
    const map = new Map<string, number>();
    alerts.forEach((a) => {
      const key = (a.severity || "Unknown").toUpperCase();
      map.set(key, (map.get(key) || 0) + 1);
    });
    return Array.from(map.entries()).map(([k, v]) => ({ severity: k, count: v }));
  }, [alerts]);

  const categoryCounts = useMemo(() => {
    const map = new Map<string, number>();
    alerts.forEach((a) => {
      const key = a.category || "Other";
      map.set(key, (map.get(key) || 0) + 1);
    });
    return Array.from(map.entries()).map(([k, v]) => ({ category: k, count: v }));
  }, [alerts]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <header className="max-w-7xl mx-auto flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold">Cloud Analytics</h1>
          <p className="text-sm text-slate-400 mt-1">Live analytics based on incoming GCP Cloud logs.</p>
        </div>
        <div className="text-sm">
          <span className={`px-2 py-1 rounded ${socketConnected ? "bg-green-700" : "bg-rose-700"}`}>
            {socketConnected ? "Realtime: connected" : "Realtime: disconnected"}
          </span>
        </div>
      </header>

      <main className="max-w-7xl mx-auto space-y-6">
        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-slate-900 p-4 rounded shadow">
            <h2 className="text-sm font-semibold text-slate-300">Total events (session)</h2>
            <p className="text-3xl font-bold mt-2">{totalEvents}</p>
          </div>

          <div className="bg-slate-900 p-4 rounded shadow">
            <h2 className="text-sm font-semibold text-slate-300">High severity events</h2>
            <p className="text-3xl font-bold mt-2 text-rose-400">
              {severityCounts.find((s) => s.severity.includes("HIGH"))?.count ?? 0}
            </p>
          </div>

          <div className="bg-slate-900 p-4 rounded shadow">
            <h2 className="text-sm font-semibold text-slate-300">Distinct categories</h2>
            <p className="text-3xl font-bold mt-2">{categoryCounts.length}</p>
          </div>
        </section>

        <section className="bg-slate-900 p-4 rounded shadow">
          <h2 className="text-sm font-semibold text-slate-300 mb-3">Events by severity</h2>
          {severityCounts.length === 0 ? (
            <p className="text-sm text-slate-400">No events yet. Generate some activity in your GCP project.</p>
          ) : (
            <ul className="text-sm space-y-1">
              {severityCounts.map((s) => (
                <li key={s.severity} className="flex justify-between">
                  <span>{s.severity}</span>
                  <span className="font-mono">{s.count}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="bg-slate-900 p-4 rounded shadow">
          <h2 className="text-sm font-semibold text-slate-300 mb-3">Top categories</h2>
          {categoryCounts.length === 0 ? (
            <p className="text-sm text-slate-400">No events yet.</p>
          ) : (
            <ul className="text-sm space-y-1 max-h-64 overflow-auto">
              {categoryCounts.map((c) => (
                <li key={c.category} className="flex justify-between">
                  <span>{c.category}</span>
                  <span className="font-mono">{c.count}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}
