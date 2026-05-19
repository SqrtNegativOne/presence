import React from "react";
import { BrowserRouter, Link, NavLink, Route, Routes } from "react-router-dom";
import AttendancePage from "./pages/AttendancePage";
import EnrollPage from "./pages/EnrollPage";
import LoginPage from "./pages/LoginPage";
import SettingsPage from "./pages/SettingsPage";
import StudentsPage from "./pages/StudentsPage";
import { useAuth } from "./auth/AuthContext";
import RequireAuth from "./auth/RequireAuth";

const navLinkClass = ({ isActive }) =>
  `flex items-center gap-1.5 text-[0.65rem] tracking-[0.15em] uppercase font-semibold transition-colors duration-150 pb-0.5 ${
    isActive
      ? "text-[var(--col-accent)]"
      : "text-[var(--col-muted)] hover:text-[var(--col-text)]"
  }`;

function NavItem({ to, label }) {
  return (
    <NavLink to={to} className={navLinkClass}>
      {({ isActive }) => (
        <>
          <span
            className="w-1 h-1 rounded-full transition-opacity duration-150"
            style={{ background: "var(--col-accent)", opacity: isActive ? 1 : 0 }}
          />
          {label}
        </>
      )}
    </NavLink>
  );
}

function UserBadge() {
  const { user, logout } = useAuth();
  if (!user) return null;
  return (
    <div className="ml-auto flex items-center gap-3">
      {user.picture_url && (
        <img
          src={user.picture_url}
          alt=""
          className="w-6 h-6 rounded-full"
          style={{ border: "1px solid var(--col-border2)" }}
          referrerPolicy="no-referrer"
        />
      )}
      <span
        className="text-xs font-mono"
        style={{ color: "var(--col-muted)" }}
        title={user.email}
      >
        {user.is_demo ? "Demo Teacher" : user.name}
      </span>
      <button
        onClick={logout}
        className="text-[0.65rem] tracking-[0.15em] uppercase font-semibold transition-colors duration-150"
        style={{ color: "var(--col-muted)" }}
        onMouseEnter={(e) => (e.currentTarget.style.color = "var(--col-red)")}
        onMouseLeave={(e) => (e.currentTarget.style.color = "var(--col-muted)")}
      >
        Sign out
      </button>
    </div>
  );
}

export default function App() {
  const { user } = useAuth();

  return (
    <BrowserRouter>
      <div className="min-h-screen">

        <nav
          className="px-8 py-4 flex items-center gap-10"
          style={{
            background: "var(--col-surface)",
            borderBottom: "1px solid var(--col-border)",
          }}
        >
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
            <span
              className="w-1.5 h-1.5 mt-0.5 flex-shrink-0"
              style={{ background: "var(--col-accent)" }}
            />
          </Link>

          {user && (
            <div className="flex items-center gap-8">
              <NavItem to="/enroll"     label="Enroll" />
              <NavItem to="/students"   label="Students" />
              <NavItem to="/attendance" label="Attendance" />
              <NavItem to="/settings"   label="Settings" />
            </div>
          )}

          <UserBadge />
        </nav>

        <main className="max-w-5xl mx-auto px-6 py-10">
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/"           element={<RequireAuth><Home /></RequireAuth>} />
            <Route path="/enroll"     element={<RequireAuth><EnrollPage /></RequireAuth>} />
            <Route path="/students"   element={<RequireAuth><StudentsPage /></RequireAuth>} />
            <Route path="/attendance" element={<RequireAuth><AttendancePage /></RequireAuth>} />
            <Route path="/settings"   element={<RequireAuth><SettingsPage /></RequireAuth>} />
          </Routes>
        </main>

      </div>
    </BrowserRouter>
  );
}

/* ── Home / Landing Page ───────────────────────────────────────────────── */
function Home() {
  const { user } = useAuth();
  return (
    <div className="page-enter">

      <div className="py-16 max-w-2xl">
        <p className="page-label mb-4" style={{ opacity: 1 }}>
          Face Recognition · Attendance System
        </p>
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
          Upload a group photo. A pluggable recognition engine identifies each
          student and marks their attendance automatically.{" "}
          {user?.is_demo &&
            <span style={{ color: "var(--col-accent)" }}>
              Try the demo class — four students are already enrolled.
            </span>}
        </p>

        <div className="flex gap-4 flex-wrap">
          <ActionLink to="/enroll" primary>Enroll Students</ActionLink>
          <ActionLink to="/attendance">Take Attendance</ActionLink>
          <ActionLink to="/settings">Pick Engine</ActionLink>
        </div>
      </div>

      <div
        className="page-enter-d1 grid grid-cols-1 sm:grid-cols-3 gap-px mt-4"
        style={{ background: "var(--col-border)", border: "1px solid var(--col-border)" }}
      >
        {[
          { step: "01", title: "Enroll",
            desc: "Upload one solo portrait per student. The chosen engine extracts a face embedding and stores it." },
          { step: "02", title: "Photograph",
            desc: "Take a group photo of the class. Any smartphone camera works." },
          { step: "03", title: "Export",
            desc: "Attendance is marked instantly. Download the session as a CSV spreadsheet." },
        ].map((item) => (
          <div key={item.step} className="p-6" style={{ background: "var(--col-surface)" }}>
            <span className="page-label" style={{ opacity: 0.6 }}>{item.step}</span>
            <h3 className="text-base font-semibold mt-2 mb-1.5"
                style={{ fontFamily: "'Fraunces', serif" }}>{item.title}</h3>
            <p className="text-sm leading-relaxed" style={{ color: "var(--col-muted)" }}>
              {item.desc}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

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
        <span className="text-sm transition-transform duration-150 group-hover:translate-x-1"
              style={{ display: "inline-block" }}>→</span>
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
      <span className="text-sm transition-transform duration-150 group-hover:translate-x-1"
            style={{ display: "inline-block" }}>→</span>
    </Link>
  );
}
