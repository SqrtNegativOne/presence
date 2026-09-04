import React, { useRef, useState } from "react";
import { enrollStudent, enrollStudentEmbedding } from "../api";
import CameraCapture from "../components/CameraCapture";
import { useModel } from "../context/ModelContext";
import localFaceService from "../services/localFaceService";

export default function EnrollPage() {
  const { isLocal } = useModel();

  // Form field state
  const [name, setName]           = useState("");
  const [roll, setRoll]           = useState("");
  const [className, setClassName] = useState("");
  const [photo, setPhoto]         = useState(null);    // File or Blob object
  const [preview, setPreview]     = useState(null);    // data URL or object URL for preview

  // Source selection: "upload" | "camera"
  const [sourceMode, setSourceMode] = useState("upload");

  // UI state
  const [loading, setLoading] = useState(false);
  const [toast, setToast]     = useState(null); // { type: "success"|"error", msg }

  const fileInputRef = useRef(null);

  function clearPhoto() {
    if (preview && preview.startsWith("blob:")) {
      URL.revokeObjectURL(preview);
    }
    setPhoto(null);
    setPreview(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleSourceModeChange(newMode) {
    if (newMode === sourceMode) return;
    clearPhoto();
    setSourceMode(newMode);
  }

  // When the user picks a file, generate a preview immediately using FileReader.
  // FileReader reads the file in the browser without uploading it.
  function handlePhotoChange(e) {
    const file = e.target.files[0];
    if (!file) return;
    if (preview && preview.startsWith("blob:")) {
      URL.revokeObjectURL(preview);
    }
    setPhoto(file);
    const reader = new FileReader();
    reader.onload = (ev) => setPreview(ev.target.result);
    reader.readAsDataURL(file); // converts file → base64 data URL
  }

  function handleCameraCapture({ file, previewUrl }) {
    if (preview && preview.startsWith("blob:")) {
      URL.revokeObjectURL(preview);
    }
    setPhoto(file);
    setPreview(previewUrl);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!photo) {
      showToast("error", sourceMode === "camera" ? "Please capture a portrait photo." : "Please select a photo.");
      return;
    }

    setLoading(true);
    setToast(null);

    try {
      if (isLocal) {
        // Local mode: detect face in browser using face-api.js and extract 128-d descriptor
        const faceData = await localFaceService.detectSingleFace(photo);

        const result = await enrollStudentEmbedding({
          name: name.trim(),
          roll_number: roll.trim(),
          class_name: className.trim(),
          embedding: faceData.descriptor,
          model_type: "faceapi",
        });

        showToast("success", `${result.name || name} enrolled successfully (Local Face-API engine).`);
      } else {
        // Cloud mode: upload full photo via FormData to FastAPI backend
        const fd = new FormData();
        fd.append("name",        name.trim());
        fd.append("roll_number", roll.trim());
        fd.append("class_name",  className.trim());
        fd.append("photo",       photo, photo.name || "solo_portrait.jpg");

        const result = await enrollStudent(fd);
        showToast("success", `${result.name} enrolled successfully (Cloud InsightFace engine).`);
      }

      // Reset form on success
      setName("");
      setRoll("");
      setClassName("");
      clearPhoto();
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
        <div className="flex items-center justify-between gap-4 mb-2">
          <span className="page-label mb-0">01 / Enroll</span>
          <span
            className="text-[0.65rem] font-mono tracking-wider uppercase px-2 py-0.5 border"
            style={{
              borderColor: isLocal ? "var(--col-accent)" : "var(--col-border2)",
              color: isLocal ? "var(--col-accent)" : "var(--col-muted)",
              background: "var(--col-surface2)",
            }}
          >
            {isLocal ? "🔒 Local Mode (Browser)" : "☁️ Cloud Mode (Server)"}
          </span>
        </div>
        <h1
          className="text-3xl font-bold"
          style={{ fontFamily: "'Fraunces', serif" }}
        >
          New Student
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--col-muted)" }}>
          {isLocal
            ? "Photo is processed locally in your browser — only the 128-d face embedding is saved."
            : "Upload one clear, frontal portrait per student for server-side processing."}
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
              {/* Mode toggle: Upload File vs Use Camera */}
              <div className="flex border border-[var(--col-border)] bg-[var(--col-surface2)] p-1 gap-1 mb-3">
                <button
                  type="button"
                  onClick={() => handleSourceModeChange("upload")}
                  className={`flex-1 py-1.5 px-3 text-xs uppercase tracking-wider font-semibold transition-colors duration-150 ${
                    sourceMode === "upload"
                      ? "bg-[var(--col-accent)] text-[#06060f]"
                      : "text-[var(--col-muted)] hover:text-[var(--col-text)]"
                  }`}
                >
                  📁 Upload File
                </button>
                <button
                  type="button"
                  onClick={() => handleSourceModeChange("camera")}
                  className={`flex-1 py-1.5 px-3 text-xs uppercase tracking-wider font-semibold transition-colors duration-150 ${
                    sourceMode === "camera"
                      ? "bg-[var(--col-accent)] text-[#06060f]"
                      : "text-[var(--col-muted)] hover:text-[var(--col-text)]"
                  }`}
                >
                  📷 Use Camera
                </button>
              </div>

              {sourceMode === "upload" ? (
                <div>
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
                      required={!photo}
                      className="block w-full text-sm cursor-pointer py-2.5 px-3"
                      style={{ color: "var(--col-muted)" }}
                    />
                  </div>
                  <p className="text-xs mt-1.5" style={{ color: "var(--col-muted)" }}>
                    Must contain exactly one face. Clear, well-lit, frontal.
                  </p>

                  {/* Photo preview — shown once a file is chosen */}
                  {preview && (
                    <div
                      className="mt-3 flex justify-center p-4 relative"
                      style={{ background: "var(--col-surface2)", border: "1px solid var(--col-border)" }}
                    >
                      <img
                        src={preview}
                        alt="Photo preview"
                        className="max-h-48 object-contain"
                        style={{ border: "2px solid var(--col-accent)", opacity: 0.9 }}
                      />
                      <button
                        type="button"
                        onClick={clearPhoto}
                        className="absolute top-2 right-2 text-xs font-mono px-2 py-1 bg-[var(--col-surface)] text-[var(--col-muted)] hover:text-[var(--col-red)] border border-[var(--col-border)]"
                      >
                        ✕ Remove
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <CameraCapture
                  onCapture={handleCameraCapture}
                  onClear={clearPhoto}
                  previewUrl={preview}
                  filename="solo_portrait.jpg"
                  promptText="Snap student solo portrait photo"
                  defaultFacingMode="environment"
                />
              )}
            </Field>

          </div>

          {/* Submit button separated by a border — like a form footer */}
          <div style={{ borderTop: "1px solid var(--col-border)" }}>
            <button type="submit" disabled={loading} className="btn-amber">
              {loading
                ? isLocal
                  ? "Analyzing Face Locally…"
                  : "Processing…"
                : "Enroll Student"}
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
