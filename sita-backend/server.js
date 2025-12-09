import express from "express";
import axios from "axios";
import cors from "cors";
import http from "http";
import { Server as SocketIOServer } from "socket.io";
import { MongoClient } from "mongodb";
import { BigQuery } from "@google-cloud/bigquery";
import { Logging } from "@google-cloud/logging";
import dotenv from "dotenv";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
dotenv.config({ path: path.join(__dirname, ".env") });

const app = express();
app.use(cors());
app.use(express.json());

// --- Debug startup info (no secrets printed) ---
console.log("Starting backend — PROJECT_ID:", process.env.PROJECT_ID);
console.log("ADK_URL present:", !!process.env.ADK_URL);
console.log("MONGO_URI present:", !!process.env.MONGO_URI);

// --- MongoDB connect (will throw if URI invalid) ---
let mongoClient = null;
let logsCollection = null;

if (process.env.MONGO_URI) {
  mongoClient = new MongoClient(process.env.MONGO_URI);
  try {
    await mongoClient.connect();
    console.log("MongoDB connected");
    logsCollection = mongoClient.db("sita").collection("logs");
  } catch (err) {
    console.error("MongoDB connection failed:", err && err.message);
    // allow process to continue so Cloud Run logs show failure; you may choose to exit
  }
} else {
  console.error("MONGO_URI not set; MongoDB features disabled");
}
const bigquery = new BigQuery({ projectId: process.env.PROJECT_ID });
const logging = new Logging({ projectId: process.env.PROJECT_ID });

// --- In-memory agent activity tracking ---
const AGENT_IDS = [
  "collector",
  "analyzer",
  "triage",
  "remediation",
  "orchestrator",
  "reporter",
  "learning",
];

/**
 * agentActivity[agentId] = {
 *   status: "idle" | "running" | "error",
 *   lastUpdated: ISO string,
 *   recentEvents: string[] // last 10 messages
 * }
 */
const agentActivity = {};

// initialize all agents as idle
AGENT_IDS.forEach((id) => {
  agentActivity[id] = {
    status: "idle",
    lastUpdated: new Date().toISOString(),
    recentEvents: [],
  };
});

function recordAgentEvent(agentId, status, message) {
  if (!AGENT_IDS.includes(agentId)) return;

  const now = new Date().toISOString();
  const current = agentActivity[agentId] || {
    status: "idle",
    lastUpdated: now,
    recentEvents: [],
  };

  const nextEvents = [...(current.recentEvents || []), message].slice(-10);

  agentActivity[agentId] = {
    status,
    lastUpdated: now,
    recentEvents: nextEvents,
  };
}

// --- HTTP + socket.io setup ---
const httpServer = http.createServer(app);
const io = new SocketIOServer(httpServer, {
  cors: {
    origin: "*",
  },
});

let gcpConnected = false;
let lastPollTimestamp = new Date(Date.now() - 5 * 60 * 1000).toISOString(); // start 5 minutes ago

io.on("connection", (socket) => {
  console.log("socket.io client connected", socket.id);
  socket.on("disconnect", () => {
    console.log("socket.io client disconnected", socket.id);
  });
});
/* =========================================================
   ✅ Pub/Sub PUSH endpoint (Logs Sink → Pub/Sub → Cloud Run)
   ========================================================= */
app.post("/pubsub/push", async (req, res) => {
  try {
    const msg = req.body?.message;

    if (!msg || !msg.data) {
      console.warn("Pub/Sub push received without message.data");
      return res.status(204).send(); // NO retry
    }

    // Decode base64 payload
    const decoded = Buffer.from(msg.data, "base64").toString("utf8");
    console.log("📨 PUBSUB RAW DATA:", decoded);

    let entry;
    try {
      entry = JSON.parse(decoded);
    } catch (err) {
      console.warn("Pub/Sub message is not valid JSON");
      return res.status(204).send(); // still ACK
    }

    // Normalize log (reuse your architecture)
    const alert = {
      time: entry.timestamp || new Date().toISOString(),
      category: entry.resource?.type || "cloud-log",
      severity: entry.severity || "INFO",
      summary:
        entry.jsonPayload?.message ||
        entry.textPayload ||
        "No summary",
      log: JSON.stringify(entry),
      sourceLogName: entry.logName,
    };

    /* -------- Agent pipeline -------- */
    recordAgentEvent("collector", "running", "Log received via Pub/Sub");
    recordAgentEvent("analyzer", "running", "Analyzed Pub/Sub log");
    recordAgentEvent("triage", "running", `Severity ${alert.severity}`);
    recordAgentEvent("reporter", "running", "Sent alert to dashboard");
    recordAgentEvent("orchestrator", "running", "Pipeline coordinated");
    recordAgentEvent("learning", "running", "Learning updated");

    /* -------- Socket.IO -------- */
    io.emit("cloud-alert", alert);

    /* -------- MongoDB (best-effort) -------- */
    if (logsCollection) {
      await logsCollection.insertOne({
        ...alert,
        createdAt: new Date(),
      });
    }

    // ✅ ALWAYS ACK
    res.status(200).send("OK");
  } catch (err) {
    console.error("❌ Pub/Sub handler crashed:", err);
    // ACK ANYWAY → prevents 429 retry storm
    res.status(204).send();
  }
});


