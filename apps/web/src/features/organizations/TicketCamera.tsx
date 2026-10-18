import {useEffect, useRef, useState} from "react";
import {Select} from "../../shared/components/Select";

function cameraError(error: unknown) {
  const name = (error as {name?: string})?.name;
  if (name === "NotAllowedError") return "Camera permission was denied. Allow camera access in your browser, or use the ticket code below.";
  if (name === "NotFoundError" || name === "OverconstrainedError") return "No matching camera was found. Connect a webcam or use a scanner / ticket code below.";
  if (name === "NotReadableError") return "The camera is unavailable or in use by another app. Close that app and try again.";
  return "Unable to start the camera. Try again, or use the ticket code below.";
}

export function TicketCamera({onScan, onClose}: {onScan: (code: string) => void; onClose: () => void}) {
  const video = useRef<HTMLVideoElement>(null);
  const scan = useRef(onScan);
  scan.current = onScan;
  const [device, setDevice] = useState("");
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [status, setStatus] = useState("Starting camera…");
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let stream: MediaStream | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const preview = video.current!;
    function stop() {
      cancelled = true;
      clearTimeout(timer);
      stream?.getTracks().forEach(track => track.stop());
      if (preview.srcObject === stream) preview.srcObject = null;
    }
    function hidden() { if (document.hidden) { stop(); onClose(); } }
    document.addEventListener("visibilitychange", hidden);
    setError("");
    setStatus("Starting camera…");
    async function start() {
      try {
        if (!window.isSecureContext) {
          setError("Camera scanning needs HTTPS (or localhost on this computer). Open the secure site, or use the ticket code below.");
          return;
        }
        if (!navigator.mediaDevices?.getUserMedia) {
          setError("This browser cannot access a camera. Use another browser, a scanner or the ticket code below.");
          return;
        }
        const {default: decode} = await import("jsqr");
        if (cancelled) return;
        stream = await navigator.mediaDevices.getUserMedia({audio: false, video: device ? {deviceId: {exact: device}} : {facingMode: {ideal: "environment"}, width: {ideal: 1280}, height: {ideal: 720}}});
        if (cancelled) { stream.getTracks().forEach(track => track.stop()); return; }
        preview.srcObject = stream;
        await preview.play();
        if (cancelled) return;
        // Device enumeration is optional; a working default camera must still scan.
        navigator.mediaDevices.enumerateDevices?.().then(list => {
          if (!cancelled) setDevices(list.filter(item => item.kind === "videoinput" && item.deviceId));
        }).catch(() => {});
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("2d", {willReadFrequently: true});
        if (!context) throw new Error("Canvas unavailable");
        setStatus("Point the camera at a ticket QR code. It will check in automatically.");
        function frame() {
          if (cancelled) return;
          try {
            if (preview.readyState >= 2 && preview.videoWidth && preview.videoHeight) {
              const scale = Math.min(1, 960 / preview.videoWidth);
              canvas.width = Math.round(preview.videoWidth * scale);
              canvas.height = Math.round(preview.videoHeight * scale);
              context!.drawImage(preview, 0, 0, canvas.width, canvas.height);
              const pixels = context!.getImageData(0, 0, canvas.width, canvas.height);
              const result = decode(pixels.data, pixels.width, pixels.height, {inversionAttempts: "dontInvert"});
              if (result) {
                const credential = result.data.trim();
                if (/^[a-f0-9]{48}$/.test(credential)) {
                  stop();
                  scan.current(credential);
                  return;
                }
                setStatus("This is not a SEMS ticket QR code. Point the camera at the ticket shown in My tickets.");
              }
            }
            timer = setTimeout(frame, 180);
          } catch {
            stop();
            setError("Unable to read camera frames. Try again, or use the ticket code below.");
          }
        }
        frame();
      } catch (e) {
        if (!cancelled) { stop(); setError(cameraError(e)); }
      }
    }
    void start();
    return () => { stop(); document.removeEventListener("visibilitychange", hidden); };
  }, [device, attempt, onClose]);

  return <section className="ticket-camera" aria-label="Ticket camera scanner">
    <video ref={video} autoPlay muted playsInline aria-label="Camera preview" />
    {error ? <p role="alert">{error}</p> : <p role="status">{status}</p>}
    {devices.length > 1 && <Select label="Camera" value={device} options={[{value: "", label: "Automatic (prefer rear camera)"}, ...devices.map((item, index) => ({value: item.deviceId, label: item.label || `Camera ${index + 1}`}))]} onChange={setDevice} />}
    <div className="camera-actions">
      {error && <button type="button" onClick={() => setAttempt(value => value + 1)}>Retry camera</button>}
      <button type="button" onClick={onClose}>Close camera</button>
    </div>
  </section>;
}
