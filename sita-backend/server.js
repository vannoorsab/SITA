import express from "express";
import axios from "axios";
import cors from "cors";
import { MongoClient } from "mongodb";
import { BigQuery } from "@google-cloud/bigquery";
import dotenv from "dotenv";

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());

// --- Debug startup info (no secrets printed) ---
console.log("Starting backend — PROJECT_ID:", process.env.PROJECT_ID);
console.log("ADK_URL present:", !!process.env.ADK_URL);
console.log("MONGO_URI present:", !!process.env.MONGO_URI);

// --- MongoDB connect (will throw if URI invalid) ---
const mongoClient = new MongoClient(process.env.MONGO_URI);
try {
  await mongoClient.connect();
  console.log("MongoDB connected");
} catch (err) {
  console.error("MongoDB connection failed:", err && err.message);
  // allow process to continue so Cloud Run logs show failure; you may choose to exit
}

const logsCollection = mongoClient.db("sita").collection("logs");
const bigquery = new BigQuery({ projectId: process.env.PROJECT_ID });

app.get("/", (req, res) => {
  res.json({ status: "Backend Running" });
});

app.post("/analyze-log", async (req, res) => {
  try {
    // accept multiple field names for compatibility
    const logText = req.body.logText || req.body.log || req.body.input;
    if (!logText || typeof logText !== "string") {
      return res.status(400).json({ error: "Missing 'logText' in request body" });
    }

    const adkUrl = process.env.ADK_URL;
    if (!adkUrl || !adkUrl.startsWith("http")) {
      console.error("ADK_URL invalid:", adkUrl);
      return res.status(500).json({ error: "ADK service URL not configured" });
    }

    console.log("Calling ADK at:", adkUrl);
    let adkResponse;
    try {
      adkResponse = await axios.post(adkUrl, { input: logText }, { timeout: 30000 });
      console.log("ADK returned status:", adkResponse.status);
    } catch (err) {
      console.error("ADK call failed:", err.message || err);
      if (err.response) {
        console.error("ADK response status:", err.response.status, "body:", err.response.data);
        return res.status(502).json({ error: "ADK error", details: err.response.data });
      }
      return res.status(502).json({ error: "ADK request failed", details: err.message });
    }

    const result = adkResponse.data?.result || adkResponse.data || {};

    // Save to MongoDB (best-effort)
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
    return res.status(500).json({ error: "Internal server error" });
  }
});

app.get("/logs", async (req, res) => {
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
app.listen(PORT, () => {
  console.log("Backend running on port", PORT);
});
