import React, { useRef, useState } from "react";
import { downloadCsv, processAttendance } from "../api";

export default function AttendancePage() {
  // Form state
  const [className, setClassName] = useState("");
  const [date, setDate]           = useState(todayStr());
  const [photo, setPhoto]         = useState(null);

  // Result state
  const [result, setResult]   = useState(null);   // full API response object
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  const fileInputRef = useRef(null);

  function handlePhotoChange(e) {
    setPhoto(e.target.files[0] || null);
    // Clear previous results whenever a new photo is selected
    setResult(null);
    setError(null);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!photo) { setError("Please select a group photo."); return; }

    setLoading(true);
    setError(null);
    setResult(null);

    const fd = new FormData();
    fd.append("class_name",      className);
    fd.append("attendance_date", date);
    fd.append("photo",           photo);

    try {
      const data = await processAttendance(fd);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  // Build the export URL and trigger a browser download from the DB session.
  function handleExport() {
    if (!result) return;
    downloadCsv({
      sessionId: result.session_id,
      className: result.class_name,
      date:      result.date,
    });
  }

  return (
    <div className="page-enter">

      {/* ── Page header ─────────────────────────────────────────────── */}
      <div className="mb-8">
        <span className="page-label">03 / Attendance</span>
        <h1
          className="text-3xl font-bold"
          style={{ fontFamily: "'Fraunces', serif" }}
        >
          Take Attendance
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--col-muted)" }}>
          Upload a group photo — faces are matched against enrolled students.
        </p>
      </div>

      {/* ── Upload form ─────────────────────────────────────────────── */}
      <div className="card mb-8">
        <form onSubmit={handleSubmit}>

          <div className="p-6 space-y-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="field-label">Class</label>
                <input
                  type="text"
                  value={className}
                  onChange={(e) => setClassName(e.target.value)}
                  required
                  placeholder="e.g. 10-A"
                  className="field-input"
                />
              </div>
              <div>
                <label className="field-label">Date</label>
                {/*
                  colorScheme: dark makes the browser render the date picker
                  with a dark calendar — otherwise it pops open a white popup
                  that clashes with our dark UI.
                */}
                <input
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className="field-input"
                  style={{ colorScheme: "dark" }}
                />
              </div>
            </div>

            <div>
              <label className="field-label">Group Photo</label>
              <div
                style={{
                  borderLeft: "2px solid var(--col-border2)",
                  background: "var(--col-surface2)",
                }}
              >
                <input
                  type="file"
                  accept="image/*"
                  ref={fileInputRef}
                  onChange={handlePhotoChange}
                  required
                  className="block w-full text-sm cursor-pointer py-2.5 px-3"
                  style={{ color: "var(--col-muted)" }}
                />
              </div>
            </div>

            {error && (
              <div className="alert-error">{error}</div>
            )}
          </div>

          <div style={{ borderTop: "1px solid var(--col-border)" }}>
            <button type="submit" disabled={loading} className="btn-amber">
              {loading
                ? "Scanning faces… this may take 5–15 s"
                : "Process Attendance"}
            </button>
          </div>

        </form>
      </div>

      {/* ── Results ─────────────────────────────────────────────────── */}
      {result && (
        <div className="space-y-6 page-enter-d1">

          {/* Summary / export bar */}
          <div
            className="p-5 flex flex-wrap items-center justify-between gap-4 card"
          >
            <div>
              <p
                className="text-xs font-mono tracking-widest mb-1"
                style={{ color: "var(--col-muted)" }}
              >
                {result.date} · CLASS {result.class_name.toUpperCase()}
              </p>
              {/*
                Two-tone large number: the present count is green,
                the denominator is muted — instantly scannable.
              */}
              <p
                className="text-2xl font-bold"
                style={{ fontFamily: "'Fraunces', serif" }}
              >
                <span style={{ color: "var(--col-green)" }}>
                  {result.recognized_count}
                </span>
                <span style={{ color: "var(--col-muted)" }}>
                  {" "}/ {result.total_faces} recognized
                </span>
              </p>
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              <span className="badge-present">{result.recognized_count} Present</span>
              {result.absent_count !== undefined && (
                <span className="badge-absent">{result.absent_count} Absent</span>
              )}
              <span className="badge-unknown">{result.unknown_count} Unknown</span>
              <button
                onClick={handleExport}
                disabled={!result.session_id && result.recognized_count === 0}
                className="btn-ghost"
              >
                Export CSV
              </button>
            </div>
          </div>

          {/* Split view: annotated photo + results table */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* Annotated photo */}
            <div className="card p-4 page-enter-d2">
              <p
                className="text-xs tracking-[0.1em] uppercase mb-3"
                style={{ color: "var(--col-muted)", fontFamily: "'Space Mono', monospace" }}
              >
                Annotated Photo
              </p>
              {/*
                The backend returns a plain base64 string (no "data:" prefix),
                so we add "data:image/png;base64," here in the JSX.
              */}
              <img
                src={`data:image/png;base64,${result.annotated_image}`}
                alt="Annotated attendance photo"
                className="w-full object-contain max-h-[500px]"
                style={{ border: "1px solid var(--col-border2)" }}
              />
            </div>

            {/* Results table */}
            <div className="card page-enter-d3">
              <div
                className="px-4 py-2.5"
                style={{
                  borderBottom: "1px solid var(--col-border)",
                  background: "var(--col-surface2)",
                }}
              >
                <p
                  className="text-xs tracking-[0.1em] uppercase"
                  style={{ color: "var(--col-muted)", fontFamily: "'Space Mono', monospace" }}
                >
                  Recognition Results
                </p>
              </div>

              <div className="overflow-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--col-border)" }}>
                      <th className="th">#</th>
                      <th className="th">Name</th>
                      <th className="th">Roll</th>
                      <th className="th">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.results.map((r, idx) => {
                      const isAbsent = r.status === "absent";
                      const rowKey =
                        r.face_index != null
                          ? `face-${r.face_index}`
                          : `student-${r.student_id || r.roll_number || idx}`;
                      return (
                        <tr
                          key={rowKey}
                          style={{
                            borderBottom: "1px solid rgba(28,28,56,0.8)",
                            opacity: isAbsent ? 0.6 : 1,
                          }}
                        >
                          <td
                            className="px-4 py-3 text-xs font-mono"
                            style={{ color: "var(--col-muted)" }}
                          >
                            {r.face_index != null ? r.face_index : "—"}
                          </td>
                          <td
                            className={`px-4 py-3 font-medium ${
                              isAbsent ? "text-[var(--col-muted)]" : ""
                            }`}
                          >
                            {r.name}
                          </td>
                          <td
                            className="px-4 py-3 text-xs"
                            style={{
                              fontFamily: "'Space Mono', monospace",
                              color: "var(--col-muted)",
                            }}
                          >
                            {r.roll_number ?? "—"}
                          </td>
                          <td className="px-4 py-3">
                            {r.status === "recognized" ? (
                              <span className="badge-present">Present</span>
                            ) : r.status === "absent" ? (
                              <span className="badge-absent">Absent</span>
                            ) : (
                              <span className="badge-unknown">Unknown</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}

// Returns today's date as YYYY-MM-DD — the format HTML date inputs require
function todayStr() {
  return new Date().toISOString().slice(0, 10);
}
