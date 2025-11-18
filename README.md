# 🔐 SITA Alerts  
### *Security Intelligent Threat Analyzer – AI Powered Cloud Log Monitoring System*

SITA Alerts is an AI-powered real-time cloud security monitoring platform built using *Google Cloud Run, Pub/Sub, Cloud Logging, MongoDB, Socket.io, and an ADK Security Agent*.

It analyzes logs using AI, detects security threats, classifies severity, and displays *real-time alerts* on a dark-themed dashboard with charts and live streaming.

This system is fully production-ready and hackathon-ready.

---

## 🚀 Features

### 🔍 AI Log Analyzer  
- Upload/enter logs from UI  
- AI agent generates:  
  - Severity (Low/Medium/High/Critical)  
  - Category  
  - Summary  
  - Root Cause  
  - Recommended Action  

### ☁ One-Click Cloud Connection  
- Automatically creates Pub/Sub topic & subscription  
- Connects Cloud Logging → Pub/Sub → Cloud Run  
- Displays *Cloud Connected* on UI  
- Opens dashboard automatically  

### 📡 Real-Time Cloud Monitoring  
- Google Cloud Logging Sink pushes to Pub/Sub  
- Pub/Sub pushes to Cloud Run using authenticated push  
- Cloud Run streams events via WebSocket  
- Dashboard updates instantly  

### 📊 Real-Time Dashboard  
- Live alerts feed  
- Severity color badges  
- Trend chart  
- Category distribution chart  
- Auto-refreshing stream  
- Dark theme cyber-security UI  

### 🧠 ADK Agent Integration  
All logs are enriched with ADK LLM analysis for accurate security classification.

---

## 🏗 Architecture



![SITA Architecture](./SITA-Architecture.png)



---

# 🛠 Local Setup

## 1️⃣ Backend Setup

bash
cd sita-backend
npm install
npm run dev


Create .env in backend:

env
MONGO_URI=<your MongoDB URI>
ADK_URL=<your ADK Security Agent URL>
PROJECT_ID=<your GCP project ID>
BACKEND_URL=http://localhost:8080
PUBSUB_TOPIC=sita-alerts
PUBSUB_PUSH_SECRET=super-secret-key
BIGQUERY_DATASET=incident_data
BIGQUERY_TABLE=incident_events


---

## 2️⃣ Frontend Setup

bash
cd sita-frontend
npm install
npm run dev


Create sita-frontend/.env:

env
VITE_BACKEND_URL=http://localhost:8080
VITE_FRONTEND_URL=http://localhost:5173


---

# ☁ Deployment Guide (Google Cloud)

## 1️⃣ Deploy Backend to Cloud Run

bash
gcloud builds submit --tag gcr.io/$PROJECT_ID/sita-backend

gcloud run deploy sita-backend \
  --image gcr.io/$PROJECT_ID/sita-backend \
  --region us-central1 \
  --allow-unauthenticated \
  --platform managed \
  --set-env-vars "MONGO_URI=...,ADK_URL=...,PROJECT_ID=$PROJECT_ID,BACKEND_URL=...,PUBSUB_TOPIC=sita-alerts,PUBSUB_PUSH_SECRET=super-secret-key"


Backend URL will look like:  

https://sita-backend-xxxxx-uc.a.run.app


---

## 2️⃣ Deploy Frontend

### Option A: Deploy via Cloud Storage (Static Website)

bash
npm run build
gsutil mb gs://$PROJECT_ID-sita-frontend
gsutil -m rsync -r dist gs://$PROJECT_ID-sita-frontend
gsutil iam ch allUsers:objectViewer gs://$PROJECT_ID-sita-frontend


Your UI URL:

https://storage.googleapis.com/$PROJECT_ID-sita-frontend/index.html


---

## 3️⃣ Create Pub/Sub Topic + Subscription

bash
gcloud pubsub topics create sita-alerts


Create a push service-account:

bash
gcloud iam service-accounts create pubsub-pusher


Give permission:

bash
gcloud run services add-iam-policy-binding sita-backend \
  --member=serviceAccount:pubsub-pusher@$PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/run.invoker


Create push subscription:

bash
gcloud pubsub subscriptions create sita-alerts-sub \
  --topic=sita-alerts \
  --push-endpoint="https://<backend-url>/pubsub/push" \
  --push-auth-service-account="pubsub-pusher@$PROJECT_ID.iam.gserviceaccount.com"


---

## 4️⃣ Connect Google Cloud Logging → Pub/Sub

bash
gcloud logging sinks create sita-alerts-sink \
"projects/$PROJECT_ID/topics/sita-alerts" \
--log-filter='severity>=ERROR'


Grant Sink Permission:

bash
SINK_SA=$(gcloud logging sinks describe sita-alerts-sink --format="value(writerIdentity)")

gcloud pubsub topics add-iam-policy-binding sita-alerts \
  --member="$SINK_SA" \
  --role="roles/pubsub.publisher"


---

# 🧪 Test

### Test Local Log Analyzer

bash
curl -X POST http://localhost:8080/analyze-log \
  -H "Content-Type: application/json" \
  -d '{"logText":"ERROR: Unauthorized access attempt"}'


### Test Pub/Sub Delivery

bash
gcloud pubsub topics publish sita-alerts \
  --message='{"textPayload":"pubsub test","severity":"ERROR"}'


---

# 🖥 Dashboard (Frontend)

Features visible on dashboard:
- Real-time feed  
- Severity highlighted badges  
- Category selector  
- Timeline chart  
- Last 50 alerts  
- Live WebSocket updates  

---

# 🏆 Why SITA Stands Out

- 💡 AI-powered security analysis  
- 🚀 Real-time GCP Log Monitoring  
- ☁ One-click cloud connection  
- ⚡ Zero-latency WebSocket alerts  
- 🔥 Hackathon-ready architecture  
- 🎨 Dark-themed professional UI  
- 🧭 Complete end-to-end cloud pipeline  

---

-

# 📞 Contact

*Created by:*  
*Vannoorsab*  
Google Cloud Innovator | Cybersecurity Specialist  

---

# ⭐ Support  
If you like this project, please ⭐ the repository on GitHub.
