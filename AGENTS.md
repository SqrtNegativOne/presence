# Presence — AI Agent Reference & Operational Guidelines

Presence is an AI-powered classroom attendance system built with a **hybrid recognition engine**:
- **Local Mode (Private)**: Client-side inference using `@vladmandic/face-api` (128-d embeddings, SSD MobileNet v1). Group photos and facial images never leave the browser.
- **Cloud Mode (Accurate)**: Server-side inference using `InsightFace` `buffalo_l` (512-d ArcFace embeddings, ONNX Runtime, Pillow annotation).
- **Attendance & Absence Tracking**: Relational session persistence in PostgreSQL 16; automatically tracks both present and absent students and exports CSV reports.
- **Live Camera Capture**: Web and mobile camera capture via HTML5 `getUserMedia` across enrollment and attendance workflows.

---

## Stack

| Layer | Tech | Details |
| :--- | :--- | :--- |
| **Backend** | Python 3.11+, FastAPI, uvicorn, uv | Async REST API, OpenAPI docs at `/docs` |
| **Database** | PostgreSQL 16 (`psycopg` v3 + `psycopg-pool`) | Connection pooling, direct parameterized SQL (`%s`), no ORM |
| **Cloud Face Recognition** | InsightFace `buffalo_l` (ArcFace), onnxruntime | 512-d float32 embeddings, server-side detection & matching |
| **Local Face Recognition** | `@vladmandic/face-api` (TF.js / WASM) | 128-d float32 embeddings, client-side detection & landmarks |
| **Image Annotation** | Pillow (cloud) / HTML5 `<canvas>` (local) | Server base64 PNG rendering vs client-side canvas boxes |
| **Frontend** | React 18, Vite, Tailwind CSS v3, react-router-dom v6 | SPA with Lucide React icons and global ModelContext |
| **Logging** | loguru | Pretty, structured terminal logs |
| **Testing** | pytest (backend), bun test (frontend) | Comprehensive automated test coverage |

---

## Directory Layout

```
presence/
├── run.ps1                         Windows launcher (starts Postgres container, runs uv/bun sync, opens servers)
├── docker-compose.yml              3 services: db (Postgres 16), backend (FastAPI), frontend (Vite)
├── AGENTS.md                       AI agent reference & operational instructions
├── README.md                       User-facing project overview & quick start
├── TODO.md                         Roadmap, milestones, and technical specifications
├── backend/
│   ├── pyproject.toml              uv project configuration and pytest settings
│   ├── Dockerfile                  Backend container definition
│   ├── main.py                     FastAPI entry point, CORS, lifespan (init_db)
│   ├── database.py                 PostgreSQL connection pool & raw SQL queries (init, CRUD)
│   ├── routers/
│   │   ├── students.py             POST /enroll, POST /enroll-embedding, GET, DELETE /{id}
│   │   └── attendance.py           POST /process, POST /match-embeddings, GET /history, GET /sessions/{id}, GET /export
│   ├── services/
│   │   ├── face_service.py         InsightFace singleton, encode_single_face, match_embeddings, match_group_photo
│   │   └── image_service.py        Pillow annotation -> base64 PNG
│   ├── tests/                      Pytest suite (conftest.py, test_database, test_attendance_api, test_students_api, etc.)
│   └── data/                       InsightFace model cache (buffalo_l/)
└── frontend/
    ├── package.json / bun.lock     Bun dependencies & scripts
    ├── vite.config.js              Proxy /api -> $BACKEND_URL (default: localhost:8000)
    ├── public/models/              Static weights for face-api.js (SSD MobileNet v1, Landmark68, Recognition)
    ├── src/
    │   ├── api.js                  Centralized API client for all backend endpoints
    │   ├── App.jsx                 Main layout, routing, and ModelSelector toggle
    │   ├── components/
    │   │   └── CameraCapture.jsx   Reusable camera modal with countdown & snapshotting
    │   ├── context/
    │   │   └── ModelContext.jsx    Active model state ('local' | 'cloud') with localStorage persistence
    │   ├── services/
    │   │   └── localFaceService.js face-api.js loader, descriptor extraction & canvas drawing
    │   └── pages/
    │       ├── EnrollPage.jsx      Enrollment with file upload or live camera
    │       ├── StudentsPage.jsx    Student roster listing and deletion
    │       └── AttendancePage.jsx  Attendance processing, session persistence, camera capture, CSV export
    └── test/                       Frontend unit tests (api.test.js, localFaceService.test.js, ModelContext.test.js)
```


