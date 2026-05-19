import React, { useState } from "react";
import { GoogleLogin } from "@react-oauth/google";
import { Navigate, useLocation } from "react-router-dom";
import { signInAsDemo, signInWithGoogle } from "../api";
import { useAuth } from "../auth/AuthContext";

export default function LoginPage() {
  const { user, completeLogin } = useAuth();
  const location = useLocation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  // Already signed in? Go straight to the app.
  if (user) {
    const dest = location.state?.from || "/";
    return <Navigate to={dest} replace />;
  }

  // Frontend reads this from .env.local — see frontend/.env.example
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;

  async function handleGoogleCredential(resp) {
    setBusy(true); setError(null);
    try {
      const session = await signInWithGoogle(resp.credential);
      completeLogin(session);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleDemo() {
    setBusy(true); setError(null);
    try {
      const session = await signInAsDemo();
      completeLogin(session);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-md mx-auto page-enter">

      <div className="mb-8">
        <span className="page-label">Sign in</span>
        <h1
          className="text-3xl font-bold"
          style={{ fontFamily: "'Fraunces', serif" }}
        >
          Welcome to Presence
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--col-muted)" }}>
          Use Google to keep your roster private, or try the demo with sample students.
        </p>
      </div>

      {error && <div className="alert-error mb-6">{error}</div>}

      <div className="card p-6 space-y-5">

        <div>
          <label className="field-label">Google Account</label>
          {clientId ? (
            <div className="flex justify-center py-2">
              <GoogleLogin
                onSuccess={handleGoogleCredential}
                onError={() => setError("Google sign-in failed.")}
                theme="filled_black"
                size="large"
                shape="rectangular"
              />
            </div>
          ) : (
            <div
              className="text-xs p-3"
              style={{
                color: "var(--col-muted)",
                background: "var(--col-surface2)",
                border: "1px solid var(--col-border)",
              }}
            >
              <p>
                <span style={{ color: "var(--col-accent)" }}>VITE_GOOGLE_CLIENT_ID</span>{" "}
                is not set in <code>frontend/.env.local</code> — Google sign-in is disabled.
              </p>
              <p className="mt-1">Use the demo button below to try the app.</p>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3">
          <span className="flex-1" style={{ borderTop: "1px solid var(--col-border)" }}></span>
          <span className="text-xs tracking-[0.18em] uppercase" style={{ color: "var(--col-muted)" }}>or</span>
          <span className="flex-1" style={{ borderTop: "1px solid var(--col-border)" }}></span>
        </div>

        <div>
          <label className="field-label">Demo Mode</label>
          <p className="text-xs mb-3" style={{ color: "var(--col-muted)" }}>
            A demo teacher with four pre-enrolled students. Try the attendance flow with the bundled group photo.
          </p>
          <button
            type="button"
            onClick={handleDemo}
            disabled={busy}
            className="btn-amber w-full"
          >
            {busy ? "Signing in…" : "Continue as Demo"}
          </button>
        </div>

      </div>

      <p className="text-xs mt-6 text-center" style={{ color: "var(--col-muted)" }}>
        Your student photos and embeddings stay on your own server. Presence
        never sends them to a third party.
      </p>

    </div>
  );
}
