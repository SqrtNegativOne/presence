import React, { useEffect, useState } from "react";
import { listRecognizers, setPreferredRecognizer } from "../api";
import { useAuth } from "../auth/AuthContext";

const SPEED_COLOR = {
  fastest: "var(--col-green)",
  fast: "var(--col-green)",
  balanced: "var(--col-accent)",
  accurate: "#a78bfa",
};

export default function SettingsPage() {
  const { user, refresh } = useAuth();
  const [data, setData] = useState(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    listRecognizers()
      .then(setData)
      .catch((e) => setToast({ type: "error", msg: e.message }));
  }, []);

  async function pick(name) {
    if (!data || name === data.preferred) return;
    setSaving(true);
    setToast(null);
    try {
      await setPreferredRecognizer(name);
      setData({ ...data, preferred: name });
      await refresh();
      setToast({ type: "success", msg: `Switched to ${name}. Re-enroll students if matching fails.` });
    } catch (e) {
      setToast({ type: "error", msg: e.message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page-enter max-w-3xl">

      <div className="mb-8">
        <span className="page-label">Settings</span>
        <h1
          className="text-3xl font-bold"
          style={{ fontFamily: "'Fraunces', serif" }}
        >
          Recognition Engine
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--col-muted)" }}>
          Trade accuracy for speed. Embeddings are tied to the engine that produced
          them — switching engines means students enrolled with the previous engine
          will not be matched until you re-enroll them.
        </p>
      </div>

      {toast && (
        <div className={`mb-6 ${toast.type === "success" ? "alert-success" : "alert-error"}`}>
          {toast.msg}
        </div>
      )}

      {!data ? (
        <div className="text-center py-12 text-xs tracking-[0.2em] uppercase"
             style={{ color: "var(--col-muted)" }}>Loading…</div>
      ) : (
        <div className="space-y-3">
          {data.recognizers.map((r) => {
            const isPreferred = r.name === data.preferred;
            const disabled = !r.available || saving;
            return (
              <button
                key={r.name}
                onClick={() => pick(r.name)}
                disabled={disabled}
                className="w-full text-left p-5 transition-colors duration-150"
                style={{
                  border: `1px solid ${isPreferred ? "var(--col-accent)" : "var(--col-border)"}`,
                  background: isPreferred ? "rgba(240,180,41,0.06)" : "var(--col-surface)",
                  opacity: r.available ? 1 : 0.45,
                  cursor: disabled ? "not-allowed" : "pointer",
                }}
              >
                <div className="flex items-start gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="text-base font-semibold"
                            style={{ fontFamily: "'Fraunces', serif" }}>
                        {r.display_name}
                      </span>
                      <span
                        className="text-[0.65rem] font-mono tracking-[0.15em] uppercase px-2 py-0.5"
                        style={{
                          color: SPEED_COLOR[r.speed] || "var(--col-muted)",
                          border: `1px solid ${SPEED_COLOR[r.speed] || "var(--col-border)"}`,
                        }}
                      >
                        {r.speed}
                      </span>
                      {!r.available && (
                        <span className="text-[0.65rem] uppercase tracking-[0.15em]"
                              style={{ color: "var(--col-red)" }}>
                          unavailable
                        </span>
                      )}
                    </div>
                    <p className="text-sm" style={{ color: "var(--col-muted)" }}>
                      {r.description}
                    </p>
                    <p className="text-xs mt-2 font-mono"
                       style={{ color: "var(--col-muted)", opacity: 0.65 }}>
                      embedding_dim={r.embedding_dim} · threshold={r.threshold}
                    </p>
                  </div>
                  {isPreferred && (
                    <span className="badge-class" style={{ background: "var(--col-accent)", color: "#06060f" }}>
                      Active
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      )}

      {user?.is_demo && (
        <p className="text-xs mt-8" style={{ color: "var(--col-muted)" }}>
          You are signed in as the demo user — settings here only affect the
          demo account.
        </p>
      )}
    </div>
  );
}