function normalizeLogEntry(entry) {
  const metadata = entry.metadata || {};
  const payload = entry.data; // Cloud Logging payload (jsonPayload, protoPayload, or text)
  const ts = metadata.timestamp || new Date().toISOString();
  const severity = metadata.severity || "INFO";
  const resourceType = metadata.resource && metadata.resource.type ? metadata.resource.type : "generic";
  const logName = metadata.logName || "";

  let raw = "";
  let summary = "";

  // Prefer the structured payload from entry.data when available
  if (typeof payload === "string") {
    raw = payload;
    summary = payload.slice(0, 200);
  } else if (payload && typeof payload === "object") {
    try {
      raw = JSON.stringify(payload);
    } catch {
      raw = String(payload);
    }
    summary = raw.slice(0, 200);
  } else if (metadata.textPayload) {
    raw = metadata.textPayload;
    summary = metadata.textPayload.slice(0, 200);
  } else if (metadata.jsonPayload) {
    try {
      raw = JSON.stringify(metadata.jsonPayload);
    } catch {
      raw = String(metadata.jsonPayload);
    }
    summary = raw.slice(0, 200);
  } else {
    try {
      raw = JSON.stringify(metadata);
    } catch {
      raw = String(metadata);
    }
    summary = raw.slice(0, 200);
  }

  return {
    time: ts,
    category: resourceType || logName || "Cloud Log",
    severity,
    summary,
    log: raw,
    sourceLogName: logName,
  };
}

function isMaliciousLog(alert) {
  const text = (alert.log || alert.summary || "").toLowerCase();

  // 1) Generic text-based indicators (fallback)
  if (text) {
    const badPatterns = [
      "unauthorized",
      "forbidden",
      "permission denied",
      "failed login",
      "brute force",
      "sql injection",
      "union select",
      "xss attack",
      "<script>",
      "malware",
      "ransomware",
      "suspicious",
    ];
    if (badPatterns.some((p) => text.includes(p))) return true;
  }

  // 2) Structured detection using common GCP log formats
  let payload = null;
  try {
    if (alert.log && alert.log.trim().startsWith("{")) {
      payload = JSON.parse(alert.log);
    }
  } catch {
    payload = null;
  }

  if (!payload || typeof payload !== "object") return false;

  // ---- Cloud Audit Logs (protoPayload) ----
  const proto = payload.protoPayload || payload;
  const methodName = String(proto.methodName || "").toLowerCase();
  const statusCode = proto.status && typeof proto.status.code === "number" ? proto.status.code : undefined;
  const resourceName = String(proto.resourceName || "").toLowerCase();

  // Sensitive IAM / admin methods
  const sensitiveMethods = [
    "setiampolicy",
    "setiam",
    "serviceaccounts.keys.create",
    "serviceaccounts.keys.delete",
    "projects.setorgpolicy",
    "organizations.setorgpolicy",
    "cryptoKeyVersions.use",
    "cryptoKeyVersions.destroy",
    "instances.insert",
    "instances.delete",
    "firewalls.insert",
    "firewalls.patch",
  ];

  if (methodName && sensitiveMethods.some((m) => methodName.includes(m))) {
    return true;
  }

  // Repeated permission errors / access denials (7=PERMISSION_DENIED, 16=UNAUTHENTICATED)
  if (typeof statusCode === "number" && [7, 13, 16].includes(statusCode)) {
    return true;
  }

  // Suspicious access to admin APIs / metadata endpoints in resource name
  if (resourceName && (resourceName.includes("metadata.google.internal") || resourceName.includes("/admin"))) {
    return true;
  }

  // ---- VPC Flow Logs / network logs ----
  const flow = payload.jsonPayload || payload;
  const conn = flow.connection || {};
  const dispositionRaw = flow.disposition || flow.disposition_desc || flow.dispositionDescription;
  const disposition = String(dispositionRaw || "").toUpperCase();
  const destPort = Number(conn.dest_port || conn.destination_port || flow.dest_port || flow.destination_port);

  // Frequent denies can indicate scanning; here we flag individual DENY/REJECT events as suspicious.
  if (disposition && ["DENY", "REJECT"].includes(disposition)) {
    return true;
  }

  // High-value ports being accessed (SSH, RDP, DBs, etc.)
  const sensitivePorts = [22, 3389, 3306, 5432, 27017, 6379, 9200, 25];
  if (destPort && sensitivePorts.includes(destPort)) {
    return true;
  }

  return false;
}

