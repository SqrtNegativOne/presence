/**
 * api.js — All network calls to the FastAPI backend in one place.
 *
 * Auth: a JWT session token (issued by /api/auth/google or /api/auth/demo) is
 * persisted in localStorage. Every API call attaches it via Authorization:
 * Bearer. On 401 we clear the token and the AuthContext picks that up.
 */

const BASE = "/api";
const TOKEN_KEY = "presence.token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(t) {
  if (t) localStorage.setItem(TOKEN_KEY, t);
  else localStorage.removeItem(TOKEN_KEY);
}

function authHeaders() {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function request(url, opts = {}) {
  const headers = { ...(opts.headers || {}), ...authHeaders() };
  const res = await fetch(url, { ...opts, headers });
  if (res.status === 401) {
    setToken(null);
    // Let callers know; the AuthContext listens to the storage event,
    // but we also throw so the current call surfaces an error.
    window.dispatchEvent(new Event("presence:unauthenticated"));
    throw new Error("Sign in required.");
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const err = await res.json();
      detail = err.detail || detail;
    } catch { /* not JSON */ }
    throw new Error(detail);
  }
  return res;
}

// ── Auth ────────────────────────────────────────────────────────────────────

export async function signInWithGoogle(credential) {
  const res = await request(`${BASE}/auth/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential }),
  });
  return res.json();
}

export async function signInAsDemo() {
  const res = await request(`${BASE}/auth/demo`, { method: "POST" });
  return res.json();
}

export async function fetchMe() {
  const res = await request(`${BASE}/auth/me`);
  return res.json();
}

export async function logout() {
  try {
    await request(`${BASE}/auth/logout`, { method: "POST" });
  } catch { /* even if it fails, clear locally */ }
  setToken(null);
}

// ── Recognizers ─────────────────────────────────────────────────────────────

export async function listRecognizers() {
  const res = await request(`${BASE}/recognizers`);
  return res.json();
}

export async function setPreferredRecognizer(name) {
  const res = await request(`${BASE}/recognizers/preferred`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  return res.json();
}

// ── Students ────────────────────────────────────────────────────────────────

export async function enrollStudent(formData) {
  const res = await request(`${BASE}/students/enroll`, {
    method: "POST",
    body: formData,
  });
  return res.json();
}

export async function listStudents(className = null) {
  const url = className
    ? `${BASE}/students?class_name=${encodeURIComponent(className)}`
    : `${BASE}/students`;
  const res = await request(url);
  return res.json();
}

export async function deleteStudent(studentId) {
  const res = await request(`${BASE}/students/${studentId}`, { method: "DELETE" });
  return res.json();
}

// ── Attendance ──────────────────────────────────────────────────────────────

export async function listDemoClasses() {
  const res = await request(`${BASE}/attendance/demo-classes`);
  return res.json();
}

export async function fetchDemoGroupPhoto(className) {
  const res = await request(
    `${BASE}/attendance/demo-group-photo?class_name=${encodeURIComponent(className)}`,
  );
  return res.blob();
}

export async function processAttendance(formData) {
  const res = await request(`${BASE}/attendance/process`, {
    method: "POST",
    body: formData,
  });
  return res.json();
}

/**
 * CSV download — uses fetch (not window.location.href) so we can send the
 * Authorization header, then triggers a blob download in the browser.
 */
export async function downloadCsv({ className, date, rollNumbers }) {
  const rolls = rollNumbers.join(",");
  const url = `${BASE}/attendance/export?class_name=${encodeURIComponent(className)}&attendance_date=${encodeURIComponent(date)}&roll_numbers=${encodeURIComponent(rolls)}`;
  const res = await request(url);
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = `${date}_${className}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(objectUrl);
}
