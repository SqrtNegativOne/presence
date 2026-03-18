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
 * Bulk-enroll students from a CSV file and a ZIP of their photos.
 * @param {FormData} formData  Must contain: csv_file (File), photos_zip (File)
 * Returns { total, succeeded, failed, results[] }
 */
export async function bulkEnrollStudents(formData) {
  const res = await fetch(`${BASE}/students/bulk-enroll`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Bulk enrollment failed");
  }
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
 * Build the URL for CSV export and trigger a browser download.
 * We use window.location.href so the browser downloads it as a file,
 * rather than showing the CSV text in the page.
 */
export function downloadCsv({ className, date, rollNumbers }) {
  const rolls = rollNumbers.join(",");
  const url = `${BASE}/attendance/export?class_name=${encodeURIComponent(className)}&attendance_date=${encodeURIComponent(date)}&roll_numbers=${encodeURIComponent(rolls)}`;
  window.location.href = url;
}
