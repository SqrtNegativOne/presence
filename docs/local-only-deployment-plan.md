# Local-Only Deployment Profile — Implementation Plan

> **Audience:** an implementing agent (or engineer) picking this up cold.
> **Repo:** `presence/` — AI classroom attendance (FastAPI + PostgreSQL + React/Vite, hybrid face recognition).
> **Read first:** `AGENTS.md` (project rules), `README.md`, `docker-compose.yml`, `backend/pyproject.toml`.

---

## 1. Objective

Make the app deployable to a **free** hosting tier by running it in **local-only mode**: all face detection/embedding happens in the browser (`@vladmandic/face-api`), and the backend becomes a thin JSON + PostgreSQL service with **no InsightFace / ONNX / OpenCV / Pillow runtime dependency**.

At the same time, **keep full cloud mode (InsightFace) fully working on the developer's own machine** via the existing `docker-compose.yml` / `run.ps1` flow. This is a feature flag, not a deletion.

### Target architecture

| Piece | Host | Notes |
| :--- | :--- | :--- |
| Frontend (static Vite SPA) | Cloudflare Pages (or Vercel / Render static) | Serves `public/models/` for face-api.js; HTTPS required for `getUserMedia`. |
| Backend (FastAPI, **lite**) | Render free Docker Web Service | Long-running process, so the existing `psycopg_pool` works unchanged. |
| PostgreSQL | Neon free (or any managed Postgres) | Reachable from Render. |
| **Local "production"** (InsightFace) | This computer only | Unchanged `docker-compose up --build`; optionally points at the same Neon DB. |

**Cloudflare is frontend-only.** Do NOT attempt to port the API to Cloudflare Workers/Python — Python Workers are Pyodide/WASM and cannot load `psycopg[binary]`; D1 is SQLite, not Postgres. See §9.

---

## 2. Non-negotiable constraints (from AGENTS.md)

1. **No ORM.** Keep raw parameterized `psycopg` SQL with `%s`. Do not introduce SQLAlchemy/Tortoise.
2. **No `pickle`.** Embeddings stay `np.ndarray.tobytes()` / `np.frombuffer()` on `BYTEA`.
3. **Never mix embedding dimensions.** 128-d (`faceapi`) and 512-d (`insightface`) stay isolated by `model_type` **and** the existing dimension check in `match_embeddings`. Do not weaken either.
4. **Local mode must never upload group photos.** Preserve the privacy guarantee.
5. **Cloud mode must keep working locally.** The flag defaults to enabled; do not remove InsightFace handling.
6. Keep model inference centralized in `services/face_service.py` for actual cloud inference.

---

## 3. Environment variables (add + document)

Create `backend/.env.example` and a small `backend/config.py`.

| Variable | Default | Meaning |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql://presence:presence@localhost:5432/presence` | Already read in `database.py`. |
| `CLOUD_MODE_ENABLED` | `true` | When `false`, cloud endpoints return **503** and no heavy module is importable. |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated CORS allow-list. |
| `PORT` | `8000` | Injected by Render; Dockerfile must honor it. |
| `VITE_API_BASE_URL` (frontend) | *(unset)* | Backend origin, e.g. `https://presence-api.onrender.com`. Unset ⇒ relative `/api` (dev proxy). |
| `VITE_ALLOW_CLOUD` (frontend) | `true` | When `false`, force Local mode and hide the model selector. |

`TOKEN` semantics: `CLOUD_MODE_ENABLED=true` must remain the default so local dev and all existing tests are unaffected.

---

## 4. Work breakdown

Each phase is independently testable. Do them in order.

### Phase 1 — Decouple pure matching from the heavy ML stack

**Problem:** `backend/routers/attendance.py` imports `match_embeddings` from `services.face_service`, but `face_service.py` imports `cv2` and `insightface` at module top. So even local-only requests drag in the entire ML stack (and blow serverless/size budgets / OOM free tiers).