// --- Basic local analyzer used when ADK is unavailable or failing ---
function basicLocalAnalyze(logText) {
  const lower = logText.toLowerCase();

  let severity = "INFO";
  let category = "General";
  const recommended_actions = [];

  if (lower.includes("error") || lower.includes("exception") || lower.includes("stack trace")) {
    severity = "HIGH";
    category = "Application Error";
    recommended_actions.push("Investigate application error and check recent deployments.");
  } else if (lower.includes("failed login") || lower.includes("unauthorized") || lower.includes("forbidden")) {
    severity = "HIGH";
    category = "Authentication / Access";
    recommended_actions.push("Review authentication logs and consider blocking suspicious IPs.");
  } else if (lower.includes("warn") || lower.includes("warning")) {
    severity = "MEDIUM";
    category = "Warning";
    recommended_actions.push("Review warning and create follow-up ticket if needed.");
  } else if (lower.includes("timeout") || lower.includes("unreachable") || lower.includes("connection refused")) {
    severity = "MEDIUM";
    category = "Network / Connectivity";
    recommended_actions.push("Check network connectivity and service health.");
  }

  const summary = logText.slice(0, 300);

  if (recommended_actions.length === 0) {
    recommended_actions.push("Review log details and determine if further investigation is required.");
  }

  return { severity, category, summary, recommended_actions };
}

async function pollCloudLogsOnce() {
  if (!gcpConnected) return;

  const filter = `timestamp > "${lastPollTimestamp}"`;

  try {
    const [entries] = await logging.getEntries({
      filter,
      orderBy: "timestamp asc",
      pageSize: 50,
    });

    if (!entries || !entries.length) return;

    // Collector agent received new logs from Cloud Logging (batch-level)
    recordAgentEvent(
      "collector",
      "running",
      `Received ${entries.length} log entr${entries.length === 1 ? "y" : "ies"} from Cloud Logging`,
    );

    for (const entry of entries) {
      const alert = normalizeLogEntry(entry);
      let malicious = false;

      if (isMaliciousLog(alert)) {
        alert.severity = `HIGH (malicious)`;
        malicious = true;
      }

      // Forward raw log to dashboard
      io.emit("cloud-alert", alert);

      if (alert.time && alert.time > lastPollTimestamp) {
        lastPollTimestamp = alert.time;
      }

      const summarySnippet = (alert.summary || alert.log || "")
        .toString()
        .slice(0, 80);

      // Analyzer processes the log
      recordAgentEvent(
        "analyzer",
        "running",
        `Analyzed log from ${alert.category || "unknown"} (${alert.severity || "INFO"}): ${summarySnippet}`,
      );

      // Triage evaluates severity / category
      recordAgentEvent(
        "triage",
        "running",
        `Triaged log as ${alert.severity || "INFO"} severity in ${alert.category || "Other"}`,
      );

      // Remediation only gets activity for suspicious logs
      if (malicious) {
        recordAgentEvent(
          "remediation",
          "running",
          "Evaluating remediation options for suspicious log event",
        );
      }

      // Reporter records / exposes incident
      recordAgentEvent(
        "reporter",
        "running",
        `Reported analysis for log in category ${alert.category || "Other"}`,
      );

      // Orchestrator coordinates pipeline
      recordAgentEvent(
        "orchestrator",
        "running",
        "Coordinated collector → analyzer → triage → remediation steps for log",
      );

      // Learning agent updates internal insights
      recordAgentEvent(
        "learning",
        "running",
        "Updated insights from latest Cloud Logging event",
      );
    }
  } catch (err) {
    console.error("Failed to poll Cloud Logging:", err && err.message);
  }
}

// background poll loop
setInterval(() => {
  pollCloudLogsOnce().catch((err) => {
    console.error("pollCloudLogsOnce error:", err && err.message);
  });
}, 10000);

app.get("/", (req, res) => {
  res.json({ status: "Backend Running" });
});

app.post("/connect-gcp", async (req, res) => {
  try {
    // simple sanity check call to verify credentials / connectivity
    const [entries] = await logging.getEntries({ pageSize: 1, orderBy: "timestamp desc" });
    console.log("/connect-gcp test entries count:", entries ? entries.length : 0);

    // Start by looking back 5 minutes so the dashboard can immediately show recent logs
    lastPollTimestamp = new Date(Date.now() - 5 * 60 * 1000).toISOString();

    gcpConnected = true;
    console.log("GCP Logging connection verified. Starting realtime stream from", lastPollTimestamp);
    res.json({ connected: true });
  } catch (err) {
    console.error("/connect-gcp failed:", err && err.message);
    gcpConnected = false;
    res.status(500).json({ connected: false, error: "Failed to connect to Google Cloud Logging" });
  }
});