## Running Locally

### Option A: Automated Startup (Windows)
```powershell
.\run.ps1
```
The script performs preflight checks, syncs backend dependencies (`uv sync`), installs frontend dependencies (`bun install`), spins up the PostgreSQL container (`docker compose up db -d`), and opens separate terminal windows for backend and frontend.

### Option B: Manual Startup
1. **Start PostgreSQL database**:
   ```bash
   docker compose up db -d
   ```
   *Database runs on `localhost:5432` with user `presence`, password `presence`, database `presence`.*

2. **Start Backend (FastAPI)**:
   ```bash
   cd backend
   uv sync
   uv run uvicorn main:app --reload --port 8000
   ```
   *Backend API explorer (Swagger): http://localhost:8000/docs*

3. **Start Frontend (Vite)**:
   ```bash
   cd frontend
   bun install
   bun run dev
   ```
   *Frontend application: http://localhost:5173*

---

## Running with Docker

```bash
docker compose up --build
```
- Orchestrates three containers:
  - `db`: PostgreSQL 16 with health check (`pg_isready`).
  - `backend`: FastAPI app waiting on healthy `db`.
  - `frontend`: Vite dev server forwarding `/api` to `http://backend:8000`.
- Persistent volumes:
  - `pgdata`: Keeps database records across restarts.
  - `presence_data`: Caches the ~500 MB InsightFace model in `/app/data/`.

---

## Automated Test Suites

Always run the full test suite when modifying database queries, API contracts, or face matching logic:

```powershell
# Backend pytest suite (covers DB operations, APIs, matching logic, edge cases)
cd backend
uv run pytest

# Frontend test suite (covers API client, model service contracts, localStorage)
cd frontend
bun test
```

---

## Key Architecture Decisions

### 1. Hybrid AI Face Recognition Engine
- **Local Mode**:
  - Model: `@vladmandic/face-api` (FaceNet / SSD MobileNet v1).
  - Embeddings: 128-dimensional float32 vectors generated entirely in-browser.
  - Privacy guarantee: Raw student photos remain strictly on client device; only 128-d float vectors are sent to `/api/attendance/match-embeddings` or `/api/students/enroll-embedding`.
  - Annotation: Bounding boxes and recognition badges are drawn directly onto an HTML5 `<canvas>`.
- **Cloud Mode**:
  - Model: InsightFace `buffalo_l` (ArcFace).
  - Embeddings: 512-dimensional float32 L2-normalized vectors.
  - Execution: Cached in `backend/data/` (~500 MB downloaded on first face recognition call).
  - Singleton: `_face_app` in `backend/services/face_service.py` initialized on first demand to prevent slow startup times.
  - Annotation: Rendered server-side using Pillow and returned as raw base64 PNG string.

### 2. Matching & Absence Calculation
- **Metric**: Cosine similarity via dot product on L2-normalized embeddings.
- **Thresholds**:
  - `THRESHOLD = 0.4` for Cloud Mode (512-d embeddings).
  - `threshold = 0.6` for Local Mode (128-d embeddings).
- **1-to-1 Match Enforcement**: Greedy match ensures no single enrolled student is assigned to multiple detected faces in the same photograph.
- **Absence Computation**: Backend takes the set of all students enrolled in the specified class and subtracts recognized IDs, recording remaining students as `absent`.

