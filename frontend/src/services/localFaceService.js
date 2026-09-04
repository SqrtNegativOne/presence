import * as faceapi from "@vladmandic/face-api";

/**
 * Singleton promise for model loading to guarantee models are loaded at most once.
 */
let modelsPromise = null;

/**
 * Helper to convert various input types (File, Blob, string URL, HTMLImageElement, HTMLCanvasElement)
 * into an HTMLImageElement or HTMLCanvasElement that faceapi can process.
 *
 * @param {HTMLImageElement|HTMLCanvasElement|File|Blob|string} input
 * @returns {Promise<HTMLImageElement|HTMLCanvasElement>}
 */
export async function toImageElement(input) {
  if (typeof window === "undefined") {
    throw new Error("localFaceService can only be executed in a browser environment");
  }

  if (input instanceof HTMLImageElement) {
    if (!input.complete || input.naturalWidth === 0) {
      await new Promise((resolve, reject) => {
        input.onload = () => resolve();
        input.onerror = (err) => reject(new Error("Image element failed to load"));
      });
    }
    return input;
  }

  if (typeof HTMLCanvasElement !== "undefined" && input instanceof HTMLCanvasElement) {
    return input;
  }

  if (typeof Blob !== "undefined" && input instanceof Blob) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      const objectUrl = URL.createObjectURL(input);
      img.onload = () => {
        URL.revokeObjectURL(objectUrl);
        resolve(img);
      };
      img.onerror = (err) => {
        URL.revokeObjectURL(objectUrl);
        reject(new Error("Failed to load image from file/blob"));
      };
      img.src = objectUrl;
    });
  }

  if (typeof input === "string") {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => resolve(img);
      img.onerror = (err) => reject(new Error("Failed to load image from URL"));
      img.src = input;
    });
  }

  throw new Error("Unsupported image input type. Expected Image, Canvas, File, Blob, or URL string.");
}

/**
 * Loads face-api models from static assets directory (/models).
 * Cached so multiple calls reuse the same load promise.
 *
 * @param {string} [modelUri='/models']
 * @returns {Promise<boolean>}
 */
export async function loadModels(modelUri = "/models") {
  if (
    faceapi.nets.ssdMobilenetv1.isLoaded &&
    faceapi.nets.faceLandmark68Net.isLoaded &&
    faceapi.nets.faceRecognitionNet.isLoaded
  ) {
    return true;
  }

  if (!modelsPromise) {
    modelsPromise = (async () => {
      try {
        await Promise.all([
          faceapi.nets.ssdMobilenetv1.loadFromUri(modelUri),
          faceapi.nets.faceLandmark68Net.loadFromUri(modelUri),
          faceapi.nets.faceRecognitionNet.loadFromUri(modelUri),
        ]);
        return true;
      } catch (err) {
        modelsPromise = null; // reset to allow retry on error
        throw new Error(`Failed to load face recognition models: ${err.message}`);
      }
    })();
  }

  return modelsPromise;
}

/**
 * Detects a single face in the input photo and extracts its 128-d descriptor.
 * Throws validation error if 0 faces or >1 face are detected.
 *
 * @param {HTMLImageElement|HTMLCanvasElement|File|Blob|string} input
 * @returns {Promise<{
 *   descriptor: number[],
 *   box: { x: number, y: number, width: number, height: number },
 *   totalFaces: number
 * }>}
 */
export async function detectSingleFace(input) {
  const img = await toImageElement(input);
  await loadModels();

  // Detect all faces first to strictly enforce exactly 1 face for enrollment
  const allDetections = await faceapi
    .detectAllFaces(img, new faceapi.SsdMobilenetv1Options({ minConfidence: 0.5 }))
    .withFaceLandmarks()
    .withFaceDescriptors();

  const count = allDetections.length;
  if (count === 0) {
    throw new Error("No face detected in photo. Please ensure good lighting and a clear frontal view.");
  }
  if (count > 1) {
    throw new Error(`Found ${count} faces. Enrollment photos must contain exactly ONE face.`);
  }

  const face = allDetections[0];
  const descriptor = Array.from(face.descriptor);
  const box = {
    x: Math.round(face.detection.box.x),
    y: Math.round(face.detection.box.y),
    width: Math.round(face.detection.box.width),
    height: Math.round(face.detection.box.height),
  };

  return {
    descriptor,
    box,
    totalFaces: 1,
  };
}

