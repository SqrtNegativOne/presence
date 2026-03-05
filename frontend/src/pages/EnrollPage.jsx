import React, { useRef, useState } from "react";
import { enrollStudent } from "../api";

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