### 3. Database & Embeddings Storage
- **Engine**: PostgreSQL 16 with `psycopg-pool.ConnectionPool` (min 1, max 10 connections).
- **Zero ORM**: Standard SQL queries with `%s` parameterization for performance and predictability.
- **Schema**:
  - `students`: `id`, `name`, `roll_number` (UNIQUE), `class_name`, `model_type` (`'faceapi'` or `'insightface'`), `face_embedding` (`BYTEA`), `enrolled_at`.
  - `attendance_sessions`: `id`, `class_name`, `attendance_date`, `photo_hash`, `total_faces`, `recognized_count`, `unknown_count`, `created_at`.
  - `attendance_records`: `id`, `session_id` (FK cascade), `student_id` (FK set null), `status` (`'present'` | `'absent'`), `similarity`, `face_index`.
- **Safe Embeddings Serialization**:
  - Encoded: `embedding.astype(np.float32).tobytes()` stored in `BYTEA`.
  - Decoded: `np.frombuffer(raw_bytes, dtype=np.float32)`.
  - **No `pickle`**: Arbitrary code execution vulnerability completely avoided.

### 4. API & Client Contracts
- **Endpoints**:
  - `POST /api/students/enroll`: Solo portrait image upload (Cloud mode).
  - `POST /api/students/enroll-embedding`: JSON embedding enrollment (Local mode).
  - `GET /api/students?class_name=`: List enrolled students.
  - `DELETE /api/students/{id}`: Delete student.
  - `POST /api/attendance/process`: Group photo upload (Cloud mode).
  - `POST /api/attendance/match-embeddings`: JSON vector list matching (Local mode).
  - `GET /api/attendance/history?class_name=`: Retrieve session history.
  - `GET /api/attendance/sessions/{id}`: Detailed session report.
  - `GET /api/attendance/export?session_id=...`: Stream attendance CSV.
- **CSV Format**: Columns `[Name, Roll Number, Class, Date, Status]` covering both Present and Absent students.

---

## Common Development Tasks

### Changing Similarity Thresholds
- For Cloud mode: Edit `THRESHOLD` in `backend/services/face_service.py` (default `0.4`).
- For Local mode: Edit threshold check in `match_embeddings()` in `backend/services/face_service.py` (default `0.6` for `<=128-d`).

### Adding a New API Route
1. Define the endpoint in `backend/routers/students.py` or `backend/routers/attendance.py`.
2. Add corresponding database queries in `backend/database.py`.
3. Add client method in `frontend/src/api.js`.
4. Add backend pytest in `backend/tests/` and frontend test in `frontend/test/`.

### Adding a New Frontend Page / Component
1. Create page component in `frontend/src/pages/`.
2. Register route and navigation link in `frontend/src/App.jsx`.
3. Use `useModel()` hook from `frontend/src/context/ModelContext.jsx` if behavior depends on Local/Cloud mode.

### Database Maintenance
- Schema updates: Add `CREATE TABLE IF NOT EXISTS` or `CREATE INDEX IF NOT EXISTS` in `database.py:init_db()`.
- Wiping local database: Run `docker compose down -v` to reset the PostgreSQL `pgdata` volume.

---

## What NOT to Do

- **Never use `pickle` for embedding storage**: Always use `np.ndarray.tobytes()` and `np.frombuffer()` for security.
- **Never add an ORM (SQLAlchemy, Tortoise, etc.)**: Direct parameterized PostgreSQL queries with `psycopg` connection pooling are intentional and high-performance.
- **Never mix embedding dimensions**: Ensure 128-d (face-api.js) and 512-d (InsightFace) vectors are isolated by `model_type` and dimension checks before computing dot products.
- **Never upload group photos to the server in Local Mode**: The privacy guarantee requires that client-side inference keeps images on the user's machine.
- **Never call `FaceAnalysis.get()` outside of `face_service.py`**: Keep model inference centralized within the singleton service.
