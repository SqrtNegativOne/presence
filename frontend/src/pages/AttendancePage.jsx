import React, { useRef, useState } from "react";
import { downloadCsv, matchEmbeddings, processAttendance } from "../api";
import CameraCapture from "../components/CameraCapture";
import { useModel } from "../context/ModelContext";
import localFaceService from "../services/localFaceService";

export default function AttendancePage() {
  const { isLocal } = useModel();

  // Form state
  const [className, setClassName] = useState("");
  const [date, setDate]           = useState(todayStr());
  const [photo, setPhoto]         = useState(null);
  const [preview, setPreview]     = useState(null);

  // Source selection: "upload" | "camera"
  const [sourceMode, setSourceMode] = useState("upload");

  // Result state
  const [result, setResult]   = useState(null);   // full API response object
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

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
    setResult(null);
    setError(null);
    setSourceMode(newMode);
  }

  function handlePhotoChange(e) {
    const file = e.target.files[0] || null;
    if (preview && preview.startsWith("blob:")) {
      URL.revokeObjectURL(preview);
    }
    setPhoto(file);
    if (file) {
      const reader = new FileReader();
      reader.onload = (ev) => setPreview(ev.target.result);
      reader.readAsDataURL(file);
    } else {
      setPreview(null);
    }
    // Clear previous results whenever a new photo is selected
    setResult(null);
    setError(null);
  }

  function handleCameraCapture({ file, previewUrl }) {
    if (preview && preview.startsWith("blob:")) {
      URL.revokeObjectURL(preview);
    }
    setPhoto(file);
    setPreview(previewUrl);
    setResult(null);
    setError(null);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!photo) {
      setError(sourceMode === "camera" ? "Please capture a group photo first." : "Please select a group photo.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      if (isLocal) {
        // Step 1: Detect all faces locally in the browser
        const detectedFaces = await localFaceService.detectAllFaces(photo);
        if (detectedFaces.length === 0) {
          throw new Error("No faces detected in group photo. Please ensure good lighting and clear faces.");
        }

        // Step 2: Extract embeddings
        const embeddings = detectedFaces.map((f) => f.descriptor);

        // Compute SHA-256 hash of photo for session tracking / deduplication
        let photoHash = null;
        try {
          const buffer = await photo.arrayBuffer();
          const hashBuffer = await crypto.subtle.digest("SHA-256", buffer);
          photoHash = Array.from(new Uint8Array(hashBuffer))
            .map((b) => b.toString(16).padStart(2, "0"))
            .join("");
        } catch {
          // Non-critical
        }

        // Step 3: Match embeddings against enrolled students
        const matchData = await matchEmbeddings({
          class_name: className.trim(),
          attendance_date: date,
          embeddings,
          model_type: "faceapi",
          photo_hash: photoHash,
        });

        // Step 4: Map backend match records to detected face bounding boxes
        let faceResults = [];
        let absentStudents = [];

        if (Array.isArray(matchData.results)) {
          faceResults = matchData.results
            .filter((r) => r.status !== "absent")
            .map((r) => ({
              ...r,
              bbox: r.bbox || (r.face_index != null && detectedFaces[r.face_index]?.box) || null,
            }));
          absentStudents = matchData.results.filter((r) => r.status === "absent");
        } else {
          const records = matchData.records || [];
          const presentRecords = records.filter((r) => r.status === "present");
          const unmatched = matchData.unmatched_faces || [];

          for (let i = 0; i < detectedFaces.length; i++) {
            const det = detectedFaces[i];
            const matched = presentRecords.find((r) => r.face_index === i);
            if (matched) {
              faceResults.push({
                face_index: i,
                bbox: det.box,
                student_id: matched.student_id,
                name: matched.name,
                roll_number: matched.roll_number,
                class_name: matched.class_name || className,
                status: "recognized",
                similarity: matched.similarity,
              });
            } else {
              const unrec = unmatched.find((u) => u.face_index === i);
              faceResults.push({
                face_index: i,
                bbox: det.box,
                student_id: null,
                name: "Unknown",
                roll_number: null,
                class_name: className,
                status: "unknown",
                similarity: unrec?.similarity || null,
              });
            }
          }

          absentStudents = records
            .filter((r) => r.status === "absent")
            .map((a) => ({
              face_index: null,
              bbox: null,
              student_id: a.student_id,
              name: a.name,
              roll_number: a.roll_number,
              class_name: a.class_name || className,
              status: "absent",
              similarity: null,
            }));
        }

        // Step 5: Annotate the group photo on a client-side canvas
        const annotatedDataUrl = await localFaceService.annotateImage(photo, faceResults);

        const recognizedCount =
          matchData.recognized_count ?? faceResults.filter((f) => f.status === "recognized").length;
        const unknownCount =
          matchData.unknown_count ?? faceResults.filter((f) => f.status === "unknown").length;
        const totalFaces = matchData.total_faces ?? detectedFaces.length;

        setResult({
          session_id: matchData.session_id,
          annotated_image: annotatedDataUrl,
          date: matchData.attendance_date || matchData.date || date,
          class_name: matchData.class_name || className,
          results: [...faceResults, ...absentStudents],
          total_faces: totalFaces,
          recognized_count: recognizedCount,
          unknown_count: unknownCount,
          absent_count: matchData.absent_count ?? absentStudents.length,
        });
      } else {
        // Cloud mode: upload full photo via FormData to FastAPI backend
        const fd = new FormData();
        fd.append("class_name",      className.trim());
        fd.append("attendance_date", date);
        fd.append("photo",           photo, photo.name || "attendance_group_photo.jpg");

        const data = await processAttendance(fd);
        setResult(data);
      }
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
        <div className="flex items-center justify-between gap-4 mb-2">
          <span className="page-label mb-0">03 / Attendance</span>
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
          Take Attendance
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--col-muted)" }}>
          {isLocal
            ? "Group photo is scanned directly in your browser — faces are matched against enrolled embeddings."
            : "Upload a group photo — faces are matched against enrolled students via server ML."}
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
                    Capture the whole classroom clearly with all faces visible.
                  </p>

                  {/* Preview for uploaded file */}
                  {preview && (
                    <div
                      className="mt-3 flex justify-center p-3 relative"
                      style={{ background: "var(--col-surface2)", border: "1px solid var(--col-border)" }}
                    >
                      <img
                        src={preview}
                        alt="Selected group photo"
                        className="max-h-56 w-auto object-contain"
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
                  filename="attendance_group_photo.jpg"
                  promptText="Snap classroom group photo for attendance"
                  defaultFacingMode="environment"
                />
              )}
            </div>

            {error && (
              <div className="alert-error">{error}</div>
            )}
          </div>

          <div style={{ borderTop: "1px solid var(--col-border)" }}>
            <button type="submit" disabled={loading} className="btn-amber">
              {loading
                ? isLocal
                  ? "Scanning faces locally… this may take a few seconds"
                  : "Scanning faces on server… this may take 5–15 s"
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
                Backend returns plain base64 (cloud mode), while local mode
                generates a canvas data URL ("data:image/png;base64,...").
              */}
              <img
                src={
                  result.annotated_image?.startsWith("data:")
                    ? result.annotated_image
                    : `data:image/png;base64,${result.annotated_image}`
                }
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