**Change:** extract the pure-numpy matcher into `backend/services/matching.py`.

1. Create `backend/services/matching.py` containing:
   - `THRESHOLD = 0.4` (move the constant here).
   - `match_embeddings(...)` moved **verbatim** from `services/face_service.py` (lines ~104–210).
   - Only imports allowed: `numpy`, stdlib, `loguru`.
2. Edit `backend/services/face_service.py`:
   - Remove the `match_embeddings` body and the `THRESHOLD` definition.
   - Add `from services.matching import THRESHOLD, match_embeddings` and keep them as **re-exports** so existing imports (`test_face_service.py`, others) keep working.
   - `match_group_photo` continues to call `match_embeddings` internally.
3. Edit `backend/routers/attendance.py`:
   - `from services.matching import match_embeddings` (pure module).
   - **Delete** the top-level `from services.face_service import match_embeddings, match_group_photo` and `from services.image_service import annotate_image`.
   - Inside `process_attendance` only (after the cloud-mode guard, §Phase 2), lazily import:
     ```python
     from services.face_service import match_group_photo
     from services.image_service import annotate_image
     ```
4. Edit `backend/routers/students.py`:
   - Remove top-level `from services.face_service import encode_single_face`.
   - Lazy-import it inside `enroll_student` after the guard.

**Verify:** `python -c "import services.matching"` must not import cv2/insightface. A test asserting `"insightface" not in sys.modules` after importing the lite app is ideal (Phase 6).

---

### Phase 2 — `CLOUD_MODE_ENABLED` gate

1. Create `backend/config.py`:
   ```python
   import os

   def _bool(name: str, default: bool) -> bool:
       return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}

   CLOUD_MODE_ENABLED = _bool("CLOUD_MODE_ENABLED", True)
   ALLOWED_ORIGINS = [
       o.strip()
       for o in os.getenv(
           "ALLOWED_ORIGINS",
           "http://localhost:5173,http://127.0.0.1:5173",
       ).split(",")
       if o.strip()
   ]
   ```
   (Read env after `database._load_env_file()` has run, or replicate the `.env` load — `database.py` already calls `_load_env_file()` at import. Importing `config` from `main.py` after `database` is fine; if order is fragile, move `.env` loading into a tiny shared module and have both import it.)
2. Add a guard helper (in `config.py` or `routers/__init__.py`):
   ```python
   from fastapi import HTTPException

   def require_cloud_mode() -> None:
       if not CLOUD_MODE_ENABLED:
           raise HTTPException(
               status_code=503,
               detail="Cloud mode is disabled on this deployment. Use local (browser) mode.",
           )
   ```
3. Call `require_cloud_mode()` as the **first statement** of:
   - `POST /api/students/enroll` (`students.py::enroll_student`)
   - `POST /api/attendance/process` (`attendance.py::process_attendance`)
   Only **after** the guard passes may those handlers lazily import `face_service` / `image_service`.
4. `GET /`, `/api/attendance/match-embeddings`, `/api/attendance/history`, `/api/attendance/sessions/{id}`, `/api/attendance/export`, `POST /api/students/enroll-embedding`, `GET /api/students`, `DELETE /api/students/{id}` must remain available in local-only mode.
5. Update `main.py`:
   - Replace the hardcoded `allow_origins=[...]` with `config.ALLOWED_ORIGINS`.
   - Log cloud mode at startup, e.g. `logger.info(f"Cloud mode enabled: {config.CLOUD_MODE_ENABLED}")`.
   - Do **not** import `face_service` at startup (the commented-out pre-load must stay commented / be guarded).

**Acceptance:**
- With `CLOUD_MODE_ENABLED=false`, `/process` and `/enroll` return `503` with a clear `detail`.
- With `CLOUD_MODE_ENABLED=true`, behavior is byte-for-byte unchanged locally.

---

### Phase 3 — Split dependencies into a `cloud` extra

