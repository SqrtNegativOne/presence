import { describe, it, expect, beforeEach } from "bun:test";

describe("ModelContext storage and normalization logic", () => {
  const mockStorage = new Map();

  beforeEach(() => {
    mockStorage.clear();
    globalThis.localStorage = {
      getItem: (k) => mockStorage.get(k) ?? null,
      setItem: (k, v) => mockStorage.set(k, String(v)),
      removeItem: (k) => mockStorage.delete(k),
      clear: () => mockStorage.clear(),
    };
  });

  it("reads stored engine from localStorage", () => {
    mockStorage.set("recognition_engine", "cloud");
    const stored = globalThis.localStorage.getItem("recognition_engine");
    expect(stored).toBe("cloud");
  });

  it("defaults to local if not set in localStorage", () => {
    const stored = globalThis.localStorage.getItem("recognition_engine");
    const engine = stored && (stored === "local" || stored === "cloud") ? stored : "local";
    expect(engine).toBe("local");
  });

  it("persists updated engine to localStorage", () => {
    const saveEngine = (val) => {
      const normalized = (val || "local").toLowerCase() === "cloud" ? "cloud" : "local";
      globalThis.localStorage.setItem("recognition_engine", normalized);
      return normalized;
    };

    expect(saveEngine("CLOUD")).toBe("cloud");
    expect(globalThis.localStorage.getItem("recognition_engine")).toBe("cloud");

    expect(saveEngine("local")).toBe("local");
    expect(globalThis.localStorage.getItem("recognition_engine")).toBe("local");
  });
});
