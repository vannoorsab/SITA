import React, { useEffect, useMemo, useState } from "react";
import AlertsTable from "./AlertsTable";
import AgentStatusPanel from "./AgentStatusPanel";
import AgentDetailsModal from "./AgentDetailsModal";
import { BACKEND, fetchAgentsActivity, type AgentsActivityResponse } from "../api";
import { io } from "socket.io-client";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import type { AgentStatus, AgentId } from "../types/agent";

const FORCE_POLLING = import.meta.env.VITE_FORCE_POLLING === "true";

const INITIAL_AGENTS: AgentStatus[] = [
  { id: "collector", label: "Collector", status: "idle" },
  { id: "analyzer", label: "Analyzer", status: "idle" },
  { id: "triage", label: "Triage", status: "idle" },
  { id: "remediation", label: "Remediation", status: "idle" },
  { id: "orchestrator", label: "Orchestrator", status: "idle" },
  { id: "reporter", label: "Reporter", status: "idle" },
  { id: "learning", label: "Learning", status: "idle" },
];

function mergeByName(
  prev: AgentStatus[],
  update: AgentStatus | AgentStatus[],
): AgentStatus[] {
  const updates = Array.isArray(update) ? update : [update];
  const map = new Map<AgentId, AgentStatus>();

  // start from previous state
  prev.forEach((a) => {
    map.set(a.id, a);
  });

  // apply updates, merging shallowly and ensuring lastUpdated is set
  const nowIso = new Date().toISOString();
  updates.forEach((u) => {
    const existing = map.get(u.id) ?? {
      id: u.id,
      label: u.label,
      status: "idle" as const,
    };
    map.set(u.id, {
      ...existing,
      ...u,
      lastUpdated: u.lastUpdated ?? nowIso,
    });
  });

  // ensure we always have all canonical agents in a stable order
  return INITIAL_AGENTS.map((base) => map.get(base.id) ?? base);
}

