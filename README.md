# Presence

AI-powered classroom attendance via face recognition. Take a group photo → every enrolled student is automatically marked present.

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green) ![React](https://img.shields.io/badge/React-18-61DAFB) ![InsightFace](https://img.shields.io/badge/InsightFace-buffalo__l-orange)

---

## How it works

1. **Enroll** each student once with a solo portrait photo
2. **Take attendance** by uploading any group photo of the class
3. The app detects every face, matches each one against enrolled students, and returns an annotated image plus a results table
4. **Export** a CSV attendance sheet with one click

Handles 70+ students. Recognition takes ~1–2 seconds on CPU.

---

## Requirements

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | [python.org](https://www.python.org/downloads/) |
| uv | latest | `pip install uv` or [docs.astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org/) |

> **Docker alternative**: If you have Docker Desktop installed you can skip Python/Node entirely — see [Running with Docker](#running-with-docker).

---

## Quick Start (Windows)

```powershell
.\run.ps1
```

That's it. The script:
1. Installs all Python and Node dependencies (first run only — takes a few minutes)
2. Opens the **backend** in one terminal window on port 8000
3. Opens the **frontend** in another terminal window on port 5173

Then open **http://localhost:5173** in your browser.

> **First face recognition call** downloads the InsightFace `buffalo_l` model (~500 MB) into `backend/data/`. This happens once and is cached — subsequent runs are instant.

---

## Manual Start

If you prefer to run the servers yourself:

**Terminal 1 — Backend**
```bash
cd backend
uv sync          # install Python packages (first time only)
uv run uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm install      # install Node packages (first time only)
npm run dev
```

- API docs (Swagger UI): http://localhost:8000/docs
- App: http://localhost:5173

---

## Running with Docker

```bash
docker compose up --build
```

- First build takes several minutes (downloads Python/Node images + all packages)
- The `backend/data/` folder is mounted as a volume, so your database and the face recognition model cache survive container restarts
- To stop: `docker compose down`

---

## Usage Guide

### 1. Enroll Students

Go to the **Enroll** page. For each student, fill in:
- **Name** — full name
- **Roll Number** — must be unique (e.g. `CS101`)
- **Class** — e.g. `10-A`
- **Photo** — a clear, well-lit solo portrait (one face only)

Click **Enroll Student**. The app detects the face, computes a mathematical fingerprint (embedding), and saves it.

Tips for good enrollment photos:
- Face clearly visible, not at an extreme angle
- Good lighting — avoid harsh shadows
- No sunglasses or face coverings

### 2. View / Manage Students

The **Students** page lists all enrolled students. Use the class filter to narrow by class. Click **Delete** to remove a student.

### 3. Take Attendance

Go to the **Attendance** page:
1. Enter the **class name** (e.g. `10-A`)
2. Set the **date** (defaults to today)
3. Upload a **group photo** of the class
4. Click **Process Attendance**

The app will:
- Detect all faces in the photo
- Match each face against enrolled students
- Return an annotated image (green box = recognized, red box = unknown)
- Show a results table (name, roll number, status)

### 4. Export CSV

After processing, click **Export CSV** to download a spreadsheet with columns:

| Name | Roll Number | Class | Date | Status |
|------|-------------|-------|------|--------|
| Arjun Sharma | CS101 | 10-A | 2026-03-05 | Present |

Only recognized (present) students are included.

---

## Project Structure

```
presence/
├── run.ps1                  Windows launcher script
├── docker-compose.yml
├── backend/
│   ├── pyproject.toml       Python dependencies
│   ├── main.py              FastAPI app entry point
│   ├── database.py          SQLite operations
│   ├── routers/
│   │   ├── students.py      Enroll / list / delete students
│   │   └── attendance.py    Process photo / export CSV
│   ├── services/
│   │   ├── face_service.py  Face detection + recognition (InsightFace)
│   │   └── image_service.py Draw boxes on photo (Pillow)
│   └── data/                Database + model cache (auto-created)
└── frontend/
    ├── src/
    │   ├── api.js           All API calls
    │   ├── App.jsx          Router + navigation
    │   └── pages/
    │       ├── EnrollPage.jsx
    │       ├── StudentsPage.jsx
    │       └── AttendancePage.jsx
    └── vite.config.js
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/students/enroll` | Enroll a student (multipart: name, roll_number, class_name, photo) |
| `GET` | `/api/students` | List students (`?class_name=10-A` to filter) |
| `DELETE` | `/api/students/{id}` | Remove a student |
| `POST` | `/api/attendance/process` | Process group photo (multipart: class_name, photo, attendance_date) |
| `GET` | `/api/attendance/export` | Download CSV (`?class_name=&attendance_date=&roll_numbers=`) |

Full interactive docs at **http://localhost:8000/docs**.

---

## Troubleshooting

**"No face detected" on enrollment**
- Use a well-lit, front-facing portrait
- Make sure only one person is in the frame

**Students not recognized in group photo**
- Ensure the student's enrollment photo is clear and recent
- The recognition threshold is set to 0.4 (cosine similarity). If too many faces are "Unknown", it can be lowered in `backend/services/face_service.py` → `THRESHOLD`

**First run is very slow**
- The InsightFace model (~500 MB) downloads on the first face recognition call. Subsequent calls load from cache in under a second.

**`uv` command not found**
- Install uv: `pip install uv` or follow https://docs.astral.sh/uv/getting-started/installation/

**Port already in use**
- Something else is running on port 8000 or 5173. Stop it, or change the port in `run.ps1` and `vite.config.js`.

---

## Tech Stack

| Concern | Choice | Why |
|---------|--------|-----|
| Face recognition | InsightFace (ArcFace buffalo_l) | 99.4% LFW accuracy, works on CPU, installs on Windows without C++ compiler |
| Similarity metric | Cosine similarity on 512-d embeddings | Standard for ArcFace; fast and accurate |
| Database | SQLite (stdlib) | Zero setup; embeddings stored as binary BLOBs |
| Backend framework | FastAPI + uvicorn | Fast, modern, auto-generates API docs |
| Package manager | uv | Much faster than pip |
| Image annotation | Pillow | Lightweight, no display required |
| Frontend | React + Vite + Tailwind CSS | Fast dev experience, minimal boilerplate |
