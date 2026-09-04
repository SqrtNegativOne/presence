Teachers upload a group photo → InsightFace detects and identifies every student → attendance is auto-marked and exportable as CSV.

## Stack
| Layer | Tech |
|-------|------|
| Backend | Python 3.11+, FastAPI, uvicorn, uv (package manager) |
| Face recognition | InsightFace `buffalo_l` (ArcFace), onnxruntime (CPU) |
| Database | SQLite via stdlib `sqlite3` — no ORM |
| Image annotation | Pillow |
| Logging | loguru |
| Frontend | React 18, Vite, Tailwind CSS v3, react-router-dom v6 |

## Directory Layout
```
presence/
├── run.ps1                     Windows launcher (opens 2 PowerShell windows)
├── docker-compose.yml
├── backend/
│   ├── pyproject.toml          uv dependencies
│   ├── main.py                 FastAPI app, CORS, lifespan
│   ├── database.py             All SQLite logic (init, CRUD)
│   ├── routers/
│   │   ├── students.py         POST /api/students/enroll, GET, DELETE /{id}
│   │   └── attendance.py       POST /api/attendance/process, GET /export
│   ├── services/
│   │   ├── face_service.py     InsightFace singleton + encode_single_face / match_group_photo
│   │   └── image_service.py    Pillow annotation -> base64 PNG
│   └── data/                   Auto-created; holds presence.db + model cache
└── frontend/
    ├── vite.config.js          Proxy /api -> $BACKEND_URL (default: localhost:8000)
    ├── src/
    │   ├── api.js              All fetch() calls in one place
    │   ├── App.jsx             BrowserRouter + nav
    │   └── pages/
    │       ├── EnrollPage.jsx
    │       ├── StudentsPage.jsx
    │       └── AttendancePage.jsx
```

## Running Locally
```powershell
# Simplest: one script opens both servers
.\run.ps1

# Manual:
cd backend && uv run uvicorn main:app --reload --port 8000
cd frontend && bun run dev
```
- Backend API explorer: http://localhost:8000/docs
- Frontend: http://localhost:5173

## Running with Docker
```bash
docker compose up --build
```
`backend/data/` is volume-mounted, so the database and model cache persist across rebuilds.

## Key Architecture Decisions

### Face Recognition
- **Model**: InsightFace `buffalo_l` — downloads ~500 MB on first face recognition call, cached in `backend/data/`
- **Singleton**: `_face_app` in `face_service.py` is initialized once at first use (not at startup) because loading takes ~5s
- **Embeddings**: 512-dimensional float32 numpy arrays, stored as `pickle.dumps()` BLOBs in SQLite
- **Matching**: cosine similarity; threshold is `THRESHOLD = 0.4` in `face_service.py` — tune this if needed (higher = stricter)
- **Enrollment**: must have exactly 1 face in photo or ValueError is raised

### Database
- No migration system — schema is created by `database.init_db()` via `CREATE TABLE IF NOT EXISTS`
- `get_all_students()` omits embeddings (for listing); `get_all_students_with_embeddings()` includes them (for matching)
- Unique constraint on `roll_number` — duplicate enrollment returns HTTP 409

### API / Frontend Contract
- Annotated image is returned as a raw base64 string (no `data:` prefix) — the frontend adds `data:image/png;base64,` in the `<img src>`
- CSV export uses `window.location.href` (browser download trigger), not fetch
- Vite proxies `/api` to the backend, so all frontend fetch calls use relative URLs like `/api/students`
- Docker uses `BACKEND_URL=http://backend:8000` env var to override the proxy target in `vite.config.js`

## Common Tasks

### Change the similarity threshold
Edit `THRESHOLD` in `backend/services/face_service.py`. Default is `0.4`.
- Too many unknowns → lower the threshold
- Wrong people being recognized → raise the threshold

### Add a new API endpoint
1. Add the route function in the appropriate router (`routers/students.py` or `routers/attendance.py`)
2. Add the corresponding fetch call in `frontend/src/api.js`
3. Use it in the relevant page component

### Add a new page
1. Create `frontend/src/pages/MyPage.jsx`
2. Add a `<Route>` in `App.jsx`
3. Add a `<NavLink>` in the nav bar in `App.jsx`

### Reset the database
Delete `backend/data/presence.db`. It will be recreated on next startup.

### Reset the InsightFace model cache
Delete the contents of `backend/data/` (except `presence.db`). The model re-downloads on next face recognition call.

## What NOT to Do
- Do not add an ORM (SQLAlchemy, etc.) — the plain sqlite3 queries are intentionally simple
- Do not switch the face recognition library — InsightFace was chosen specifically because it works on Windows without C++ compilation
- Do not change embeddings storage from pickle BLOBs without migrating existing data
- Do not use `app.get()` (InsightFace) outside of `face_service.py` — keep it in the singleton
