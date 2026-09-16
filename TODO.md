# Presence — Roadmap

> Fast, private face-recognition attendance system for classrooms.  
> **Hybrid engine**: Client-side local inference (face-api.js) + Cloud inference (InsightFace) backed by PostgreSQL & FastAPI.

This file tracks **outstanding work only**. Shipped milestones (safe embeddings storage, relational attendance persistence, hybrid local/cloud recognition, camera capture, and the initial test suite) are recorded in git history and documented under "Key Architecture Decisions" in `AGENTS.md`.

## 🚀 Upcoming Milestones

### 📌 Phase 1: CI/CD & Cloud Deployment
Target: Free, zero-cost **local-only** hosting — Render (Docker API) + Cloudflare Pages/Vercel (static frontend) + Neon/Supabase (PostgreSQL).

> **Deployment profile:** [`docs/local-only-deployment-plan.md`](docs/local-only-deployment-plan.md). Hosted builds run browser-only inference (`CLOUD_MODE_ENABLED=false`, no server ML runtime). Full InsightFace cloud mode stays available on the developer machine via `docker-compose` / `run.ps1` (`INSTALL_CLOUD=true`).

- [ ] **Health Check Endpoint**: Add `GET /api/health` returning database connectivity and service status. *(Render currently health-checks `/`.)*
- [ ] **GitHub Actions CI (`.github/workflows/test.yml`)**:
  - Backend test runner (uv + pytest with PostgreSQL service container).
  - Frontend test runner (`bun test` + `bun run build`).
  - Lint gates (`uv run ruff check`, `bun run lint`).
- [ ] **Cloud Database Setup**:
  - [ ] Provision a permanent PostgreSQL instance on Neon or Supabase (500 MB free tier, no 30-day deletion).
  - [x] Env-driven `DATABASE_URL` documented in `backend/.env.example`.
- [ ] **Backend Deployment (Render — Docker Web Service)**:
  - [x] Infrastructure-as-code (`render.yaml`, free plan) and `${PORT}` support in `backend/Dockerfile`.
  - [x] Production dependency group: `cloud` is now an optional extra, so the lite image installs no InsightFace/ONNX/OpenCV/Pillow and imports none of them.
  - [ ] Handle spin-down cold starts (frontend ping / keep-alive).
- [ ] **Frontend Deployment (Cloudflare Pages / Vercel — static)**:
  - [x] Static build (`bun run build`) serving model weights from `/models/`.
  - [x] Backend URL via `VITE_API_BASE_URL`; `VITE_ALLOW_CLOUD=false` forces local mode and hides the cloud toggle.

### 📌 Phase 2: Authentication & Multi-Tenancy
Target: Secure multi-teacher support and class isolation.

- [ ] **Auth Provider Integration**:
  - Supabase Auth or FastAPI JWT auth with `python-jose` / `passlib` / `bcrypt`.
  - Teacher sign-up and login (email/password, Google OAuth).
- [ ] **Teacher Ownership & Data Isolation**:
  - Add `teacher_id` / `user_id` foreign keys to classes, students, and attendance sessions.
  - Implement Row Level Security (RLS) or API route-level authorization guards.
- [ ] **Protected Routes**:
  - Frontend auth context, login/register modal/page, and JWT injection in HTTP requests.

### 📌 Phase 3: Analytics & User Experience
- [ ] **Attendance Analytics Dashboard**:
  - Visual charts (e.g. `recharts`) showing attendance trends over time per class and student.
  - Identification of chronic absentees and attendance rate summaries.
- [ ] **Bulk Enrollment & CSV Import**:
  - Ability to import student roster from CSV / Excel spreadsheets.
- [ ] **PWA / Mobile Polish**:
  - Web app manifest and service worker for installable mobile web app.
  - Improved mobile camera viewfinder styling.

### 📌 Phase 4: Advanced ML & Optimization (Stretch Goals)
- [ ] **Optimal Face Assignment (Hungarian Algorithm)**:
  - Replace greedy cosine similarity matching with global minimum-cost bipartite matching via `scipy.optimize.linear_sum_assignment`.
- [ ] **Database Vector Search (`pgvector`)**:
  - Add `pgvector` extension and `vector(512)` / `vector(128)` columns for in-database cosine distance matching (`ORDER BY embedding <=> query LIMIT 1`).
- [ ] **Async Inference Pipeline**:
  - Offload CPU/GPU-heavy InsightFace processing to worker threadpools (`starlette.concurrency.run_in_threadpool`) or Celery/Redis queue.
- [ ] **Adaptive Detection Resolution**:
  - Dynamic `det_size` scaling in InsightFace based on image dimensions to catch distant/small faces in large classrooms.

## 📐 Architecture Reference

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Frontend** | React 18, Vite, TailwindCSS | Single-page application |
| **Local ML Engine** | `@vladmandic/face-api` (TF.js/WASM) | In-browser 128-d face detection & descriptor generation |
| **Cloud ML Engine** | InsightFace (ArcFace / ONNX) | Server-side 512-d high-accuracy face recognition |
| **Backend API** | FastAPI, Python 3.11+ | REST endpoints, thin matching API, attendance persistence |
| **Database** | PostgreSQL 16 (`psycopg` v3 + pool) | Relational student & attendance records with binary embeddings |
| **Testing** | `pytest` (backend), `bun test` (frontend) | Comprehensive automated test suite (34 tests total) |
| **Packaging** | Docker, Docker Compose, Bun, uv | Reproducible containerized local & cloud deployment |

### Storage Footprint

| Model | Embedding Dimensions | Bytes per Embedding | Full Student Row |
| :--- | :---: | :---: | :---: |
| **InsightFace (ArcFace)** | 512 × float32 | 2,048 bytes (2 KB) | ~2.2 KB |
| **face-api.js (FaceNet)** | 128 × float32 | 512 bytes (0.5 KB) | ~0.7 KB |

*An attendance record is ~75 bytes. A full school year of attendance for 40 students × 180 days is only **~540 KB**.*