Goal: the hosted image installs **fastapi, uvicorn, python-multipart, numpy, loguru, psycopg[binary], psycopg-pool** only.

1. Edit `backend/pyproject.toml`:
   - Keep base `[project].dependencies`: `fastapi`, `uvicorn[standard]`, `python-multipart`, `numpy`, `loguru`, `psycopg[binary]`, `psycopg-pool`.
   - Move to a new group:
     ```toml
     [project.optional-dependencies]
     cloud = [
         "insightface>=0.7.3",
         "onnxruntime>=1.18.0",
         "Pillow>=10.0.0",
         "opencv-python-headless>=4.10.0",
     ]
     ```
   - Leave `[dependency-groups] dev` as-is.
2. Regenerate the lockfile: `cd backend && uv lock`.
3. Update commands:
   - **Local full stack / tests:** `uv sync --extra cloud` (or `--all-extras`).
   - **Hosted lite runtime:** `uv sync --no-dev` (no `cloud` extra).
4. `backend/Dockerfile`: add a build arg so one file serves both:
   ```dockerfile
   ARG INSTALL_CLOUD=false
   RUN if [ "$INSTALL_CLOUD" = "true" ]; then uv sync --extra cloud; else uv sync --no-dev; fi
   ```
   and change the last line to shell form so `$PORT` expands:
   ```dockerfile
   CMD uv run uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
   ```
   Keep `EXPOSE 8000` (Render routes to `$PORT` regardless).
5. `docker-compose.yml`: build the local `backend` with `args: { INSTALL_CLOUD: "true" }` and set `CLOUD_MODE_ENABLED: "true"` in its `environment`. (Local InsightFace "production" keeps working.)
6. `run.ps1`: change `uv sync` → `uv sync --extra cloud` so local dev keeps cloud mode.

**Risk to manage:** `backend/tests/test_face_service.py` imports the heavy stack. Add `pytest.importorskip("insightface")` / `pytest.importorskip("cv2")` at the top of that module so a lite environment still collects and runs the rest of the suite instead of erroring.

---

### Phase 4 — Frontend: configurable API base + force local mode

1. Edit `frontend/src/api.js`:
   ```js
   const API_ORIGIN = import.meta.env.VITE_API_BASE_URL ?? "";
   const BASE = `${API_ORIGIN}/api`;
   ```
   Unset ⇒ relative `/api` ⇒ the Vite dev proxy still works with zero config.
2. Model selection:
   - Inspect `frontend/src/context/ModelContext.jsx` and `frontend/src/App.jsx` (the `ModelSelector` toggle).
   - When `import.meta.env.VITE_ALLOW_CLOUD === "false"`:
     - force the active model to `'local'`,
     - hide (or disable with a tooltip) the cloud toggle.
   - Keep the default (`true`/unset) exactly as today.
3. `frontend/vite.config.js`: no change required for the base, but ensure `VITE_*` vars are read at build time (they are, via `import.meta.env`). The existing `BACKEND_URL` dev-proxy var stays.
4. Frontend tests: `frontend/test/api.test.js` may stub `fetch` against `/api/...`. Update/extend so it does not break, and add a case for the configured origin if practical (mock `import.meta.env` via a helper or test the URL builder as a pure function).

---

### Phase 5 — Deployment configuration

**Backend → Render (Docker Web Service).** Add `render.yaml` at repo root:
```yaml
services:
  - type: web
    name: presence-api
    runtime: docker
    dockerfilePath: ./backend/Dockerfile
    dockerContext: ./backend
    plan: free
    healthCheckPath: /
    envVars:
      - key: CLOUD_MODE_ENABLED
        value: "false"
      - key: ALLOWED_ORIGINS
        sync: false            # set to the Pages URL, e.g. https://presence.pages.dev
      - key: DATABASE_URL
        sync: false            # Neon connection string
```
Note: build the **lite** image (default `INSTALL_CLOUD=false`). No persistent disk and no model cache are needed in lite mode.

