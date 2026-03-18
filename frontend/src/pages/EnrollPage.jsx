import React, { useRef, useState } from "react";
import { bulkEnrollStudents, enrollStudent } from "../api";

export default function EnrollPage() {
  // Form field state
  const [name, setName]           = useState("");
  const [roll, setRoll]           = useState("");
  const [className, setClassName] = useState("");
  const [photo, setPhoto]         = useState(null);    // File object
  const [preview, setPreview]     = useState(null);    // data URL for preview

  // UI state
  const [loading, setLoading] = useState(false);
  const [toast, setToast]     = useState(null); // { type: "success"|"error", msg }

  const fileInputRef = useRef(null);

  // When the user picks a file, generate a preview immediately using FileReader.
  // FileReader reads the file in the browser without uploading it.
  function handlePhotoChange(e) {
    const file = e.target.files[0];
    if (!file) return;
    setPhoto(file);
    const reader = new FileReader();
    reader.onload = (ev) => setPreview(ev.target.result);
    reader.readAsDataURL(file); // converts file → base64 data URL
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!photo) { showToast("error", "Please select a photo."); return; }

    setLoading(true);
    setToast(null);

    // FormData is the browser's way of sending a mix of text + file data
    // in one HTTP request (multipart/form-data format).
    const fd = new FormData();
    fd.append("name",       name);
    fd.append("roll_number", roll);
    fd.append("class_name", className);
    fd.append("photo",      photo);

    try {
      const result = await enrollStudent(fd);
      showToast("success", `${result.name} enrolled successfully.`);
      // Reset form after success
      setName(""); setRoll(""); setClassName(""); setPhoto(null); setPreview(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      showToast("error", err.message);
    } finally {
      setLoading(false);
    }
  }

  function showToast(type, msg) {
    setToast({ type, msg });
    // Auto-dismiss after 5 seconds
    setTimeout(() => setToast(null), 5000);
  }

  return (
    <div className="max-w-lg mx-auto page-enter">

      {/* ── Page header ─────────────────────────────────────────────── */}
      <div className="mb-8">
        <span className="page-label">01 / Enroll</span>
        <h1
          className="text-3xl font-bold"
          style={{ fontFamily: "'Fraunces', serif" }}
        >
          New Student
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--col-muted)" }}>
          Upload one clear, frontal portrait per student.
        </p>
      </div>

      {/* ── Toast notification ──────────────────────────────────────── */}
      {toast && (
        <div
          className={`mb-6 ${toast.type === "success" ? "alert-success" : "alert-error"}`}
        >
          {toast.msg}
        </div>
      )}

      {/* ── Form card ───────────────────────────────────────────────── */}
      {/*
        The card has no border-radius (square corners) to reinforce the
        "official document" aesthetic. The submit button sits outside the
        padding area, separated by a border, like a footer on a form.
      */}
      <div className="card">
        <form onSubmit={handleSubmit}>

          <div className="p-6 space-y-5">

            <Field label="Student Name">
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                placeholder="e.g. Arjun Sharma"
                className="field-input"
              />
            </Field>

            {/* Two-column row for roll + class */}
            <div className="grid grid-cols-2 gap-4">
              <Field label="Roll Number">
                <input
                  type="text"
                  value={roll}
                  onChange={(e) => setRoll(e.target.value)}
                  required
                  placeholder="e.g. CS101"
                  className="field-input"
                  style={{ fontFamily: "'Space Mono', monospace", fontSize: "0.8125rem" }}
                />
              </Field>
              <Field label="Class">
                <input
                  type="text"
                  value={className}
                  onChange={(e) => setClassName(e.target.value)}
                  required
                  placeholder="e.g. 10-A"
                  className="field-input"
                />
              </Field>
            </div>

            <Field label="Solo Portrait Photo">
              {/* The native file input is hard to fully style.
                  We wrap it in a div that has the same left-border treatment
                  as our other inputs. */}
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
              <p className="text-xs mt-1.5" style={{ color: "var(--col-muted)" }}>
                Must contain exactly one face. Clear, well-lit, frontal.
              </p>
            </Field>

            {/* Photo preview — shown once a file is chosen */}
            {preview && (
              <div
                className="flex justify-center p-4"
                style={{ background: "var(--col-surface2)", border: "1px solid var(--col-border)" }}
              >
                <img
                  src={preview}
                  alt="Photo preview"
                  className="max-h-48 object-contain"
                  style={{ border: "2px solid var(--col-accent)", opacity: 0.9 }}
                />
              </div>
            )}

          </div>

          {/* Submit button separated by a border — like a form footer */}
          <div style={{ borderTop: "1px solid var(--col-border)" }}>
            <button type="submit" disabled={loading} className="btn-amber">
              {loading ? "Processing…" : "Enroll Student"}
            </button>
          </div>

        </form>
      </div>

      {/* ── Bulk Import section ──────────────────────────────────────── */}
      <BulkEnrollSection />

    </div>
  );
}