/**
 * Detects all faces in an image and extracts their 128-d descriptors and bounding boxes.
 *
 * @param {HTMLImageElement|HTMLCanvasElement|File|Blob|string} input
 * @param {number} [minConfidence=0.5]
 * @returns {Promise<Array<{
 *   index: number,
 *   descriptor: number[],
 *   box: { x: number, y: number, width: number, height: number },
 *   score: number
 * }>>}
 */
export async function detectAllFaces(input, minConfidence = 0.5) {
  const img = await toImageElement(input);
  await loadModels();

  const detections = await faceapi
    .detectAllFaces(img, new faceapi.SsdMobilenetv1Options({ minConfidence }))
    .withFaceLandmarks()
    .withFaceDescriptors();

  return detections.map((det, index) => ({
    index,
    descriptor: Array.from(det.descriptor),
    box: {
      x: Math.round(det.detection.box.x),
      y: Math.round(det.detection.box.y),
      width: Math.round(det.detection.box.width),
      height: Math.round(det.detection.box.height),
    },
    score: det.detection.score,
  }));
}

/**
 * Client-side image annotation for local recognition mode.
 * Draws bounding boxes (green for recognized, red for unknown), names, and similarity scores
 * on a <canvas> and returns the annotated image as a base64 PNG data URL.
 *
 * @param {HTMLImageElement|HTMLCanvasElement|File|Blob|string} inputImage
 * @param {Array<{
 *   bbox?: [number, number, number, number] | { x: number, y: number, width: number, height: number },
 *   box?: { x: number, y: number, width: number, height: number },
 *   face_index?: number,
 *   name?: string,
 *   status?: string,
 *   similarity?: number
 * }>} faceResults
 * @returns {Promise<string>} Base64 data URL ("data:image/png;base64,...")
 */
export async function annotateImage(inputImage, faceResults = []) {
  const img = await toImageElement(inputImage);
  const canvas = document.createElement("canvas");
  const width = img.naturalWidth || img.width;
  const height = img.naturalHeight || img.height;

  canvas.width = width;
  canvas.height = height;

  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("Unable to create 2D canvas rendering context");
  }

  // Draw base photo
  ctx.drawImage(img, 0, 0, width, height);

  // Dynamic font and line sizing based on image resolution
  const fontSize = Math.max(14, Math.round(width / 60));
  const boxThickness = Math.max(2, Math.round(width / 300));
  ctx.font = `600 ${fontSize}px sans-serif`;

  for (const face of faceResults) {
    const rawBox = face.bbox || face.box;
    if (!rawBox) continue;

    let x, y, w, h;
    if (Array.isArray(rawBox)) {
      x = Math.round(rawBox[0]);
      y = Math.round(rawBox[1]);
      w = Math.round(rawBox[2] - rawBox[0]);
      h = Math.round(rawBox[3] - rawBox[1]);
    } else {
      x = Math.round(rawBox.x);
      y = Math.round(rawBox.y);
      w = Math.round(rawBox.width);
      h = Math.round(rawBox.height);
    }

    const isRecognized = face.status === "recognized";
    const strokeColor = isRecognized ? "#22c55e" : "#ef4444"; // emerald green / red

    // Draw bounding box
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = boxThickness;
    ctx.strokeRect(x, y, w, h);

    // Compose label text
    let label = "";
    if (face.face_index != null) {
      label += `${face.face_index} `;
    }
    label += face.name || (isRecognized ? "Recognized" : "Unknown");

    if (face.similarity != null && face.similarity !== undefined) {
      const pct = Math.round(face.similarity * 100);
      label += ` (${pct}%)`;
    }

    // Measure label text for pill background
    const metrics = ctx.measureText(label);
    const textWidth = metrics.width;
    const paddingX = Math.max(4, Math.round(fontSize * 0.3));
    const paddingY = Math.max(2, Math.round(fontSize * 0.15));
    const pillWidth = textWidth + paddingX * 2;
    const pillHeight = fontSize + paddingY * 2;

    let pillY = y - pillHeight - 2;
    if (pillY < 0) {
      pillY = y + h + 2; // place below box if too close to top edge
    }

    // Background rectangle for text label
    ctx.fillStyle = strokeColor;
    ctx.fillRect(x, pillY, pillWidth, pillHeight);

    // Text rendering inside pill
    ctx.fillStyle = "#ffffff";
    ctx.textBaseline = "middle";
    ctx.fillText(label, x + paddingX, pillY + pillHeight / 2);
  }

  return canvas.toDataURL("image/png");
}

export default {
  loadModels,
  toImageElement,
  detectSingleFace,
  detectAllFaces,
  annotateImage,
};
