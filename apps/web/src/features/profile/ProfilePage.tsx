import { useEffect, useState, type FormEvent } from "react";
import { apiRequest } from "../../shared/api/client";
import { useAuth } from "../auth/AuthContext";
import {
  registrationFields,
  type AttendeeInfo,
} from "../bookings/registration";
export function ProfilePage() {
  const { token } = useAuth();
  const [info, setInfo] = useState<AttendeeInfo>({});
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    apiRequest<AttendeeInfo>("/api/v1/profile", {}, token!)
      .then((data) => {
        if (active) {
          setInfo(data);
          setLoaded(true);
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token, attempt]);
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      setInfo(
        await apiRequest<AttendeeInfo>(
          "/api/v1/profile",
          { method: "PUT", body: JSON.stringify(info) },
          token!,
        ),
      );
      setMessage("Saved. Apply these details when you register for an event.");
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function clear() {
    setBusy(true);
    try {
      await apiRequest("/api/v1/profile", { method: "DELETE" }, token!);
      setInfo({});
      setError("");
      setMessage(
        "Saved details cleared. Existing bookings and pre-registrations keep their own details.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="app-shell">
      <p className="eyebrow">YOUR SPACE</p>
      <h1>Saved registration details</h1>
      <p>
        Save only the details you want to reuse. Nothing is shared with an
        organizer until you submit a booking. Applying details never changes
        your account email.
      </p>
      {loading ? (
        <p role="status">Loading profile…</p>
      ) : loaded ? (
        <form className="card profile-form" onSubmit={save}>
          <fieldset disabled={busy}>
            <legend>Personal information · optional</legend>
            {registrationFields.map((f) => (
              <label key={f.key}>
                {f.label}
                <input
                  type={f.type}
                  maxLength={f.max}
                  value={info[f.key] ?? ""}
                  onChange={(e) =>
                    setInfo({ ...info, [f.key]: e.target.value })
                  }
                />
              </label>
            ))}
          </fieldset>
          <div className="actions">
            <button disabled={busy}>Save details</button>
            <button
              type="button"
              className="secondary-button"
              disabled={busy}
              onClick={clear}
            >
              Clear saved details
            </button>
          </div>
        </form>
      ) : null}
      {error && (
        <div role="alert">
          <p>{error}</p>
          <button onClick={() => setAttempt((n) => n + 1)}>
            Reload profile
          </button>
        </div>
      )}
      {message && <p role="status">{message}</p>}
    </main>
  );
}
