# Presence — Roadmap & Status

> Fast, private face-recognition attendance system for classrooms.  
> **Hybrid engine**: Client-side local inference (face-api.js) + Cloud inference (InsightFace) backed by PostgreSQL & FastAPI.

---

## 🎯 Completed Milestones

### ✅ Phase 1: Security & Core Persistence
- [x] **Safe Embeddings Storage**: Replaced `pickle` with `numpy.tobytes()` (float32 BLOBs/BYTEA) to eliminate arbitrary code execution vulnerabilities.
- [x] **Attendance Persistence**: Added `attendance_sessions` and `attendance_records` tables with full relational tracking and cascade deletion.
- [x] **Absence Tracking**: Auto-compute absent students per class session and include in attendance results and CSV export.
- [x] **Session History & Inspection**: Endpoints for past session history (`GET /api/attendance/history`) and session details (`GET /api/attendance/sessions/{id}`).

### ✅ Phase 2: Hybrid AI Recognition & Camera Capture
- [x] **In-Browser Camera Capture**: Live webcam/mobile camera capture via `navigator.mediaDevices.getUserMedia` on both Enrollment and Attendance pages.
- [x] **Local Model Engine (face-api.js)**: Integrated `@vladmandic/face-api` for private, client-side face detection and 128-d embedding extraction.
- [x] **Static Model Assets**: Hosted SSD MobileNet v1, FaceLandmark68, and FaceRecognition models in `frontend/public/models/`.
- [x] **Dual-Pipeline Backend Matching**: `POST /api/attendance/match-embeddings` and `POST /api/students/enroll-embedding` supporting both 128-d (local) and 512-d (cloud) embeddings.
- [x] **Client-Side Annotation**: Real-time `<canvas>` bounding box and label rendering in the browser (photos never sent to server in Local mode).
- [x] **Model Selector UI**: Navbar toggle (`Local (Private) | Cloud (Accurate)`) with explanation tooltip and `localStorage` persistence.

### ✅ Phase 3: Production Database (PostgreSQL)
- [x] **PostgreSQL Migration**: Replaced SQLite with `psycopg` (v3) + `psycopg-pool` connection pooling.
- [x] **Relational Schema**: `students` (with `model_type`), `attendance_sessions`, and `attendance_records`.
- [x] **Containerized Dev & Orchestration**: PostgreSQL 16 service added to `docker-compose.yml` with health checks; updated `run.ps1` for local setup.
- [x] **Zero-ORM Direct Queries**: Retained high-performance parameterized SQL queries with `%s` placeholders and connection pooling.

### ✅ Phase 4: Core Test Suite
- [x] **Backend Unit & Integration Tests**: 22 tests covering CRUD, constraints, endpoints, local/cloud matching, duplicate roll numbers, and CSV exports (`uv run pytest`).
- [x] **Frontend Unit Tests**: 12 tests covering API client, model service contracts, and localStorage context state (`bun test`).

---

## 🚀 Active & Upcoming Milestones

### 📌 Phase 5: CI/CD & Cloud Deployment
Target: Free, zero-cost production hosting on Render/Vercel + Neon/Supabase.

- [ ] **Health Check Endpoint**: Add `GET /api/health` returning database connectivity and service status.
- [ ] **GitHub Actions CI (`.github/workflows/test.yml`)**:
  - Backend test runner (uv + pytest with PostgreSQL service container).
  - Frontend test runner (`bun test` + `bun run build`).
- [ ] **Cloud Database Setup**:
  - Provision a permanent PostgreSQL instance on Neon or Supabase (500 MB free tier, no 30-day deletion).
  - Configure `DATABASE_URL` environment variable for production.
- [ ] **Backend Deployment (Render / Railway / Fly.io)**:
  - Infrastructure-as-code (`render.yaml` or Dockerfile).
  - Production dependency group (ensure thin matching API stays comfortably within free tier 512 MB RAM limit).
  - Handle spin-down cold starts (frontend ping / keep-alive).
- [ ] **Frontend Deployment (Vercel / Cloudflare Pages)**:
  - Static build (`bun run build`) with CDN caching for static model weights (`/models/`).
  - Configure API proxy / environment variables for backend URL.

### 📌 Phase 6: Authentication & Multi-Tenancy
Target: Secure multi-teacher support and class isolation.

- [ ] **Auth Provider Integration**:
  - Supabase Auth or FastAPI JWT auth with `python-jose` / `passlib` / `bcrypt`.
  - Teacher sign-up and login (email/password, Google OAuth).
- [ ] **Teacher Ownership & Data Isolation**:
  - Add `teacher_id` / `user_id` foreign keys to classes, students, and attendance sessions.
  - Implement Row Level Security (RLS) or API route-level authorization guards.
- [ ] **Protected Routes**:
  - Frontend auth context, login/register modal/page, and JWT injection in HTTP requests.

### 📌 Phase 7: Analytics & User Experience
- [ ] **Attendance Analytics Dashboard**:
  - Visual charts (e.g. `recharts`) showing attendance trends over time per class and student.
  - Identification of chronic absentees and attendance rate summaries.
- [ ] **Bulk Enrollment & CSV Import**:
  - Ability to import student roster from CSV / Excel spreadsheets.
- [ ] **PWA / Mobile Polish**:
  - Web app manifest and service worker for installable mobile web app.
  - Improved mobile camera viewfinder styling.

### 📌 Phase 8: Advanced ML & Optimization (Stretch Goals)
- [ ] **Optimal Face Assignment (Hungarian Algorithm)**:
  - Replace greedy cosine similarity matching with global minimum-cost bipartite matching via `scipy.optimize.linear_sum_assignment`.
- [ ] **Database Vector Search (`pgvector`)**:
  - Add `pgvector` extension and `vector(512)` / `vector(128)` columns for in-database cosine distance matching (`ORDER BY embedding <=> query LIMIT 1`).
- [ ] **Async Inference Pipeline**:
  - Offload CPU/GPU-heavy InsightFace processing to worker threadpools (`starlette.concurrency.run_in_threadpool`) or Celery/Redis queue.
- [ ] **Adaptive Detection Resolution**:
  - Dynamic `det_size` scaling in InsightFace based on image dimensions to catch distant/small faces in large classrooms.

---

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