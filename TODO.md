## Phase 0: Quick Fixes (1–2 hours)

Small, high-impact changes that close the most obvious gaps.

### 0.1 — Replace `pickle` with `numpy.tobytes()`

> ⚠️ **Security issue.** `pickle.loads()` on data from disk is an arbitrary code execution vulnerability. If anyone modifies `presence.db`, unpickling the BLOB column can run arbitrary Python. This is one of the first things a security-conscious reviewer will flag.

**Current** ([database.py:L56](file:///C:/Users/arkma/Documents/GitHub/presence/backend/database.py#L56)):
```python
blob = pickle.dumps(embedding)                    # save
embedding = pickle.loads(d["face_embedding"])      # load
```

**Target:**
```python
blob = embedding.astype(np.float32).tobytes()                      # save: 512 × 4 bytes = 2048 bytes
embedding = np.frombuffer(d["face_embedding"], dtype=np.float32)   # load: safe, no code execution
```

**Files to change:**
- [x] `backend/database.py` — `insert_student()` (line 56), `get_all_students_with_embeddings()` (line 99)
- [x] Remove `import pickle`
- [x] Write a one-time migration script (`scripts/migrate_pickle_to_bytes.py`) that reads existing BLOBs with pickle and re-writes them with tobytes, so existing databases aren't broken


### 0.2 — Persist Attendance in the Database

> ❗ **The single biggest architectural gap.** Right now, attendance results exist only in-memory — close the browser tab and they're gone forever. The CSV export relies on the client passing roll numbers back via query string, which is fragile and stateless.

**New tables:**
```sql
CREATE TABLE attendance_sessions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    class_name       TEXT    NOT NULL,
    attendance_date  TEXT    NOT NULL,
    photo_hash       TEXT,                  -- SHA-256 of uploaded photo (dedup)
    total_faces      INTEGER NOT NULL,
    recognized_count INTEGER NOT NULL,
    unknown_count    INTEGER NOT NULL,
    created_at       TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE attendance_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES attendance_sessions(id) ON DELETE CASCADE,
    student_id      INTEGER REFERENCES students(id) ON DELETE SET NULL,
    status          TEXT    NOT NULL CHECK (status IN ('present', 'absent')),
    similarity      REAL,                   -- cosine similarity score (NULL for absent)
    face_index      INTEGER,                -- which face in the photo (NULL for absent)
    UNIQUE(session_id, student_id)
);
```

**Changes:**
- [x] `backend/database.py` — Add `create_attendance_session()`, `insert_attendance_records()`, `get_attendance_history()`, `get_session_detail()`
- [x] `backend/routers/attendance.py` — After `match_group_photo()` succeeds, persist the session and all records (both present AND absent students)
- [x] `backend/routers/attendance.py` — Rewrite `/export` to pull from the DB instead of from query-string roll numbers
- [x] New endpoint: `GET /api/attendance/history?class_name=10-A` — returns past sessions
- [x] New endpoint: `GET /api/attendance/sessions/{id}` — returns full detail for one session

### 0.3 — Track Absences

Currently the system only outputs *present* students. The delta is trivial to compute:

```python
enrolled_ids = {s["id"] for s in all_students}
recognized_ids = {r["student_id"] for r in records if r["status"] == "present"}
absent_ids = enrolled_ids - recognized_ids
```

- [x] Include absent students in the results response (status: `"absent"`)
- [x] Include absent students in the CSV export
- [x] Show absent students in the frontend results table (greyed out or red)

## Phase 1: Camera Capture + Model Selection (3–5 days)

### 1.1 — Camera Capture via `getUserMedia`

Let the user snap a photo directly from their laptop webcam/phone camera instead of uploading a file.

**Implementation:**
- [ ] Add a `<video>` element + "Start Camera" button that calls `navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })`
- [ ] "Capture" button snapshots the video to a `<canvas>`, converts to `Blob` via `canvas.toBlob()`
- [ ] Feed the `Blob` into the same upload flow (either enrollment or attendance)
- [ ] Add a toggle: "Upload File" vs "Use Camera"
- [ ] Handle permissions gracefully (camera denied, not available, etc.)

**Apply to both pages:**
- [ ] `EnrollPage.jsx` — solo portrait capture for enrollment
- [ ] `AttendancePage.jsx` — group photo capture for attendance

### 1.2 — Local Model (Browser-Side Face Recognition)

Add [face-api.js](https://github.com/justadudewhohacks/face-api.js) as a client-side alternative to the server-side InsightFace pipeline.

**Why face-api.js:**
- ~6 MB of model files (vs 500 MB for InsightFace)
- Runs entirely in the browser via TensorFlow.js / WebAssembly
- 99.2% LFW accuracy (vs 99.4% for ArcFace) — very close
- No server compute needed — photos never leave the device

**Architecture:**

```
┌─────────────────────────────────────────────┐
│  Browser (Local Mode)                        │
│  face-api.js loads SSD MobileNet + FaceNet  │
│  Detects faces → generates 128-d embeddings │
│  Sends ONLY embeddings to backend           │
└──────────────┬──────────────────────────────┘
               │  POST /api/attendance/match-embeddings
               │  Body: { embeddings: [[0.1, 0.2, ...], ...], class_name, date }
               ▼
┌─────────────────────────────────────────────┐
│  Backend (Thin matching API)                 │
│  Loads stored embeddings from DB            │
│  Runs np.dot() matching                     │
│  Returns results (no image processing)      │
└─────────────────────────────────────────────┘
```

> ℹ️ face-api.js produces **128-d** embeddings while InsightFace produces **512-d** embeddings. These are **not interchangeable** — a student enrolled with one model must be matched with the same model. The DB needs a `model_type` column on the `students` table, and enrollment must record which model generated the embedding.

**Implementation:**
- [ ] `npm install face-api.js` in frontend
- [ ] Create `frontend/src/services/localFaceService.js` — load models, detect, compute embeddings
- [ ] Host the face-api.js model weights as static assets in `frontend/public/models/`
- [ ] Add `model_type TEXT NOT NULL DEFAULT 'insightface'` column to `students` table
- [ ] New backend endpoint: `POST /api/attendance/match-embeddings` — accepts raw embeddings instead of an image
- [ ] New backend endpoint: `POST /api/students/enroll-embedding` — accepts a pre-computed embedding instead of a photo
- [ ] Adapt `face_service.py` matching logic to handle both 128-d and 512-d embeddings (filter students by model_type)
- [ ] Frontend: annotate the image client-side using `<canvas>` drawing (since the backend never sees the image in local mode)

---

### 1.3 — Model Selector UI

- [ ] Add a toggle/dropdown in the nav or settings: **"Recognition Engine: Local (Private) | Cloud (Accurate)"**
- [ ] Persist the choice in `localStorage`
- [ ] When "Local" is selected, enrollment and attendance use face-api.js in the browser
- [ ] When "Cloud" is selected, use the current server-side InsightFace flow
- [ ] Show a brief explainer: *"Local mode runs entirely on your device — photos are never uploaded. Cloud mode uses a more accurate model on the server."*

---

## Phase 2: Database — The "Real App" Path

### The Database Discussion
#### SQLite (what you have now)

```
Type:       Embedded (runs inside your Python process, no server)
Storage:    Single file on disk (presence.db)
Setup:      Zero — it's in Python's standard library
```

**What it's great at:**
- Local development, prototypes, desktop/mobile apps
- Read-heavy workloads (it's *extremely* fast for reads)
- Single-user applications

**What kills it in production:**
- **One writer at a time.** SQLite uses a file-level lock. If two teachers upload group photos simultaneously, one request blocks until the other finishes. For a classroom app this is probably fine — for anything beyond ~10 concurrent users, it's a problem.
- **Ephemeral cloud filesystems.** Render, Heroku, Fly.io, Railway — all of them wipe the filesystem on every deploy, restart, or idle spin-down. Your entire database vanishes. You'd need a persistent disk (usually a paid add-on) to keep SQLite alive.
- **No remote access.** You can't connect to a SQLite database from another machine. There's no concept of users, permissions, or network access.

**Verdict:** Perfect for local dev. Problematic for cloud hosting. Incompatible with multi-user production.

---

#### PostgreSQL (the standard recommendation)

```
Type:       Client-server (runs as a separate process/service)
Storage:    Managed by the Postgres server
Setup:      Need to run a Postgres server (or use a managed service)
Free tiers: Supabase (500 MB), Neon (512 MB, serverless, fast wake-up),
            Render (256 MB — but expires after 30 days!)
```

**What it's great at:**
- **Everything a web app needs.** Concurrent reads/writes, transactions, constraints, indexes, JSON columns, full-text search, window functions.
- **Extensions.** `pgvector` adds native vector similarity search — you could store and query face embeddings directly in Postgres instead of loading them all into memory for `np.dot()`. This is genuinely relevant to your project.
- **Universal support.** Every hosting platform, every ORM, every language has first-class Postgres support. It's the "default right answer" for web applications.
- **Battle-tested at scale.** Instagram, Notion, Reddit, Supabase itself — all built on Postgres.

**What's harder:**
- More setup than SQLite (need a running server or managed instance)
- Schema migrations become important (you'll want Alembic or a migration tool)
- Slightly more complex queries for simple CRUD

**When to choose it:** When you're building a "real" web application that will be hosted in the cloud, have multiple users, or need to persist data reliably. **This is the right default choice for Presence in production.**

---

#### MongoDB

```
Type:       Document database (stores JSON-like "documents" in "collections")
Storage:    Managed by MongoDB server
Setup:      Self-host or MongoDB Atlas
Free tier:  Atlas M0 — 512 MB storage, shared cluster, max 500 connections
```

**What it's great at:**
- **Flexible schemas.** No migrations — just store whatever JSON shape you want. Great for rapidly prototyping or when your data model is genuinely document-shaped (nested, hierarchical, varies per record).
- **Content management, event logs, IoT data** — use cases where each record is self-contained.

**What makes it a bad fit for Presence:**
- Attendance data is **inherently relational**. A student belongs to a class. An attendance record belongs to a session and references a student. These are foreign key relationships — the bread and butter of relational databases. In Mongo, you'd either denormalize (duplicate data everywhere) or do application-level joins (slow, error-prone).
- No native vector similarity search (you'd still need to load all embeddings into Python and do `np.dot()`).
- Transactions across collections are supported but awkward.

**Verdict:** Wrong tool for this job. Mongo shines for content-heavy, schema-fluid applications — not for structured relational data with foreign keys.

---

#### Firebase (Firestore + Auth + Storage)

```
Type:       Backend-as-a-Service (BaaS) — Google
Storage:    Firestore (document DB) + Cloud Storage (files)
Setup:      Create a Firebase project, add the SDK
Free tier:  Spark plan — 1 GiB Firestore, 50K reads/day, 20K writes/day,
            50K auth MAUs. NOTE: Cloud Storage was REMOVED from Spark
            plan in late 2024 — requires Blaze (pay-as-you-go) plan.
```

**What it's great at:**
- **Everything bundled.** Database + auth + hosting + serverless functions, all from one SDK. You could theoretically eliminate your entire FastAPI backend.
- **Realtime sync.** Firestore pushes changes to all connected clients instantly. Great for chat apps, dashboards, collaborative tools.
- **Auth is trivial.** Google, GitHub, email/password sign-in — a few lines of code.

**What makes it tricky for Presence:**
- **No server-side Python ML.** You can't run InsightFace/numpy/scipy in a Firebase Cloud Function easily.
- **Document database limitations.** Same relational pain as Mongo — attendance sessions referencing students requires manual denormalization or multiple queries.
- **Vendor lock-in.** Your entire backend is coupled to Google's proprietary APIs. Migrating away is a rewrite.
- **Costs scale unpredictably.** You pay per document read/write. A group photo matching 40 students = 40+ reads. This adds up.

**Verdict:** Makes sense if you fully commit to client-side ML (face-api.js in browser) and want zero backend code. Building your own backend with Postgres demonstrates more engineering depth than wiring up Firebase SDK calls.

---

#### Supabase (the "open-source Firebase" on Postgres)

```
Type:       BaaS built on PostgreSQL — open source
Storage:    Postgres DB + S3-compatible object storage
Setup:      Create a Supabase project (or self-host)
Free tier:  500 MB DB, 1 GB file storage, 50K auth MAUs,
            500K Edge Function invocations, 2 active projects.
            Projects pause after 1 week of inactivity (manually unpause).
```

**What it's great at:**
- **Best of both worlds.** Firebase-like DX (auth, storage, realtime subscriptions, auto-generated REST API) but your data lives in standard Postgres. No vendor lock-in — you can `pg_dump` and move anywhere.
- **pgvector built-in.** Store face embeddings as `vector(512)` columns and do similarity search directly in SQL: `SELECT * FROM students ORDER BY embedding <=> $query_embedding LIMIT 1`.
- **Row Level Security (RLS).** Postgres policies that enforce "Teacher A can only see their own students" at the database level.
- **Auth + JWT.** Built-in auth that issues JWTs, which your FastAPI backend can verify.

**Verdict:** If you want the "real app with users" path and don't want to build auth from scratch, Supabase is the most pragmatic choice. You keep all the Postgres benefits and get auth/storage for free.

---

#### Turso (SQLite at the edge — worth mentioning)

```
Type:       Managed libSQL (SQLite-compatible) with edge replication
Storage:    5 GB total, up to 100 databases
Free tier:  500M row reads/month, 10M row writes/month, embedded replicas
            Zero cold starts. No inactivity pausing.
```

**Why it's interesting:** You could keep your existing SQLite code almost unchanged, and Turso handles replication + persistence in the cloud. The "embedded replica" feature syncs a local SQLite copy to your server for sub-millisecond reads. No cold starts, no ephemeral filesystem issues.

**Verdict:** Compelling if you want to stay on SQLite's familiar turf while getting cloud persistence. Less mainstream than Postgres (fewer interviewers will know it), but technically very elegant.

---

#### Quick-Reference Comparison

| | SQLite | PostgreSQL | MongoDB | Firebase | Supabase | Turso |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Relational data** | ✅ | ✅✅✅ | ❌ | ❌ | ✅✅✅ | ✅ |
| **Vector search** | ❌ | ✅ (pgvector) | ❌ | ❌ | ✅ (pgvector) | ❌ |
| **Concurrent writes** | ❌ | ✅✅✅ | ✅✅ | ✅✅ | ✅✅✅ | ✅ |
| **Cloud hosting** | ❌ | ✅✅✅ | ✅✅ | ✅✅✅ | ✅✅✅ | ✅✅✅ |
| **Built-in auth** | ❌ | ❌ | ❌ | ✅✅✅ | ✅✅✅ | ❌ |
| **Vendor lock-in** | None | None | Low | **High** | Low | Low |
| **Free tier durability** | N/A | Neon/Supabase ∞ | Atlas ∞ | Spark ∞ | ∞ (with pausing) | ∞ |

---

#### Recommendation for Presence

**Just use Postgres everywhere.** No dual-mode, no abstraction layer. You already have Docker — add a Postgres container to `docker-compose.yml` for local dev, point at Supabase or Neon in production. One database, one codebase, zero complexity.

Why not keep SQLite for local dev? Because maintaining two database implementations means two sets of SQL dialects, two sets of bugs, two things to test. The abstraction layer itself (abstract base classes, factory functions, two implementations) adds more code than the actual database logic. It's not worth it.

---

### How Big Are Embeddings, Really?

| Model | Dimensions | Bytes per embedding | Full student row |
|:------|:---:|:---:|:---:|
| InsightFace (ArcFace) | 512 × float32 | **2,048 bytes (2 KB)** | ~2.2 KB |
| face-api.js (FaceNet) | 128 × float32 | **512 bytes (0.5 KB)** | ~0.7 KB |

An attendance record (session_id, student_id, status, similarity) is ~75 bytes. A full school year of attendance for one class of 40 students × 180 days = **540 KB**.

These are tiny. Storage is never your bottleneck.

### How Many Students Fit in Each Free Tier?

| Service | Free Storage | Students (InsightFace) | Students (face-api.js) | School-years of attendance* |
|:--------|:---:|:---:|:---:|:---:|
| **Supabase** | 500 MB | ~227,000 | ~714,000 | ~900 |
| **Neon** | 512 MB | ~232,000 | ~731,000 | ~920 |
| **MongoDB Atlas** | 512 MB | ~232,000 | ~731,000 | ~920 |
| **Firebase Firestore** | 1 GiB | ~465,000 | ~1.4M | ~1,800 |
| **Turso** | 5 GB | ~2.2M | ~7.1M | ~9,000 |

\* *One class of 40 students × 180 school days.*

A school district with 10,000 students uses ~22 MB of embedding storage. You could run for centuries on any free tier. The real constraints are **compute hours** (Neon: 100 CU-hrs/month), **inactivity pausing** (Supabase: 1 week, Neon: 5 min), and **connection limits** (Atlas: 500) — not disk.

---

### 2.1 — Switch to PostgreSQL

No abstraction layer. Just replace `sqlite3` calls with `psycopg` (or `asyncpg`) directly in `database.py`.

**Local dev** — add Postgres to `docker-compose.yml`:
```yaml
services:
  db:
    image: postgres:16
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: presence
      POSTGRES_USER: presence
      POSTGRES_PASSWORD: presence
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

**Production** — set `DATABASE_URL` env var pointing to Supabase or Neon (both free, both permanent).

**Tasks:**
- [ ] Add `postgres` service to `docker-compose.yml`
- [ ] `pip install psycopg[binary]` (or add to `pyproject.toml`)
- [ ] Rewrite `database.py` to use `psycopg` instead of `sqlite3` — the queries are almost identical, just swap `?` placeholders for `%s` and `AUTOINCREMENT` for `SERIAL`
- [ ] Read `DATABASE_URL` from env (with a sensible default for local Docker: `postgresql://presence:presence@localhost:5432/presence`)
- [ ] Use connection pooling (`psycopg_pool.ConnectionPool`) instead of opening a new connection per call
- [ ] Update `run.ps1` to start Postgres via `docker compose up db -d` before launching the backend

### 2.2 — PostgreSQL Schema

```sql
CREATE TABLE students (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    roll_number     TEXT NOT NULL UNIQUE,
    class_name      TEXT NOT NULL,
    model_type      TEXT NOT NULL DEFAULT 'insightface',  -- 'insightface' | 'faceapi'
    face_embedding  BYTEA NOT NULL,                       -- raw float32 bytes (2 KB per InsightFace embedding)
    enrolled_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE attendance_sessions (
    id               SERIAL PRIMARY KEY,
    class_name       TEXT NOT NULL,
    attendance_date  DATE NOT NULL,
    photo_hash       TEXT,
    total_faces      INTEGER NOT NULL,
    recognized_count INTEGER NOT NULL,
    unknown_count    INTEGER NOT NULL,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE attendance_records (
    id              SERIAL PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES attendance_sessions(id) ON DELETE CASCADE,
    student_id      INTEGER REFERENCES students(id) ON DELETE SET NULL,
    status          TEXT NOT NULL CHECK (status IN ('present', 'absent')),
    similarity      REAL,
    face_index      INTEGER,
    UNIQUE(session_id, student_id)
);
```

**Stretch goal — pgvector:**
```sql
-- Replace BYTEA with native vector type
ALTER TABLE students ADD COLUMN embedding vector(512);
-- Then similarity search becomes a single SQL query:
SELECT *, embedding <=> $query AS distance FROM students ORDER BY distance LIMIT 1;
```

This eliminates the need to load all embeddings into Python memory — the database handles similarity search natively.

---

## Phase 3: Authentication (2–3 days)

- [ ] Use Supabase's built-in auth (email/password, Google OAuth)
- [ ] Supabase issues JWTs automatically — verify them in FastAPI with `python-jose`
- [ ] Row Level Security policies enforce data isolation at the DB level

## Phase 4: Test Suite (2–3 days)

### 4.1 — Backend Tests (pytest)

```
backend/
└── tests/
    ├── conftest.py           # fixtures: test DB, mock face_service
    ├── test_database.py      # CRUD operations, constraints, migrations
    ├── test_students_api.py  # enrollment, listing, deletion via HTTP
    ├── test_attendance_api.py # processing, history, CSV export via HTTP
    └── test_face_service.py  # threshold boundaries, edge cases (mocked)
```

**Key tests to write:**
- [x] `test_enroll_student` — happy path, returns student ID
- [x] `test_enroll_duplicate_roll_number` — returns HTTP 409
- [x] `test_enroll_no_face` — returns HTTP 400 with message
- [x] `test_enroll_multiple_faces` — returns HTTP 400 with message
- [x] `test_list_students_by_class` — filter works correctly
- [x] `test_delete_student` — deletes and returns 200; deleting again returns 404
- [x] `test_matching_above_threshold` — similarity 0.41 → recognized
- [x] `test_matching_below_threshold` — similarity 0.39 → unknown
- [x] `test_csv_export_format` — correct headers, correct data
- [x] `test_attendance_persistence` — session and records saved to DB

**Test strategy:** Mock `face_service.get_face_app()` in API tests (don't download the 500 MB model in CI). Use a temporary Postgres test database (or testcontainers-python to spin up a disposable Postgres container per test run). FastAPI's `TestClient` for HTTP-level tests.

### 4.2 — Frontend Tests (vitest)

- [ ] `npm install -D vitest @testing-library/react @testing-library/jest-dom`
- [ ] `test/api.test.js` — mock `fetch`, verify correct URLs and payloads
- [ ] `test/EnrollPage.test.jsx` — form validation, submit flow
- [ ] `test/AttendancePage.test.jsx` — file upload, results rendering

### 4.3 — CI Pipeline (GitHub Actions)

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: cd backend && uv sync
      - run: cd backend && uv run pytest -v
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: cd frontend && npm ci && npm test
```

---

## Phase 5: Deployment on Render (1 day)

### Free-Tier Architecture

```
┌──────────────────────┐     ┌──────────────────────┐
│  Render Static Site   │     │  Render Web Service   │
│  or Vercel (free)     │     │  Backend (FastAPI)     │
│  Frontend (React)     │────▶│  Free (512 MB RAM)     │
│  100 GB bandwidth     │     │  750 hrs/month         │
└──────────────────────┘     └────────┬───────────────┘
                                      │
                              ┌───────▼───────────────┐
                              │  Supabase or Neon      │
                              │  Free PostgreSQL       │
                              │  500–512 MB storage    │
                              └───────────────────────┘
```

> ⚠️ **RAM constraint.** The backend free tier has 512 MB RAM. InsightFace alone loads ~500 MB+ into memory. **Cloud mode (server-side face recognition) will not work on the free tier.** The deployment must default to local mode (face-api.js in browser), where the backend is a thin CRUD + matching API using ~50 MB RAM.

> ⚠️ **Don't use Render's free PostgreSQL.** It expires and is permanently deleted after 30 days. Use **Supabase** (500 MB, pauses after 1 week inactivity but doesn't delete) or **Neon** (512 MB, scales to zero after 5 min, no deletion).

**Tasks:**
- [ ] Add `render.yaml` (Infrastructure as Code for Render)
- [ ] Build step: `cd frontend && npm run build` → deploy as static site (or use Vercel for 100 GB free bandwidth)
- [ ] Backend: configure `DATABASE_URL` env var pointing to Supabase/Neon Postgres
- [ ] Set `PYTHON_VERSION=3.11` in Render env
- [ ] Strip InsightFace/ONNX from production requirements (optional `[cloud]` dependency group in `pyproject.toml`)
- [ ] Add health check endpoint: `GET /api/health` → `{ "status": "ok" }`
- [ ] Handle Render's spin-down behavior: free services sleep after 15 min of inactivity, cold start takes ~50–60s. Consider a periodic ping from the frontend or an UptimeRobot monitor during active hours.

## Phase 6: Stretch Goals (time permitting)

| Feature | What It Demonstrates |
|:--------|:---------------------|
| **Hungarian algorithm for matching** | Optimal bipartite assignment instead of greedy. `scipy.optimize.linear_sum_assignment`. |
| **Async inference** | `await run_in_threadpool(match_group_photo, ...)` — don't block the event loop. |
| **Configurable det_size** | Auto-scale InsightFace detection resolution based on image dimensions. Fixes missed faces in large photos.
| **Attendance analytics page** | Charts (e.g., recharts) showing attendance rates over time per student/class. Requires Phase 0.2. |
| **pgvector for similarity search** | Move embedding matching into the database. Eliminates loading all embeddings into Python memory. |
| **FAISS index** | Approximate nearest neighbor search for scaling to thousands of students. |
| **PWA / mobile support** | Service worker + manifest for installable app. Camera capture already works on mobile. |

## Suggested Order of Execution

```
Phase 0 (Quick Fixes)
  └─→ Phase 4.1 (Backend Tests)
       └─→ Phase 1.1 (Camera Capture)
            └─→ Phase 1.2–1.3 (Local Model + Selector)
                 └─→ Phase 2 (Database Abstraction)
                      └─→ Phase 3 (Authentication)
                           └─→ Phase 5 (Deploy to Render)
                                └─→ Phase 6 (Stretch Goals)
```