# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Core commands

### Install dependencies

Use npm (lockfile is `package-lock.json`):

- Install: `npm install`

### Development server

- Start dev server (Vite, hot reload): `npm run dev`
  - Default URL: `http://localhost:5173` (Vite default, unless overridden).
  - The frontend expects a backend URL in `VITE_BACKEND_URL` (see Environments below).

### Build

- Type-check and production build: `npm run build`
  - Runs `tsc -b` (uses `tsconfig.json` / `tsconfig.app.json` / `tsconfig.node.json`)
  - Then runs `vite build` to emit static assets into `dist/`.

### Linting

- Lint all TypeScript/TSX files using flat ESLint config: `npm run lint`
  - ESLint configuration lives in `eslint.config.js` and uses:
    - `@eslint/js` recommended
    - `typescript-eslint` recommended
    - `eslint-plugin-react-hooks` recommended
    - `eslint-plugin-react-refresh` Vite preset

### Preview production build

- Build (if not already) and run local preview server: `npm run preview`

### Docker image

The repo includes a Dockerized production build using Nginx:

- Build image (example): `docker build -t sita-frontend .`
- Run container (example): `docker run -p 8080:8080 sita-frontend`
  - Serves the built SPA from Nginx using `nginx.conf` (SPA fallback to `index.html`).

## Environments & configuration

### Backend URL

All API calls go through a single backend base URL:

- Defined in `src/api.ts` as `BACKEND = import.meta.env.VITE_BACKEND_URL ?? "https://sita-backend-310714690883.us-central1.run.app"`.
- Local overrides:
  - `.env` and `.env.production` (both currently set `VITE_BACKEND_URL` to the same Cloud Run URL).
  - During development, set `VITE_BACKEND_URL` for a different backend by editing `.env` or exporting the variable before running `npm run dev`.
- The effective backend URL is surfaced in the UI header via `import.meta.env.VITE_BACKEND_URL`.

### Realtime transport (dashboard)

`src/components/Dashboard.tsx` can force Socket.IO to use polling instead of websockets:

- Env var: `VITE_FORCE_POLLING` (string "true" to enable forced polling).
- This is read via `import.meta.env.VITE_FORCE_POLLING`.

## High-level architecture

### Frontend stack

- React 19 + TypeScript, bundled with Vite (`vite.config.ts` with `@vitejs/plugin-react`).
- Styling via Tailwind CSS (`tailwind.config.js`, `postcss.config.js`, and `src/index.css` / `src/App.css`).
- HTTP client: `axios`.
- Charts and dashboard visuals: `recharts`.
- Realtime updates: `socket.io-client` connected to the backend.

### Application entry & layout

- `src/main.tsx`
  - Bootstraps React using `createRoot` from `react-dom/client`.
  - Renders `<App />` within `React.StrictMode` and imports global styles from `src/index.css`.

- `src/App.tsx`
  - Top-level application shell with two main views selected via local state `view: "triage" | "dashboard"`:
    - **Triage view** (default):
      - Left column: `<LogAnalyzer />` to submit a single log line for analysis.
      - Right column: `<LogsTable />` showing incident history fetched from the backend.
      - Polls `fetchLogs()` on mount and every 30 seconds to keep the history fresh.
      - Maintains `analysis` (latest analysis result) and `history` (list of previous analyses).
    - **Dashboard view**:
      - Renders `<Dashboard />`, a realtime alert and analytics dashboard.
  - Binds `import.meta.env.VITE_BACKEND_URL` into the header for quick inspection of the backend target.

### API boundary

- `src/api.ts` centralizes all HTTP calls and backend URL handling:
  - `BACKEND` base URL with env override and Cloud Run default.
  - `analyzeLog(log: string)` → `POST /analyze-log` with `{ logText }`.
  - `fetchLogs()` → `GET /logs` (used by both App history and Dashboard).
  - `fetchAnalysisResults()` → `GET /analysis-results`.
  - `deleteLog(id: string)` → `DELETE /logs/:id`.
  - `deleteAnalysisResult(id: string)` → `DELETE /analysis-results/:id`.

When adding new backend endpoints, create small wrapper functions here rather than scattering `axios` calls inside components.

### Domain model

- `src/types.ts` defines the core incident analysis shape:

  - `AnalysisResult` (partial / flexible type) with fields like `severity`, `category`, `summary`, `root_cause`, `recommended_actions`, plus an index signature for extra backend fields.

This is the main type passed between the triage UI, history list, and dashboard.

### Triage flow components

- `src/components/LogAnalyzer.tsx`
  - Handles the user flow of pasting a single log line and triggering analysis.
  - Local state: `logText`, `loading`, `error`.
  - Calls `analyzeLog()` from `api.ts` and normalizes the response to `res.data.analysis ?? res.data`.
  - Notifies parent via `onDone(AnalysisResult | undefined)` so `App` can both show the latest analysis and refresh history.

- `src/components/LogsTable.tsx`
  - Pure presentational component to display a list of `AnalysisResult` items.
  - Shows timestamp (formatted via `toLocaleString`), summary, category, severity, and recommended actions list.
  - Used in the triage view sidebar to render incident history.

### Live dashboard

- `src/components/Dashboard.tsx`
  - Maintains in-memory list of `alerts` and displays them along with aggregate charts.
  - On mount:
    - Calls `fetchLogs()` for initial dataset, normalizing:
      - Accepts either an array response or an object with `alerts`.
      - Reverses the array to ensure newest-first ordering and caps at ~200 items.
    - Establishes a Socket.IO connection to the backend using `BACKEND` as base URL.
      - Optionally forces polling via `VITE_FORCE_POLLING`.
      - Listens to `cloud-alert` events and prepends normalized alerts (with fallback timestamp) into local state, keeping a sliding window (~300 items).
  - Derived data (via `useMemo`):
    - **`eventsOverTime`**: groups alerts by minute (using a `Map`) to feed a `LineChart`.
    - **`categoryBreakdown`**: counts alerts per category for a `PieChart`.
  - Renders:
    - Header with realtime connection badge.
    - Left: `AlertsTable` with latest alerts.
    - Right: small charts and summary stats (total events, explanatory text).

- `src/components/AlertsTable.tsx`
  - Presentation for alerts as a table, independent from the `AnalysisResult` type.
  - Local `AlertItem` type with optional `id`, `time`, `category`, `severity`, `summary`, `log`.
  - Uses `sevClass()` helper to map severity text to Tailwind color classes (error/high → red, warn/medium → amber, info/informational → blue, default gray).

### Styling and layout system

- Tailwind-based styles defined via:
  - `tailwind.config.js`: points at `index.html` and all `src/**/*.{js,ts,jsx,tsx}` for class scanning.
  - `postcss.config.js`: Tailwind + Autoprefixer.
  - `src/index.css` and `src/App.css`: global and per-app styling (gradients, layout, typography).

Most component markup is composed of Tailwind utility classes; when adjusting layout or theming, prefer editing these classes rather than introducing ad hoc inline styles.

### Build & deploy pipeline

- Local / CI build:
  - `npm ci` followed by `npm run build` is the canonical production build sequence.

- Containerized deploy:
  - `Dockerfile` has a two-stage build:
    - `node:18-alpine` builder: installs dependencies via `npm ci --legacy-peer-deps`, copies the repo, runs `npm run build`.
    - `nginx:stable-alpine` runtime: copies `dist/` into Nginx web root and uses `nginx.conf` to configure SPA routing.

If you change Vite output paths or add routes, ensure `nginx.conf` still points to the correct `index.html` for SPA fallback.
