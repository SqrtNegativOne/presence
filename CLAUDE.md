Teachers sign in (Google or one-click demo), upload a group photo → a pluggable
recognizer detects and identifies their enrolled students → attendance is
auto-marked, persisted per teacher, and exportable as CSV.

## Stack
| Layer | Tech |
|-------|------|
| Backend | Python 3.11+, FastAPI, uvicorn, uv (package manager) |
| Auth | Google ID token (`google-auth`) → HS256 JWT (`pyjwt`) sessions stored in SQLite |
| Face recognition | Pluggable: InsightFace (`buffalo_l/s/sc`, ArcFace ONNX), OpenCV Haar, MediaPipe BlazeFace |
| Database | SQLite via stdlib `sqlite3` — no ORM |
| Image annotation | Pillow |
| Logging | loguru |
| Frontend | React 18, Vite, Tailwind CSS v3, react-router-dom v6, `@react-oauth/google` |

## Directory Layout
```
presence/
├── run.ps1
├── docker-compose.yml
├── backend/
│   ├── pyproject.toml
│   ├── .env.example
│   ├── main.py                  FastAPI app + lifespan + background demo seeder
│   ├── database.py              users, sessions, students, attendance_records
│   ├── seed_demo.py             Creates the demo user + 4 enrolled students
│   ├── auth/
│   │   ├── jwt.py               HS256 session tokens
│   │   ├── google.py            Google ID-token verification
│   │   └── dependencies.py      FastAPI `get_current_user` dependency
│   ├── recognizers/             Pluggable engines (one factory per name)
│   │   ├── base.py              `FaceRecognizer` ABC + `DetectedFace` dataclass
│   │   ├── registry.py          Lazy singleton registry + availability checks
│   │   ├── insightface_engine.py  buffalo_l / buffalo_s / buffalo_sc
│   │   ├── opencv_haar.py       Haar cascade + flat pixel embedding (fastest)
│   │   └── mediapipe_blaze.py   BlazeFace detector + flat pixel embedding
│   ├── routers/
│   │   ├── auth.py              POST /api/auth/google, /demo, /logout; GET /me
│   │   ├── recognizers.py       GET /api/recognizers, PUT /api/recognizers/preferred
│   │   ├── students.py          enroll/list/delete — scoped to the signed-in user
│   │   └── attendance.py        /process, /export, /demo-group-photo, /history
│   ├── services/
│   │   ├── face_service.py      Vectorized matcher + per-(user, recognizer) cache
│   │   └── image_service.py     Pillow annotation → base64 PNG
│   ├── demo_assets/             Synthetic faces (CC0) bundled for the demo user
│   │   ├── students/{alice,bob,carol,dave}.jpg
│   │   └── group/class.jpg      2×2 composite of the four demo students
│   └── data/                    Auto-created; SQLite DB + InsightFace model cache
└── frontend/
    ├── vite.config.js           Proxies /api → $BACKEND_URL
    ├── .env.example             VITE_GOOGLE_CLIENT_ID
    ├── package.json             Adds @react-oauth/google
    ├── src/
    │   ├── api.js               fetch() + Authorization: Bearer + 401 handling
    │   ├── App.jsx              Routes, RequireAuth, nav with sign-out
    │   ├── main.jsx             GoogleOAuthProvider + AuthProvider
    │   ├── auth/
    │   │   ├── AuthContext.jsx  user + token state
    │   │   └── RequireAuth.jsx  redirect-to-login wrapper
    │   └── pages/
    │       ├── LoginPage.jsx
    │       ├── EnrollPage.jsx
    │       ├── StudentsPage.jsx
    │       ├── AttendancePage.jsx   "Use sample →" button for demo users
    │       └── SettingsPage.jsx     Pick a recognizer engine
```

## Running Locally
```powershell
# Simplest: one script opens both servers
.\run.ps1

# Manual:
cd backend && uv run uvicorn main:app --reload --port 8000
cd frontend && npm install && npm run dev
```
Required env vars (copy `.env.example` and fill in):
- `PRESENCE_JWT_SECRET`  — random 48+ char string (sessions invalidated on change)
- `PRESENCE_GOOGLE_CLIENT_ID`  — from Google Cloud Console (frontend reads `VITE_GOOGLE_CLIENT_ID`)
- Both can be left blank in development — the demo button always works.