/* ── Bulk CSV + ZIP enrollment ─────────────────────────────────────────── */
function BulkEnrollSection() {
  const [csvFile, setCsvFile]     = useState(null);
  const [zipFile, setZipFile]     = useState(null);
  const [loading, setLoading]     = useState(false);
  const [results, setResults]     = useState(null); // response from API
  const [error, setError]         = useState(null);

  const csvRef = useRef(null);
  const zipRef = useRef(null);

  async function handleBulkSubmit(e) {
    e.preventDefault();
    if (!csvFile || !zipFile) return;

    setLoading(true);
    setResults(null);
    setError(null);

    const fd = new FormData();
    fd.append("csv_file",   csvFile);
    fd.append("photos_zip", zipFile);

    try {
      const data = await bulkEnrollStudents(fd);
      setResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setCsvFile(null);
    setZipFile(null);
    setResults(null);
    setError(null);
    if (csvRef.current) csvRef.current.value = "";
    if (zipRef.current) zipRef.current.value = "";
  }

  return (
    <div className="mt-10">

      {/* Section divider */}
      <div className="flex items-center gap-4 mb-6">
        <div style={{ flex: 1, height: "1px", background: "var(--col-border)" }} />
        <span
          className="text-xs tracking-[0.15em] uppercase"
          style={{ color: "var(--col-muted)" }}
        >
          or import in bulk
        </span>
        <div style={{ flex: 1, height: "1px", background: "var(--col-border)" }} />
      </div>

      <div className="mb-4">
        <h2
          className="text-xl font-bold"
          style={{ fontFamily: "'Fraunces', serif" }}
        >
          Bulk Import
        </h2>
        <p className="text-sm mt-1" style={{ color: "var(--col-muted)" }}>
          Upload a CSV roster and a ZIP of photos to enroll many students at once.
        </p>
      </div>

      {/* Format hint */}
      <div
        className="mb-5 p-4 text-xs"
        style={{
          background: "var(--col-surface2)",
          border: "1px solid var(--col-border)",
          fontFamily: "'Space Mono', monospace",
          color: "var(--col-muted)",
          lineHeight: 1.7,
        }}
      >
        <div className="mb-1 font-semibold" style={{ color: "var(--col-text)" }}>
          CSV format (header row required)
        </div>
        name,roll_number,class_name,photo<br />
        Arjun Sharma,CS101,10-A,arjun.jpg<br />
        Priya Patel,CS102,10-A,priya.jpg<br />
        <div className="mt-2" style={{ opacity: 0.7 }}>
          The ZIP must contain all photos referenced in the <em>photo</em> column.
        </div>
      </div>

      {error && (
        <div className="alert-error mb-5">{error}</div>
      )}

      {/* Upload form */}
      {!results && (
        <div className="card">
          <form onSubmit={handleBulkSubmit}>
            <div className="p-6 space-y-5">

              <Field label="CSV Roster File">
                <div
                  style={{
                    borderLeft: "2px solid var(--col-border2)",
                    background: "var(--col-surface2)",
                  }}
                >
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    ref={csvRef}
                    onChange={(e) => setCsvFile(e.target.files[0] || null)}
                    required
                    className="block w-full text-sm cursor-pointer py-2.5 px-3"
                    style={{ color: "var(--col-muted)" }}
                  />
                </div>
              </Field>

              <Field label="Photos ZIP File">
                <div
                  style={{
                    borderLeft: "2px solid var(--col-border2)",
                    background: "var(--col-surface2)",
                  }}
                >
                  <input
                    type="file"
                    accept=".zip,application/zip"
                    ref={zipRef}
                    onChange={(e) => setZipFile(e.target.files[0] || null)}
                    required
                    className="block w-full text-sm cursor-pointer py-2.5 px-3"
                    style={{ color: "var(--col-muted)" }}
                  />
                </div>
              </Field>

            </div>

            <div style={{ borderTop: "1px solid var(--col-border)" }}>
              <button
                type="submit"
                disabled={loading || !csvFile || !zipFile}
                className="btn-amber"
              >
                {loading ? "Importing…" : "Import Students"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Results */}
      {results && (
        <div className="card page-enter">

          {/* Summary bar */}
          <div
            className="px-5 py-3 flex items-center gap-6"
            style={{ borderBottom: "1px solid var(--col-border)", background: "var(--col-surface2)" }}
          >
            <Stat label="Total" value={results.total} />
            <Stat label="Enrolled" value={results.succeeded} color="var(--col-green, #4caf50)" />
            <Stat label="Failed" value={results.failed} color={results.failed > 0 ? "var(--col-red)" : undefined} />
            <button
              onClick={handleReset}
              className="ml-auto text-xs px-3 py-1.5 transition-colors duration-150"
              style={{ border: "1px solid var(--col-border2)", color: "var(--col-muted)" }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "var(--col-text)")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "var(--col-muted)")}
            >
              Import another
            </button>
          </div>

          {/* Per-row results table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--col-border)" }}>
                  <th className="th">Row</th>
                  <th className="th">Name</th>
                  <th className="th">Roll #</th>
                  <th className="th">Result</th>
                </tr>
              </thead>
              <tbody>
                {results.results.map((r) => (
                  <tr
                    key={r.row}
                    style={{ borderBottom: "1px solid var(--col-border)" }}
                  >
                    <td
                      className="px-5 py-3 text-xs"
                      style={{ fontFamily: "'Space Mono', monospace", color: "var(--col-muted)" }}
                    >
                      {r.row}
                    </td>
                    <td className="px-5 py-3 font-medium">{r.name || "—"}</td>
                    <td
                      className="px-5 py-3 text-xs"
                      style={{ fontFamily: "'Space Mono', monospace", color: "var(--col-muted)" }}
                    >
                      {r.roll_number || "—"}
                    </td>
                    <td className="px-5 py-3">
                      {r.status === "ok" ? (
                        <span
                          className="text-xs font-semibold"
                          style={{ color: "var(--col-green, #4caf50)" }}
                        >
                          Enrolled
                        </span>
                      ) : (
                        <span
                          className="text-xs"
                          style={{ color: "var(--col-red)" }}
                        >
                          {r.detail}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

        </div>
      )}

    </div>
  );
}

/* Small stat display used in the results summary bar */
function Stat({ label, value, color }) {
  return (
    <div className="flex flex-col items-start">
      <span
        className="text-xs tracking-widest uppercase"
        style={{ color: "var(--col-muted)", fontSize: "0.6rem" }}
      >
        {label}
      </span>
      <span
        className="text-lg font-bold leading-tight"
        style={{ fontFamily: "'Space Mono', monospace", color: color || "var(--col-text)" }}
      >
        {value}
      </span>
    </div>
  );
}

/* Reusable labeled field wrapper */
function Field({ label, children }) {
  return (
    <div>
      <label className="field-label">{label}</label>
      {children}
    </div>
  );
}