export default function Dashboard() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [agents, setAgents] = useState<AgentStatus[]>(INITIAL_AGENTS);
  const [socketConnected, setSocketConnected] = useState(false);

  const [selectedAgent, setSelectedAgent] = useState<AgentStatus | null>(null);
  const [selectedAgentEvents, setSelectedAgentEvents] = useState<string[]>([]);
  const [isAgentModalOpen, setIsAgentModalOpen] = useState(false);
  const [agentsActivity, setAgentsActivity] = useState<AgentsActivityResponse>({} as AgentsActivityResponse);

  function handleAgentClick(agent: AgentStatus) {
    setSelectedAgent(agent);
    const activity = agentsActivity?.[agent.id];
    setSelectedAgentEvents(activity?.recentEvents ?? []);
    setIsAgentModalOpen(true);
  }

  useEffect(() => {
    // connect to socket.io for realtime updates (Cloud Logging & agents)
    const url = (BACKEND || "").replace(/\/+$/, "");
    const socket = io(url, {
      path: "/socket.io",
      transports: FORCE_POLLING ? ["polling"] : ["websocket", "polling"],
    });

    socket.on("connect", () => setSocketConnected(true));
    socket.on("disconnect", () => setSocketConnected(false));

    socket.on("cloud-alert", (a: any) => {
      const item = { ...a, timestamp: a.timestamp || new Date().toISOString() };
      setAlerts((prev) => [item, ...prev].slice(0, 300));
    });

    // optional: backend can emit an array of agent statuses or a single update
    socket.on("agent-status", (payload: AgentStatus | AgentStatus[]) => {
      setAgents((prev) => mergeByName(prev, payload));
    });

    return () => {
      try {
        socket.disconnect();
      } catch {}
    };
  }, []);

  // Poll backend /agents/activity every 10s to keep agent statuses fresh
  useEffect(() => {
    let cancelled = false;

    const loadActivity = async () => {
      const data = await fetchAgentsActivity();
      if (cancelled) return;

      setAgentsActivity(data);

      // merge status + lastUpdated into existing AgentStatus list in a stable order
      setAgents((prev) => {
        const prevMap = new Map<AgentId, AgentStatus>();
        prev.forEach((a) => prevMap.set(a.id, a));

        return INITIAL_AGENTS.map((base) => {
          const existing = prevMap.get(base.id) ?? base;
          const activity = data[base.id];
          if (!activity) return existing;
          return {
            ...existing,
            status: activity.status,
            lastUpdated: activity.lastUpdated,
          };
        });
      });
    };

    loadActivity();
    const intervalId = setInterval(loadActivity, 10000);

    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, []);

  // charts data
  const eventsOverTime = useMemo(() => {
    // group by minute (keep insertion order by using Map)
    const map = new Map<string, number>();
    // iterate oldest -> newest to create an intuitive time series
    alerts
      .slice()
      .reverse()
      .forEach((a) => {
        const key = new Date(a.timestamp || Date.now()).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });
        map.set(key, (map.get(key) || 0) + 1);
      });
    return Array.from(map.entries()).map(([time, count]) => ({ time, count }));
  }, [alerts]);

  const categoryBreakdown = useMemo(() => {
    const map = new Map<string, number>();
    alerts.forEach((a) => {
      const c = a.category || "Other";
      map.set(c, (map.get(c) || 0) + 1);
    });
    return Array.from(map.entries()).map(([name, value]) => ({ name, value }));
  }, [alerts]);

  const COLORS = ["#EF4444", "#F59E0B", "#3B82F6", "#10B981", "#8B5CF6", "#F97316", "#64748B"];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <header className="max-w-7xl mx-auto flex items-center justify-between">
        <h1 className="text-2xl font-bold">SITA Live Dashboard</h1>
        <div className="text-sm">
          <span className={`px-2 py-1 rounded ${socketConnected ? "bg-green-700" : "bg-rose-700"}`}>
            {socketConnected ? "Realtime: connected" : "Realtime: disconnected"}
          </span>
        </div>
      </header>

      <main className="max-w-7xl mx-auto mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section className="lg:col-span-2 bg-slate-900 p-4 shadow rounded">
          <h2 className="font-semibold text-lg mb-3">Latest Alerts</h2>
          <AlertsTable alerts={alerts} />
        </section>

        <aside className="space-y-4">
          <div className="bg-slate-900 p-4 shadow rounded">
            <AgentStatusPanel agents={agents} onAgentClick={handleAgentClick} />
          </div>

          <div className="bg-slate-900 p-4 shadow rounded space-y-4">
            <div>
              <h3 className="font-semibold">Events over time</h3>
              <div style={{ width: "100%", height: 180 }} className="mt-2 bg-slate-800 p-2 rounded">
                <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                  <LineChart data={eventsOverTime}>
                    <XAxis dataKey="time" tick={{ fill: "#cbd5e1" }} />
                    <YAxis tick={{ fill: "#cbd5e1" }} />
                    <Tooltip />
                    <Line type="monotone" dataKey="count" stroke="#60a5fa" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div>
              <h3 className="font-semibold">Category breakdown</h3>
              <div style={{ width: "100%", height: 220 }} className="mt-2 bg-slate-800 p-2 rounded">
                <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                  <PieChart>
                    <Pie
                      data={categoryBreakdown}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={40}
                      outerRadius={70}
                      label
                    >
                      {categoryBreakdown.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="text-sm text-slate-400">
              <p>Total events: {alerts.length}</p>
              <p className="mt-1">Realtime shows incoming Pub/Sub push events (via backend socket.io).</p>
            </div>
          </div>
        </aside>
      </main>

      <AgentDetailsModal
        isOpen={isAgentModalOpen}
        onClose={() => {
          setIsAgentModalOpen(false);
          setSelectedAgent(null);
          setSelectedAgentEvents([]);
        }}
        agent={selectedAgent}
        recentEvents={selectedAgentEvents}
      />
    </div>
  );
}