## Running with Docker
```bash
docker compose up --build
```
`backend/data/` is volume-mounted, so the DB and the InsightFace model cache
persist across rebuilds. Set OAuth env vars in a shell `.env` file next to
`docker-compose.yml` if you want Google sign-in.

## Key Architecture Decisions

### Auth
- Google ID token → `google.oauth2.id_token.verify_oauth2_token` → user upsert → HS256 JWT issued + row in `sessions` table.
- Every protected route uses `Depends(get_current_user)`, which validates the JWT *and* checks the `sessions` row (so logout truly revokes the token).
- The demo user is created on demand (POST `/api/auth/demo`) and gets the same kind of session token — no Google credentials needed.

### Face recognition (pluggable)
- `FaceRecognizer` ABC in `recognizers/base.py` returns `list[DetectedFace]` with an L2-normalized embedding.
- The registry instantiates each engine at most once (lazy), and remembers if construction failed — a missing optional dep (e.g. mediapipe) just hides that engine in the UI.
- **Embedding compatibility**: embeddings produced by different engines are not interchangeable. Each `students` row stores the `recognizer_name` it was encoded with, and the matcher only considers rows with the same recognizer.
- Default recognizer: `insightface_l` (most accurate). Switch via Settings.

### Vectorized matching (~500× faster than the original loop)
- All embeddings are L2-normalized at ingest, so cosine similarity is a plain matmul.
- Per-`(user_id, recognizer_name)` cache holds a pre-stacked `(M, D)` numpy matrix plus parallel metadata, so `/process` does NOT hit SQLite or unpickle anything in the hot path.
- The cache is invalidated whenever a student is inserted or deleted.

### Database
- No migration system — `init_db()` uses `CREATE TABLE IF NOT EXISTS` plus a small `PRAGMA table_info`-based check for the legacy single-user schema.
- All student/attendance data is scoped per user via `user_id` foreign keys.
- `attendance_records` has a `UNIQUE(user_id, student_id, attendance_date, class_name)` + `ON CONFLICT DO UPDATE` so re-running a session for the same date/class is idempotent.

### API / Frontend Contract
- All `/api` calls go through `frontend/src/api.js`, which attaches `Authorization: Bearer <token>` and clears the token on a 401 (the `AuthContext` reacts to that).
- Annotated image is still a raw base64 string; the frontend adds the `data:image/png;base64,` prefix.
- CSV export now uses `fetch()` + a blob download (not `window.location.href`) so it can send the bearer header.
- Vite proxies `/api` to the backend, same as before.

## Common Tasks

### Change the default similarity threshold
Each recognizer ships its own `threshold` class attribute (see `recognizers/insightface_engine.py` etc.). The matcher uses `recognizer.threshold` — no global constant.

### Add a new recognizer
1. Subclass `FaceRecognizer` in a new file under `backend/recognizers/`.
2. Add `name`, `display_name`, `description`, `embedding_dim`, `threshold`, `speed`.
3. Implement `detect_and_encode(image_bgr) -> list[DetectedFace]` returning L2-normalized embeddings.
4. Register it in `recognizers/registry.py` (both `_FACTORIES` and `_META`).
5. It now appears in the Settings page automatically.

### Add a new API endpoint
1. Add the route in the appropriate `routers/*.py`, with `Depends(get_current_user)` if it should require auth.
2. Add a fetch wrapper in `frontend/src/api.js` (it already attaches the bearer token).
3. Call it from the relevant page.

### Add a new page
1. Create `frontend/src/pages/MyPage.jsx`.
2. Add a `<Route>` in `App.jsx` wrapped in `<RequireAuth>`.
3. Add a `<NavItem>` in the nav.

### Reset the database
Delete `backend/data/presence.db`. It will be recreated on next startup and the demo seeder will re-enroll demo students.

### Reset the InsightFace model cache
Delete `backend/data/models/`. The selected pack re-downloads on next request.

## What NOT to Do
- Do not add an ORM (SQLAlchemy, etc.) — the plain sqlite3 queries are intentionally simple.
- Do not bypass the recognizer registry — keep `insightface.FaceAnalysis` and `mediapipe.solutions.*` imports inside their respective recognizer modules.
- Do not change embeddings storage from pickle BLOBs without migrating existing data.
- Do not use a shared global `THRESHOLD` — each recognizer carries its own.
- Do not query `students` without scoping by `user_id`. Data isolation is enforced in SQL, not in app code.
