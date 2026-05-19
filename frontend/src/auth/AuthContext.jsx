import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { fetchMe, getToken, logout as apiLogout, setToken } from "../api";

const AuthContext = createContext(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // On mount, if we have a token, try to load the user.
  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!getToken()) {
        setLoading(false);
        return;
      }
      try {
        const me = await fetchMe();
        if (!cancelled) setUser(me);
      } catch {
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  // If any API call hits 401, the api layer clears the token and fires this
  // event — bring the UI back in sync.
  useEffect(() => {
    function onLogout() { setUser(null); }
    window.addEventListener("presence:unauthenticated", onLogout);
    return () => window.removeEventListener("presence:unauthenticated", onLogout);
  }, []);

  const completeLogin = useCallback((session) => {
    setToken(session.token);
    setUser(session.user);
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const me = await fetchMe();
      setUser(me);
    } catch { /* ignore */ }
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, completeLogin, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}