**Frontend → Cloudflare Pages (recommended) or Vercel.**
- Cloudflare Pages: build command `bun install --frozen-lockfile && bun run build`, output `frontend/dist`, root `frontend`, env `VITE_API_BASE_URL=https://<render-api>.onrender.com`, `VITE_ALLOW_CLOUD=false`.
- Vercel alternative: framework Vite, root `frontend`, same env vars. **Flag:** Vercel Hobby is non-commercial-use only — prefer Cloudflare Pages if a school/institution uses this.
- Render static alternative: add a second entry to `render.yaml` with `type: web` + `runtime: static` — simplest single-vendor option, but Render's free Postgres is time-limited, hence Neon.

**Database → Neon.** Create a DB, copy the pooled connection string into Render's `DATABASE_URL`. It already contains `sslmode=require`; `psycopg` honors it. Keep `min_size=1`/`max_size=10` (Render is a single long-running instance, so the existing pool is fine).

Add `backend/.env.example` (all backend vars, no secrets) and update `README.md` with a short "Deploy (local-only)" section + the switching instructions (`CLOUD_MODE_ENABLED`).

---

### Phase 6 — Tests

Backend (`backend/tests/`):
- New `test_config.py` / extend `test_students_api.py` + `test_attendance_api.py`:
  - `CLOUD_MODE_ENABLED=false` ⇒ `POST /api/students/enroll` and `POST /api/attendance/process` return **503**.
  - Same flag ⇒ `POST /api/students/enroll-embedding` and `POST /api/attendance/match-embeddings` still succeed and persist.
  - `CLOUD_MODE_ENABLED=true` ⇒ existing cloud tests pass unchanged (monkeypatch env + reload `config`, or use a fixture that sets the module attribute).
- `test_face_service.py`: guard with `importorskip`; keep `match_embeddings` tests (now in `services/matching.py`) running in the lite env — add `test_matching.py` for the pure matcher.
- Add an import-isolation test: with lite deps absent, `import main` and `import services.matching` must not pull in `insightface`/`cv2`/`onnxruntime`.

Frontend (`frontend/test/`): `bun test` — update `api.test.js` for the new `BASE` expression; keep `ModelContext.test.js` green.

**Full verification (must all pass before marking done):**
```powershell
cd backend
uv sync --extra cloud
uv run pytest
uv run ruff check .
uv run ruff format .
uv run ty check

cd ../frontend
bun test
bun run lint
bun run build
```

Also do a **lite-mode smoke test**: in a venv with only base deps installed (`uv sync --no-dev`), confirm `uvicorn main:app` boots, `match-embeddings` works, and cloud endpoints 503. Then rebuild the Docker image with `--build-arg INSTALL_CLOUD=true` and confirm local cloud mode still works.

---

## 5. Files to create / modify (checklist)

**Create**
- [ ] `backend/services/matching.py` — pure-numpy matcher + `THRESHOLD`
- [ ] `backend/config.py` — `CLOUD_MODE_ENABLED`, `ALLOWED_ORIGINS`, `require_cloud_mode()`
- [ ] `backend/.env.example`
- [ ] `render.yaml`
- [ ] `backend/tests/test_matching.py` (and `test_config.py` if split)
- [ ] `docs/` note or README section for deployment

**Modify**
- [ ] `backend/services/face_service.py` — re-export matcher, remove moved code
- [ ] `backend/routers/attendance.py` — lazy heavy imports, guard `/process`
- [ ] `backend/routers/students.py` — lazy heavy import, guard `/enroll`
- [ ] `backend/main.py` — `ALLOWED_ORIGINS`, cloud-mode log, no eager heavy import
- [ ] `backend/pyproject.toml` — `cloud` optional extra; lockfile via `uv lock`
- [ ] `backend/Dockerfile` — `INSTALL_CLOUD` arg, `${PORT:-8000}` CMD
- [ ] `docker-compose.yml` — `INSTALL_CLOUD=true`, `CLOUD_MODE_ENABLED=true`
- [ ] `run.ps1` — `uv sync --extra cloud`
- [ ] `frontend/src/api.js` — `VITE_API_BASE_URL`
- [ ] `frontend/src/context/ModelContext.jsx` + `frontend/src/App.jsx` — `VITE_ALLOW_CLOUD`
- [ ] `frontend/test/api.test.js` — updated base handling
- [ ] `README.md` — deploy + flag docs

