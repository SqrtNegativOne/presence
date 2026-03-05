import React, { useEffect, useState } from "react";
import { deleteStudent, listStudents } from "../api";

export default function StudentsPage() {
  const [students, setStudents] = useState([]);
  const [filter, setFilter]     = useState(""); // class filter
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);

  // useEffect re-runs whenever `filter` changes, so the list stays in sync
  // with whatever the teacher types in the filter input.
  useEffect(() => {
    loadStudents(filter || null);
  }, [filter]);

  async function loadStudents(className) {
    setLoading(true);
    setError(null);
    try {
      const data = await listStudents(className);
      setStudents(data.students);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id, name) {
    if (!window.confirm(`Remove ${name} from the roster? This cannot be undone.`)) return;
    try {
      await deleteStudent(id);
      // Update the list in-place — no need to re-fetch from the server
      setStudents((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  }

  return (
    <div className="page-enter">

      {/* ── Page header ─────────────────────────────────────────────── */}
      <div className="flex items-end justify-between mb-8 flex-wrap gap-4">
        <div>
          <span className="page-label">02 / Roster</span>
          <h1
            className="text-3xl font-bold"
            style={{ fontFamily: "'Fraunces', serif" }}
          >
            Enrolled Students
          </h1>
        </div>

        {/* Class filter */}
        <div className="flex items-center gap-2">
          <span className="field-label" style={{ marginBottom: 0 }}>
            Filter
          </span>
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="class e.g. 10-A"
            className="field-input w-32"
            style={{ paddingTop: "0.375rem", paddingBottom: "0.375rem" }}
          />
          {filter && (
            <button
              onClick={() => setFilter("")}
              className="text-xs transition-colors duration-150"
              style={{ color: "var(--col-muted)" }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "var(--col-red)")}
              onMouseLeave={(e) => (e.currentTarget.style.color = "var(--col-muted)")}
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="alert-error mb-6">{error}</div>
      )}

      {/* Loading state */}
      {loading ? (
        <div
          className="text-center py-20 text-xs tracking-[0.2em] uppercase"
          style={{ color: "var(--col-muted)" }}
        >
          Loading roster…
        </div>

      ) : students.length === 0 ? (
        /* Empty state */
        <div
          className="text-center py-20 card"
        >
          <p
            className="text-2xl mb-2"
            style={{ fontFamily: "'Fraunces', serif", color: "var(--col-muted)" }}
          >
            No students found
          </p>
          <p className="text-sm" style={{ color: "var(--col-muted)", opacity: 0.6 }}>
            {filter
              ? `No students enrolled in class "${filter}".`
              : "Go to Enroll to add students to the system."}
          </p>
        </div>

      ) : (
        /* Data table */
        <div className="card page-enter-d1">

          {/* Row count meta-bar */}
          <div
            className="px-5 py-2.5"
            style={{
              borderBottom: "1px solid var(--col-border)",
              background: "var(--col-surface2)",
            }}
          >
            <span
              className="text-xs font-mono tracking-widest"
              style={{ color: "var(--col-muted)" }}
            >
              {students.length} {students.length !== 1 ? "STUDENTS" : "STUDENT"}
              {filter ? ` · CLASS ${filter.toUpperCase()}` : ""}
            </span>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--col-border)" }}>
                  <th className="th">Name</th>
                  <th className="th">Roll #</th>
                  <th className="th">Class</th>
                  <th className="th">Enrolled</th>
                  <th className="th"></th>
                </tr>
              </thead>
              <tbody>
                {students.map((s, i) => (
                  <TableRow
                    key={s.id}
                    student={s}
                    even={i % 2 === 0}
                    onDelete={handleDelete}
                  />
                ))}
              </tbody>
            </table>
          </div>

        </div>
      )}

    </div>
  );
}

/*
  Extracted into its own component so each row can manage its own
  hover state independently without re-rendering the whole table.
*/
function TableRow({ student: s, even, onDelete }) {
  const [hovered, setHovered] = useState(false);
  const [delHover, setDelHover] = useState(false);

  return (
    <tr
      style={{
        borderBottom: "1px solid var(--col-border)",
        background: hovered
          ? "rgba(240,180,41,0.035)"
          : even
            ? "transparent"
            : "rgba(255,255,255,0.015)",
        transition: "background 0.1s",
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <td className="px-5 py-3.5 font-medium">{s.name}</td>
      <td
        className="px-5 py-3.5 text-xs"
        style={{ fontFamily: "'Space Mono', monospace", color: "var(--col-muted)" }}
      >
        {s.roll_number}
      </td>
      <td className="px-5 py-3.5">
        <span className="badge-class">{s.class_name}</span>
      </td>
      <td
        className="px-5 py-3.5 text-xs"
        style={{ fontFamily: "'Space Mono', monospace", color: "var(--col-muted)", opacity: 0.7 }}
      >
        {s.enrolled_at ? s.enrolled_at.slice(0, 10) : "—"}
      </td>
      <td className="px-5 py-3.5 text-right">
        <button
          onClick={() => onDelete(s.id, s.name)}
          className="text-xs px-2 py-1 transition-colors duration-150"
          style={{
            border: `1px solid ${delHover ? "var(--col-red)" : "var(--col-border2)"}`,
            color: delHover ? "var(--col-red)" : "var(--col-muted)",
          }}
          onMouseEnter={() => setDelHover(true)}
          onMouseLeave={() => setDelHover(false)}
        >
          Remove
        </button>
      </td>
    </tr>
  );
}
