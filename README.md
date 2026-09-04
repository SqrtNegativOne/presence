# Presence

AI-powered classroom attendance via face recognition with a **hybrid recognition engine**:
- **Local Mode (Private)**: In-browser face detection and 128-d descriptor extraction using `@vladmandic/face-api`. Raw images never leave your device.
- **Cloud Mode (Accurate)**: High-precision 512-d ArcFace recognition on the server using `InsightFace` (`buffalo_l`).
- **Live Camera Support**: Capture portraits and group photos directly using your webcam or mobile camera.
- **Full Attendance & Absence Tracking**: Relational session persistence in PostgreSQL 16; auto-tracks both present and absent students and exports complete CSV sheets.

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green) ![React](https://img.shields.io/badge/React-18-61DAFB) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791) ![face-api.js](https://img.shields.io/badge/face--api.js-128--d-yellow) ![InsightFace](https://img.shields.io/badge/InsightFace-buffalo__l-orange)

---

## How It Works

1. **Choose Recognition Engine**: Toggle between **Local (Private)** (100% in-browser inference) and **Cloud (Accurate)** (InsightFace server inference) in the navigation bar.
2. **Enroll Students**: Enroll each student with a solo portrait photo or snap a snapshot directly using the live camera capture modal.
3. **Take Attendance**: Upload a group photo of the classroom or capture live with your webcam/camera.
4. **Instant Matching & Absence Detection**: The app detects faces, matches them against enrolled students, annotates the image, and automatically marks unmatched enrolled students as **Absent**.
5. **Persist & Export**: Every session is saved with historical records. Export complete CSV attendance sheets with one click.

---

## Requirements

| Tool | Version | Purpose | Install |
|------|---------|---------|---------|
| Python | 3.11+ | Backend runtime | [python.org](https://www.python.org/downloads/) |
| uv | latest | Fast Python package manager | [docs.astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/) |
| Bun | 1.0+ | Frontend package manager & runner | [bun.sh](https://bun.sh/) |
| Docker | latest | Runs PostgreSQL 16 database | [docker.com](https://www.docker.com/) |

---

## Quick Start (Windows)

```powershell
.\run.ps1
```

The script automatically:
1. Performs environment preflight checks (`uv`, `bun`, Docker)
2. Installs and syncs backend dependencies (`uv sync`) and frontend packages (`bun install`)
3. Starts the PostgreSQL container (`docker compose up db -d`)
4. Opens the **backend** (`http://localhost:8000/docs`) and **frontend** (`http://localhost:5173`) in separate terminal windows

> **First Cloud-mode call**: InsightFace downloads `buffalo_l` model weights (~500 MB) into `backend/data/`. This happens once and is cached for subsequent runs.

---

## Manual Start

If you prefer to start each service manually:

**1. Start PostgreSQL**:
```bash
docker compose up db -d
```
*Database runs on `localhost:5432` with user `presence`, password `presence`, database `presence`.*

**2. Terminal 1 — Backend**:
```bash
cd backend
uv sync
uv run uvicorn main:app --reload --port 8000
```
- API Docs (Swagger): http://localhost:8000/docs

**3. Terminal 2 — Frontend**:
```bash
cd frontend
bun install
bun run dev
```
- Web Application: http://localhost:5173

---

## Running Fully with Docker

To run all services (PostgreSQL, Backend, Frontend) in Docker:

```bash
docker compose up --build
```

- Persistent volume `pgdata` keeps your database records across container rebuilds.
- Persistent volume `presence_data` caches the InsightFace model in `/app/data/`.
- Stop all services with `docker compose down`.

---

## Usage Guide

### 1. Toggle Recognition Engine
Use the toggle in the navigation bar to select:
- **Local (Private)**: Inference runs in your browser via WebAssembly / TensorFlow.js. Your photos never leave your computer.
- **Cloud (Accurate)**: Inference runs on the FastAPI backend using InsightFace `buffalo_l` for maximum facial recognition accuracy.

### 2. Enroll Students
Go to the **Enroll** page. For each student:
- Enter **Name**, unique **Roll Number** (e.g. `CS101`), and **Class** (e.g. `10-A`).
- Provide a portrait by **uploading a photo** OR clicking **Use Camera** for live webcam/mobile capture.
- Click **Enroll Student**. The face embedding is computed and securely persisted.

### 3. Take Attendance
Go to the **Attendance** page:
1. Enter the **Class Name** and select the **Date** (defaults to today).
2. Choose your input method: **Upload Group Photo** or click **Use Camera** to capture the class live.
3. Click **Process Attendance**:
   - Faces are detected and matched against enrolled students in the class.
   - Identified students are marked **Present** (with green bounding boxes).
   - Unenrolled faces are tagged **Unknown** (with red bounding boxes).
   - Enrolled students who were not detected in the photo are automatically recorded as **Absent**.

### 4. Export CSV Report
Click **Export CSV** to download a spreadsheet with complete attendance records:

| Name | Roll Number | Class | Date | Status |
| :--- | :--- | :--- | :--- | :--- |
| Aarav Sharma | CS101 | 10-A | 2026-09-05 | Present |
| Priya Patel | CS102 | 10-A | 2026-09-05 | Absent |

Both present and absent students are recorded for seamless administrative reporting.

---

## Project Structure

```
presence/
├── run.ps1                         # Windows automated startup launcher
├── docker-compose.yml              # Multi-container orchestration (db, backend, frontend)
├── AGENTS.md                       # AI agent instructions and system specifications
├── README.md                       # Project documentation
├── TODO.md                         # Product roadmap and completed milestones
├── backend/
│   ├── pyproject.toml              # uv project definition and pytest configuration
│   ├── Dockerfile                  # Backend container image
│   ├── main.py                     # FastAPI application entry point, CORS, lifespan
│   ├── database.py                 # PostgreSQL 16 connection pooling & direct SQL queries
│   ├── routers/
│   │   ├── students.py             # Student enrollment and management endpoints
│   │   └── attendance.py           # Attendance processing, session history, and CSV export
│   ├── services/
│   │   ├── face_service.py         # InsightFace singleton, embedding extraction & matching
│   │   └── image_service.py        # Pillow image annotation (Cloud mode)
│   ├── tests/                      # Pytest suite (22 unit & integration tests)
│   └── data/                       # Local model cache for buffalo_l (~500 MB)
└── frontend/
    ├── package.json / bun.lock     # Bun frontend dependencies and lockfile
    ├── vite.config.js              # Vite dev server configuration & API proxy
    ├── public/models/              # Static model weights for face-api.js
    ├── src/
    │   ├── api.js                  # Centralized backend API client
    │   ├── App.jsx                 # Main layout and ModelSelector toggle
    │   ├── components/
    │   │   └── CameraCapture.jsx   # Live camera snapshot modal with countdown
    │   ├── context/
    │   │   └── ModelContext.jsx    # Model state ('local' | 'cloud') with localStorage persistence
    │   ├── services/
    │   │   └── localFaceService.js # In-browser face-api.js loader and canvas drawing
    │   └── pages/
    │       ├── EnrollPage.jsx      # Student enrollment (upload or camera)
    │       ├── StudentsPage.jsx    # Student roster listing and deletion
    │       └── AttendancePage.jsx  # Attendance workflow, session history, and CSV export
    └── test/                       # Frontend test suite (bun test)
```

---

## API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/students/enroll` | Enroll a student via photo upload (Cloud mode) |
| `POST` | `/api/students/enroll-embedding` | Enroll student via pre-computed embedding vector (Local mode) |
| `GET` | `/api/students` | List students (`?class_name=10-A` to filter) |
| `DELETE` | `/api/students/{id}` | Remove a student by ID |
| `POST` | `/api/attendance/process` | Process group photo upload with server inference (Cloud mode) |
| `POST` | `/api/attendance/match-embeddings` | Match client-side extracted embeddings (Local mode) |
| `GET` | `/api/attendance/history` | Retrieve past attendance sessions (`?class_name=` to filter) |
| `GET` | `/api/attendance/sessions/{id}` | Detailed session report with present and absent records |
| `GET` | `/api/attendance/export` | Download CSV (`?session_id=` or `?class_name=&attendance_date=`) |

Full interactive OpenAPI documentation available at **http://localhost:8000/docs**.

---

## Testing

```powershell
# Backend test suite (Pytest)
cd backend
uv run pytest

# Frontend test suite (Bun)
cd frontend
bun test
```

---

## Troubleshooting

**"No face detected" on enrollment**
- Use a well-lit, front-facing portrait.
- Make sure only one person is in the frame.

**Students not recognized in group photo**
- Ensure the student's enrollment portrait is clear and recent.
- For Cloud mode, the cosine similarity threshold is `0.4`. For Local mode, it is `0.6`. These can be adjusted in `backend/services/face_service.py`.

**First run is slow (Cloud Mode)**
- InsightFace downloads the `buffalo_l` model weights (~500 MB) on the first face recognition call. Subsequent requests load from cache in under a second.

**Docker database connection issues**
- Ensure Docker Desktop is running and start the database with `docker compose up db -d`.

---

## Tech Stack

| Concern | Technology | Why |
| :--- | :--- | :--- |
| **Local ML Engine** | `@vladmandic/face-api` (TF.js / WASM) | 128-d in-browser inference for zero-server-leakage privacy |
| **Cloud ML Engine** | InsightFace (ArcFace `buffalo_l`) | 99.4% LFW accuracy, 512-d embeddings, runs fast on CPU |
| **Backend API** | FastAPI + Uvicorn | Async Python 3.11+, high performance, automatic OpenAPI docs |
| **Database** | PostgreSQL 16 via `psycopg` (v3) + pool | Robust relational storage, connection pooling, zero ORM |
| **Embeddings Storage** | Raw float32 bytes (`BYTEA`) | Safe, high-performance binary storage (no pickle code execution risk) |
| **Frontend SPA** | React 18 + Vite + Tailwind CSS | Fast dev experience, reactive UI, clean styling |
| **Package Managers** | `uv` (Python) + `bun` (JavaScript) | Instant dependency resolution and execution |

