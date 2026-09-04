import { describe, it, expect, mock } from "bun:test";

const mockNets = {
  ssdMobilenetv1: {
    isLoaded: false,
    loadFromUri: async () => {
      mockNets.ssdMobilenetv1.isLoaded = true;
    },
  },
  faceLandmark68Net: {
    isLoaded: false,
    loadFromUri: async () => {
      mockNets.faceLandmark68Net.isLoaded = true;
    },
  },
  faceRecognitionNet: {
    isLoaded: false,
    loadFromUri: async () => {
      mockNets.faceRecognitionNet.isLoaded = true;
    },
  },
};

mock.module("@vladmandic/face-api", () => {
  return {
    nets: mockNets,
    SsdMobilenetv1Options: class {
      constructor(opts) {
        this.opts = opts;
      }
    },
    detectAllFaces: () => ({
      withFaceLandmarks: () => ({
        withFaceDescriptors: async () => [],
      }),
    }),
  };
});

const { loadModels, toImageElement } = await import(
  "../src/services/localFaceService.js"
);

describe("localFaceService logic", () => {
  it("loadModels loads models once and returns true", async () => {
    const loaded = await loadModels("/models");
    expect(loaded).toBe(true);
    expect(mockNets.ssdMobilenetv1.isLoaded).toBe(true);
    expect(mockNets.faceLandmark68Net.isLoaded).toBe(true);
    expect(mockNets.faceRecognitionNet.isLoaded).toBe(true);
  });

  it("cached loadModels returns immediately when already loaded", async () => {
    const loadedAgain = await loadModels("/models");
    expect(loadedAgain).toBe(true);
  });

  it("throws when executed without browser window", () => {
    if (typeof window === "undefined") {
      expect(toImageElement("http://localhost/test.jpg")).rejects.toThrow(
        "localFaceService can only be executed in a browser environment"
      );
    }
  });
});
