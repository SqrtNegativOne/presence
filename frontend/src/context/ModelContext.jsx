import React, { createContext, useContext, useState } from "react";

const ModelContext = createContext({
  engine: "local",
  setEngine: () => {},
  isLocal: true,
  isCloud: false,
});

const STORAGE_KEY = "recognition_engine";

// Hosted local-only deployments set VITE_ALLOW_CLOUD=false at build time.
// That forces Local mode and removes the cloud toggle from the UI.
export const CLOUD_ALLOWED = import.meta.env.VITE_ALLOW_CLOUD !== "false";

export function ModelProvider({ children }) {
  const [engine, setEngineState] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const val = stored.toLowerCase();
        if (val === "local" || val === "cloud") {
          return val === "cloud" && !CLOUD_ALLOWED ? "local" : val;
        }
      }
    } catch (e) {
      console.warn("Could not read recognition_engine from localStorage:", e);
    }
    return "local";
  });

  const setEngine = (newEngine) => {
    let normalized = (newEngine || "local").toLowerCase() === "cloud" ? "cloud" : "local";
    if (!CLOUD_ALLOWED) {
      normalized = "local";
    }
    setEngineState(normalized);
    try {
      localStorage.setItem(STORAGE_KEY, normalized);
    } catch (e) {
      console.warn("Could not write recognition_engine to localStorage:", e);
    }
  };

  return (
    <ModelContext.Provider
      value={{
        engine,
        setEngine,
        isLocal: engine === "local",
        isCloud: engine === "cloud",
      }}
    >
      {children}
    </ModelContext.Provider>
  );
}

export function useModel() {
  const context = useContext(ModelContext);
  if (!context) {
    throw new Error("useModel must be used within a ModelProvider");
  }
  return context;
}

export default ModelContext;
