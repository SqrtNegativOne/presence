import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

/**
 * Wraps protected routes. Shows a tiny loader while we resolve the token,
 * redirects to /login if the user isn't authenticated.
 */
export default function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div
        className="text-center py-20 text-xs tracking-[0.2em] uppercase"
        style={{ color: "var(--col-muted)" }}
      >
        Loading…
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}
