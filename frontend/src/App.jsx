import React from "react";
import { BrowserRouter, Link, NavLink, Route, Routes } from "react-router-dom";
import AttendancePage from "./pages/AttendancePage";
import EnrollPage from "./pages/EnrollPage";
import StudentsPage from "./pages/StudentsPage";

/*
  NavLink's className prop receives { isActive } — React Router tells us
  whether this link is the current page. We use that to show/hide the
  amber indicator dot.
*/
const navLinkClass = ({ isActive }) =>
  `flex items-center gap-1.5 text-[0.65rem] tracking-[0.15em] uppercase font-semibold transition-colors duration-150 pb-0.5 ${
    isActive
      ? "text-[var(--col-accent)]"
      : "text-[var(--col-muted)] hover:text-[var(--col-text)]"
  }`;

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen">

        {/* ── Navigation ─────────────────────────────────────────────── */}
        <nav
          className="px-8 py-4 flex items-center gap-10"
          style={{
            background: "var(--col-surface)",
            borderBottom: "1px solid var(--col-border)",
          }}
        >
          {/* Wordmark — Fraunces at opsz 9 has tighter, more compact serifs */}
          <Link
            to="/"
            className="flex items-center gap-2 mr-6"
            style={{ textDecoration: "none" }}
          >
            <span
              className="text-lg font-bold leading-none tracking-tight"
              style={{
                fontFamily: "'Fraunces', serif",
                fontVariationSettings: "'opsz' 9",
                color: "var(--col-text)",
              }}
            >
              Presence
            </span>
            {/* Small amber square — a subtle mark of precision */}
            <span
              className="w-1.5 h-1.5 mt-0.5 flex-shrink-0"
              style={{ background: "var(--col-accent)" }}
            />
          </Link>

          <div className="flex items-center gap-8">
            <NavLink to="/enroll" className={navLinkClass}>
              {({ isActive }) => (
                <>
                  {/* Amber dot indicator for the active route */}
                  <span
                    className="w-1 h-1 rounded-full transition-opacity duration-150"
                    style={{
                      background: "var(--col-accent)",
                      opacity: isActive ? 1 : 0,
                    }}
                  />
                  Enroll
                </>
              )}
            </NavLink>

            <NavLink to="/students" className={navLinkClass}>
              {({ isActive }) => (
                <>
                  <span
                    className="w-1 h-1 rounded-full transition-opacity duration-150"
                    style={{
                      background: "var(--col-accent)",
                      opacity: isActive ? 1 : 0,
                    }}
                  />
                  Students
                </>
              )}
            </NavLink>

            <NavLink to="/attendance" className={navLinkClass}>
              {({ isActive }) => (
                <>
                  <span
                    className="w-1 h-1 rounded-full transition-opacity duration-150"
                    style={{
                      background: "var(--col-accent)",
                      opacity: isActive ? 1 : 0,
                    }}
                  />
                  Attendance
                </>
              )}
            </NavLink>
          </div>
        </nav>

        {/* ── Page content ───────────────────────────────────────────── */}
        <main className="max-w-5xl mx-auto px-6 py-10">
          <Routes>
            <Route path="/"           element={<Home />} />
            <Route path="/enroll"     element={<EnrollPage />} />
            <Route path="/students"   element={<StudentsPage />} />
            <Route path="/attendance" element={<AttendancePage />} />
          </Routes>
        </main>

      </div>
    </BrowserRouter>
  );
}

/* ── Home / Landing Page ───────────────────────────────────────────────── */
function Home() {
  return (
    <div className="page-enter">

      {/* Hero */}
      <div className="py-16 max-w-2xl">
        <p
          className="page-label mb-4"
          style={{ opacity: 1 }}
        >
          Face Recognition · Attendance System
        </p>

        {/*
          Fraunces at opsz 144 ("optical sizing") activates its display variant:
          wider ink traps, more contrast between thick and thin strokes.
          It looks like text carved or printed at a grand scale.
        */}
        <h1
          className="font-bold leading-none mb-5"
          style={{
            fontFamily: "'Fraunces', serif",
            fontVariationSettings: "'opsz' 144",
            fontSize: "clamp(2.5rem, 6vw, 4.5rem)",
            color: "var(--col-text)",
          }}
        >
          Mark attendance
          <br />
          <span style={{ color: "var(--col-accent)" }}>in seconds.</span>
        </h1>

        <p
          className="text-base max-w-md mb-10 leading-relaxed"
          style={{ color: "var(--col-muted)" }}
        >
          Upload a group photo. ArcFace identifies each student using 512-dimensional
          embeddings and marks their attendance automatically.
        </p>

        {/* Action links styled as precise rectangular buttons */}
        <div className="flex gap-4 flex-wrap">
          <ActionLink to="/enroll" primary>
            Enroll Students
          </ActionLink>
          <ActionLink to="/attendance">
            Take Attendance
          </ActionLink>
        </div>
      </div>

      {/* ── How it works — 3-step grid ─────────────────────────────── */}
      {/*
        The grid uses a 1px gap with a border-colored background.
        Each cell has its own surface background, which creates the look
        of cells separated by hairline borders — no extra border CSS needed.
      */}
      <div
        className="page-enter-d1 grid grid-cols-1 sm:grid-cols-3 gap-px mt-4"
        style={{ background: "var(--col-border)", border: "1px solid var(--col-border)" }}
      >
        {[
          {
            step: "01",
            title: "Enroll",
            desc: "Upload one solo portrait per student. The AI extracts a 512-dimensional face embedding and stores it.",
          },
          {
            step: "02",
            title: "Photograph",
            desc: "Take a group photo of the class. Any smartphone camera works fine.",
          },
          {
            step: "03",
            title: "Export",
            desc: "Attendance is marked instantly. Download the session as a CSV spreadsheet.",
          },
        ].map((item) => (
          <div
            key={item.step}
            className="p-6"
            style={{ background: "var(--col-surface)" }}
          >
            <span
              className="page-label"
              style={{ opacity: 0.6 }}
            >
              {item.step}
            </span>
            <h3
              className="text-base font-semibold mt-2 mb-1.5"
              style={{ fontFamily: "'Fraunces', serif" }}
            >
              {item.title}
            </h3>
            <p
              className="text-sm leading-relaxed"
              style={{ color: "var(--col-muted)" }}
            >
              {item.desc}
            </p>
          </div>
        ))}
      </div>

    </div>
  );
}

/* Reusable action link button */
function ActionLink({ to, children, primary }) {
  const [hovered, setHovered] = React.useState(false);

  if (primary) {
    return (
      <Link
        to={to}
        className="group inline-flex items-center gap-3 px-6 py-3.5"
        style={{ background: "var(--col-accent)", color: "#06060f", textDecoration: "none" }}
      >
        <span className="text-xs font-bold tracking-[0.12em] uppercase">{children}</span>
        <span
          className="text-sm transition-transform duration-150 group-hover:translate-x-1"
          style={{ display: "inline-block" }}
        >
          →
        </span>
      </Link>
    );
  }

  return (
    <Link
      to={to}
      className="group inline-flex items-center gap-3 px-6 py-3.5 transition-colors duration-150"
      style={{
        border: `1px solid ${hovered ? "var(--col-accent)" : "var(--col-border2)"}`,
        color: hovered ? "var(--col-accent)" : "var(--col-text)",
        textDecoration: "none",
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <span className="text-xs font-bold tracking-[0.12em] uppercase">{children}</span>
      <span
        className="text-sm transition-transform duration-150 group-hover:translate-x-1"
        style={{ display: "inline-block" }}
      >
        →
      </span>
    </Link>
  );
}