---

## 6. Acceptance criteria

1. `CLOUD_MODE_ENABLED=false` deployed backend serves local-mode enrollment, matching, history, sessions, and CSV export; `/process` + `/enroll` return 503 with a helpful message.
2. The lite image installs **without** `insightface`, `onnxruntime`, `opencv-python-headless`, or `Pillow`, and boots under a 512 MB instance.
3. Importing the lite app does **not** import `insightface`/`cv2`/`onnxruntime`.
4. With `--build-arg INSTALL_CLOUD=true` and `CLOUD_MODE_ENABLED=true`, the full InsightFace flow works exactly as before locally.
5. `ALLOWED_ORIGINS` and the frontend `VITE_API_BASE_URL` are wired end-to-end (browser requests reach the Render API cross-origin without CORS errors).
6. Backend `pytest`, `ruff check`, `ruff format`, `ty check`; frontend `bun test`, `bun run lint`, `bun run build` all pass.
7. No changes to `database.py` query semantics, embedding storage (still raw float32 bytes), or thresholds (0.4 cloud / 0.6 local).
8. A shared Postgres with mixed `model_type` rows remains safe: `match-embeddings` only matches equal-dimension embeddings.

---

## 7. Out of scope

- Porting the API to Cloudflare Workers, Vercel Functions, or any serverless runtime (would require a `psycopg`/pooling rewrite — explicitly rejected).
- Removing or deprecating cloud mode.
- Changing recognition thresholds, DB schema, or the no-ORM design.
- Auth/multi-tenancy (none exists today; don't introduce it as part of this work unless separately requested).
- Building a GPU inference path.

---

## 8. Risks & notes

- **Neon + pooling:** Neon's pooled endpoint + Render's single instance is fine with the current `ConnectionPool(min=1, max=10)`. If the API were ever scaled to multiple instances/serverless, reduce `max_size` and use the pooled host. Not required now.
- **Render free cold start:** ~30–60 s after 15 min idle. Acceptable for a classroom/demo tool; document it. Free *Postgres* on Render expires — use Neon.
- **`VITE_*` is build-time:** changing `VITE_API_BASE_URL` requires a frontend rebuild/redeploy. Document this.
- **Tracked artifact:** `backend/data/presence.db` appears in `git ls-files` despite `.gitignore`. Leave it alone or remove in a separate cleanup commit — don't fold it into this change.
- **`.env` load order:** `database.py` loads `.env` at import; `config.py` must see those values. Import `database` (or a shared dotenv helper) before reading env, or centralize dotenv loading.
- **Test isolation:** tests that monkeypatch `CLOUD_MODE_ENABLED` must restore it; prefer patching the `config` module attribute over `os.environ` where practical to avoid import-order surprises.

---

## 9. Why not Cloudflare for the backend (rationale, for reviewers)

- Cloudflare **Python Workers** run on Pyodide/WASM and are still limited/beta; they cannot load native binary wheels, so `psycopg[binary]` and `psycopg-pool` are unavailable without a rewrite.
- **D1 is SQLite**, not PostgreSQL — adopting it means rewriting `database.py` and abandoning the intentional Postgres/no-ORM design.
- Node Workers + Hyperdrive would require porting the FastAPI app to JavaScript. Not worth it.
- Conclusion: Cloudflare Pages for the static frontend only; keep the Python API on Render.