app.post("/disconnect-gcp", (req, res) => {
  gcpConnected = false;
  console.log("GCP Logging connection disabled via /disconnect-gcp");
  res.json({ connected: false });
});

app.post("/analyze-log", async (req, res) => {
  try {
    // accept multiple field names for compatibility
    const logText = req.body.logText || req.body.log || req.body.input;
    if (!logText || typeof logText !== "string") {
      return res.status(400).json({ error: "Missing 'logText' in request body" });
    }

    // Analyzer picks up a new log
    recordAgentEvent("analyzer", "running", "Received log for analysis");

    let result;

    const adkUrl = process.env.ADK_URL;
    if (adkUrl && adkUrl.startsWith("http")) {
      console.log("Calling ADK at:", adkUrl);
      try {
        const adkResponse = await axios.post(adkUrl, { input: logText }, { timeout: 30000 });
        console.log("ADK returned status:", adkResponse.status);
        result = adkResponse.data?.result || adkResponse.data || {};
      } catch (err) {
        console.error("ADK call failed, using local analyzer instead:", err.message || err);

        recordAgentEvent(
          "analyzer",
          "running",
          `ADK failed (${err.response?.status || "no status"}). Falling back to local analyzer.`,
        );

        // Fallback: local analysis so UI still works
        result = basicLocalAnalyze(logText);
      }
    } else {
      console.warn("ADK_URL not set or invalid; using local analyzer");
      recordAgentEvent("analyzer", "running", "Using local analyzer (ADK_URL not configured).");
      result = basicLocalAnalyze(logText);
    }

    // Analyzer finished successfully (either ADK or local)
    recordAgentEvent(
      "analyzer",
      "running",
      `Analysis completed: severity=${result.severity || "n/a"}, category=${result.category || "n/a"}`,
    );

    // Triage agent classifies severity/category
    recordAgentEvent(
      "triage",
      "running",
      `Triaged log as ${result.severity || "unknown"} severity in category ${result.category || "unknown"}`,
    );

    // Remediation agent when remediation info is present
    if (result.remediation_id || (Array.isArray(result.recommended_actions) && result.recommended_actions.length)) {
      recordAgentEvent("remediation", "running", "Generated remediation plan for alert");
    }

    // Reporter agent updates incident history
    recordAgentEvent("reporter", "running", "Recorded analysis and incident details");

    // Orchestrator / Learning agents as high-level coordination steps
    recordAgentEvent("orchestrator", "running", "Coordinated analyzer, triage and remediation steps");
    recordAgentEvent("learning", "running", "Updated internal insights from latest analysis");

    // Save to MongoDB (best-effort)
    if (logsCollection) {
      try {
        await logsCollection.insertOne({
          timestamp: new Date(),
          logText,
          ...result,
        });
      } catch (err) {
        console.error("MongoDB insert failed:", err && err.message);
        // continue — we don't want to block response due to logging failure
      }
    }

    // Save to BigQuery (best-effort)
    try {
      await bigquery
        .dataset(process.env.BIGQUERY_DATASET)
        .table(process.env.BIGQUERY_TABLE)
        .insert([
          {
            timestamp: new Date().toISOString(),
            category: result.category || null,
            severity: result.severity || null,
            summary: result.summary || null,
          },
        ]);
    } catch (err) {
      console.error("BigQuery insert failed:", err && err.message);
      // continue
    }

    return res.json({
      success: true,
      analysis: result,
    });
  } catch (error) {
    console.error("Unhandled /analyze-log error:", error && error.stack ? error.stack : error);

    // Global error handler for analyzer pipeline
    recordAgentEvent("analyzer", "error", "Unhandled error in /analyze-log pipeline");

    return res.status(500).json({ error: "Internal server error" });
  }
});

// Expose current in-memory agent activity to the dashboard
app.get("/agents/activity", (req, res) => {
  res.json(agentActivity);
});

app.get("/logs", async (req, res) => {
  if (!logsCollection) {
    return res.status(500).json({ error: "MongoDB not configured" });
  }
  try {
    const logs = await logsCollection.find().sort({ _id: -1 }).limit(50).toArray();
    res.json(logs);
  } catch (err) {
    console.error("Failed to fetch logs:", err && err.message);
    res.status(500).json({ error: "Failed to fetch logs" });
  }
});

// use PORT env or default 8080
const PORT = process.env.PORT || 8080;
httpServer.listen(PORT, () => {
  console.log("Backend (HTTP + socket.io) running on port", PORT);
});
