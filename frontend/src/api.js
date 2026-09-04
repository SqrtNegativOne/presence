/**
 * api.js — All network calls to the FastAPI backend in one place.
 *
 * We use the browser's built-in `fetch` API — no axios needed.
 * Because Vite proxies /api → localhost:8000, we use relative URLs.
 */

const BASE = "/api";

// ── Students ────────────────────────────────────────────────────────────────

/**
 * Enroll a student with a solo photo.
 * @param {FormData} formData  Must contain: name, roll_number, class_name, photo (File)
 */
export async function enrollStudent(formData) {
  const res = await fetch(`${BASE}/students/enroll`, {
    method: "POST",
    body: formData,  // FormData sets the Content-Type header automatically
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Enrollment failed");
  }
  return res.json();
}

/**
 * Enroll a student using a client-side computed embedding (JSON body).
 * @param {Object} params
 * @param {string} params.name
 * @param {string} params.roll_number
 * @param {string} params.class_name
 * @param {Array<number>} params.embedding - 128-d face descriptor array
 * @param {string} [params.model_type='faceapi']
 */
export async function enrollStudentEmbedding({
  name,
  roll_number,
  class_name,
  embedding,
  model_type = "faceapi",
}) {
  const res = await fetch(`${BASE}/students/enroll-embedding`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      roll_number,
      class_name,
      embedding,
      model_type,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Enrollment with embedding failed");
  }
  return res.json();
}

/**
 * List all enrolled students, optionally filtered by class.
 * @param {string|null} className
 */
export async function listStudents(className = null) {
  const url = className
    ? `${BASE}/students?class_name=${encodeURIComponent(className)}`
    : `${BASE}/students`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch students");
  return res.json();
}

/**
 * Delete a student by their database ID.
 * @param {number} studentId
 */
export async function deleteStudent(studentId) {
  const res = await fetch(`${BASE}/students/${studentId}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Delete failed");
  }
  return res.json();
}

// ── Attendance ───────────────────────────────────────────────────────────────

/**
 * Process a group photo for attendance.
 * @param {FormData} formData  Must contain: class_name, photo (File), optionally attendance_date
 */
export async function processAttendance(formData) {
  const res = await fetch(`${BASE}/attendance/process`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Attendance processing failed");
  }
  return res.json();
}

/**
 * Match client-side extracted embeddings against enrolled students.
 * @param {Object} params
 * @param {string} params.class_name
 * @param {string} [params.attendance_date]
 * @param {Array<Array<number>>} params.embeddings - Array of 128-d face descriptors
 * @param {string} [params.model_type='faceapi']
 * @param {string|null} [params.photo_hash]
 * @returns {Promise<{
 *   session_id: number,
 *   class_name: string,
 *   attendance_date: string,
 *   total_faces: number,
 *   recognized_count: number,
 *   unknown_count: number,
 *   records: Array<any>,
 *   unmatched_faces: Array<any>
 * }>}
 */
export async function matchEmbeddings({
  class_name,
  attendance_date,
  embeddings,
  model_type = "faceapi",
  photo_hash = null,
}) {
  const payload = {
    class_name,
    attendance_date,
    embeddings,
    model_type,
  };
  if (photo_hash) {
    payload.photo_hash = photo_hash;
  }
  const res = await fetch(`${BASE}/attendance/match-embeddings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Attendance matching failed");
  }
  return res.json();
}

/**
 * Build the URL for CSV export and trigger a browser download.
 * We use window.location.href so the browser downloads it as a file.
 */
export function downloadCsv({ sessionId, className, date }) {
  const params = new URLSearchParams();
  if (sessionId) params.append("session_id", sessionId);
  if (className) params.append("class_name", className);
  if (date) params.append("attendance_date", date);
  window.location.href = `${BASE}/attendance/export?${params.toString()}`;
}

/**
 * Fetch past attendance sessions, optionally filtered by class.
 * @param {string|null} className
 */
export async function getAttendanceHistory(className = null) {
  const url = className
    ? `${BASE}/attendance/history?class_name=${encodeURIComponent(className)}`
    : `${BASE}/attendance/history`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch attendance history");
  return res.json();
}

/**
 * Fetch full details and records for a specific attendance session.
 * @param {number} sessionId
 */
export async function getAttendanceSession(sessionId) {
  const res = await fetch(`${BASE}/attendance/sessions/${sessionId}`);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to fetch attendance session");
  }
  return res.json();
}

