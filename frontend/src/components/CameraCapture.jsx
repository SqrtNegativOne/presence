import React, { useEffect, useRef, useState } from "react";

/**
 * CameraCapture component
 * Enables snapping photos directly from device camera via getUserMedia + canvas.toBlob().
 *
 * Props:
 * - onCapture: ({ blob, file, previewUrl }) => void
 * - onClear: () => void
 * - previewUrl: string | null
 * - filename: string (default: "camera_photo.jpg")
 * - promptText: string
 * - defaultFacingMode: "environment" | "user" (default: "environment")
 */
export default function CameraCapture({
  onCapture,
  onClear,
  previewUrl = null,
  filename = "camera_photo.jpg",
  promptText = "Capture photo using your device camera",
  defaultFacingMode = "environment",
}) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [facingMode, setFacingMode] = useState(defaultFacingMode);
  const [hasMultipleCameras, setHasMultipleCameras] = useState(false);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);

  // Check if device has multiple camera options (e.g. front & back)
  useEffect(() => {
    async function checkCameraDevices() {
      if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
        try {
          const devices = await navigator.mediaDevices.enumerateDevices();
          const videoInputs = devices.filter((d) => d.kind === "videoinput");
          setHasMultipleCameras(videoInputs.length > 1);
        } catch {
          // If permission is not yet granted, enumerateDevices might not list labels/devices fully
        }
      }
    }
    checkCameraDevices();
  }, []);

  // Stop media stream on component unmount
  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, []);

  function stopCamera() {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsStreaming(false);
    setIsLoading(false);
  }

  async function startCamera(modeToUse = facingMode) {
    setError(null);
    setIsLoading(true);

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setIsLoading(false);
      setError("Camera access is not supported by your browser or requires a secure HTTPS/localhost connection.");
      return;
    }

    // Stop existing stream if any
    stopCamera();

    try {
      let stream;
      try {
        // Attempt with requested facingMode (defaults to 'environment' per spec)
        stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: modeToUse,
            width: { ideal: 1920 },
            height: { ideal: 1080 },
          },
          audio: false,
        });
      } catch (constraintErr) {
        // If facingMode or resolution constraint is overconstrained, fallback to basic video
        if (
          constraintErr.name === "OverconstrainedError" ||
          constraintErr.name === "ConstraintNotSatisfiedError"
        ) {
          stream = await navigator.mediaDevices.getUserMedia({
            video: true,
            audio: false,
          });
        } else {
          throw constraintErr;
        }
      }

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setIsStreaming(true);
      setFacingMode(modeToUse);

      // Re-check cameras once permission is granted
      try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoInputs = devices.filter((d) => d.kind === "videoinput");
        setHasMultipleCameras(videoInputs.length > 1);
      } catch {
        // Ignore enumerateDevices error
      }
    } catch (err) {
      let msg = "Could not access camera.";
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        msg = "Camera permission was denied. Please allow camera access in your browser address bar/settings.";
      } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
        msg = "No camera found on this device.";
      } else if (err.name === "NotReadableError" || err.name === "TrackStartError") {
        msg = "Camera is currently in use by another application or tab.";
      } else if (err.name === "SecurityError") {
        msg = "Camera access requires HTTPS or localhost.";
      } else if (err.message) {
        msg = `Camera error: ${err.message}`;
      }
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }

  function capturePhoto() {
    const video = videoRef.current;
    if (!video) return;

    const width = video.videoWidth;
    const height = video.videoHeight;
    if (!width || !height) {
      setError("Camera is still warming up. Please wait a moment and try again.");
      return;
    }

    const canvas = canvasRef.current || document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, width, height);

    canvas.toBlob(
      (blob) => {
        if (!blob) {
          setError("Failed to capture image snapshot from camera.");
          return;
        }

        // Turn off camera tracks once snapshot is taken
        stopCamera();

        let file;
        try {
          file = new File([blob], filename, { type: "image/jpeg" });
        } catch {
          file = blob;
          file.name = filename;
        }

        const newPreviewUrl = URL.createObjectURL(blob);
        onCapture({ blob, file, previewUrl: newPreviewUrl });
      },
      "image/jpeg",
      0.95
    );
  }

  function handleFlip() {
    const nextMode = facingMode === "environment" ? "user" : "environment";
    setFacingMode(nextMode);
    startCamera(nextMode);
  }

  function handleRetake() {
    if (onClear) onClear();
    startCamera(facingMode);
  }

  // If a photo has already been captured, display preview with Retake button
  if (previewUrl) {
    return (
      <div className="space-y-3">
        <div
          className="relative flex justify-center p-3"
          style={{ background: "var(--col-surface2)", border: "1px solid var(--col-border)" }}
        >
          <img
            src={previewUrl}
            alt="Captured photo preview"
            className="max-h-56 w-auto object-contain"
            style={{ border: "2px solid var(--col-accent)" }}
          />
          <div className="absolute top-4 right-4">
            <span className="badge-present">Photo Ready</span>
          </div>
        </div>
        <div className="flex items-center justify-between">
          <span
            className="text-xs"
            style={{ color: "var(--col-muted)", fontFamily: "'Space Mono', monospace" }}
          >
            Captured via camera
          </span>
          <button
            type="button"
            onClick={handleRetake}
            className="btn-ghost text-xs"
          >
            ↺ Retake Photo
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Hidden canvas used for frame capture */}
      <canvas ref={canvasRef} className="hidden" />

      {/* Camera launcher (when camera is not streaming) */}
      {!isStreaming && (
        <div
          className="p-6 text-center"
          style={{
            border: "1px dashed var(--col-border2)",
            background: "var(--col-surface2)",
          }}
        >
          <div className="mb-2 text-3xl">📷</div>
          <p className="text-sm font-medium mb-1">{promptText}</p>
          <p className="text-xs mb-4" style={{ color: "var(--col-muted)" }}>
            Supports laptop webcam or mobile back/front camera
          </p>
          <button
            type="button"
            onClick={() => startCamera(facingMode)}
            disabled={isLoading}
            className="btn-amber inline-block w-auto px-6 py-2"
          >
            {isLoading ? "Starting Camera…" : "Start Camera"}
          </button>
        </div>
      )}

      {/* Video stream viewport (when camera is streaming) */}
      <div
        className={isStreaming ? "relative overflow-hidden" : "hidden"}
        style={{
          border: "1px solid var(--col-border2)",
          background: "#000",
        }}
      >
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-full max-h-[380px] object-contain mx-auto block bg-black"
        />

        {/* Live indicator badge */}
        <div className="absolute top-3 left-3 flex items-center gap-2 bg-[#06060f]/80 px-2 py-1 border border-[var(--col-border)]">
          <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          <span className="text-[10px] font-mono uppercase tracking-widest text-[var(--col-text)]">
            LIVE · {facingMode.toUpperCase()}
          </span>
        </div>

        {/* Action bar below video */}
        <div
          className="p-3 flex items-center justify-between gap-3 flex-wrap"
          style={{
            background: "var(--col-surface)",
            borderTop: "1px solid var(--col-border)",
          }}
        >
          <button
            type="button"
            onClick={capturePhoto}
            className="btn-amber flex-1 py-2"
          >
            Capture Photo
          </button>

          {hasMultipleCameras && (
            <button
              type="button"
              onClick={handleFlip}
              className="btn-ghost py-2"
              title="Flip camera"
            >
              Flip Camera
            </button>
          )}

          <button
            type="button"
            onClick={stopCamera}
            className="btn-ghost py-2"
          >
            Cancel
          </button>
        </div>
      </div>

      {/* Error alert */}
      {error && (
        <div className="alert-error flex items-start justify-between gap-3">
          <span className="text-xs leading-relaxed">{error}</span>
          <button
            type="button"
            onClick={() => setError(null)}
            className="text-xs font-mono text-[var(--col-muted)] hover:text-[var(--col-text)]"
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
}
