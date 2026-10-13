import { Countdown, useNow } from "../../shared/components/Countdown";
import type { PreRegistration } from "./PreRegistrationsPage";
import {
  noRequirements,
  registrationFields,
  type Requirements,
  type AttendeeInfo,
} from "./registration";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { ApiError, apiRequest } from "../../shared/api/client";
import { useAuth } from "../auth/AuthContext";
interface Request {
  requestKey: string;
  eventId: string;
  ticketTypeId: string;
  quantity: number;
  attendeeInfo?: AttendeeInfo;
}
export function BookingForm({
  eventId,
  ticketTypeId,
  available,
  opensAt,
  closesAt,
  requirements = noRequirements,
}: {
  eventId: string;
  ticketTypeId: string;
  available: number;
  opensAt: string;
  closesAt: string;
  requirements?: Requirements;
}) {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const storageKey = `sems-booking:${user?.id}:${eventId}:${ticketTypeId}`;
  const [pending, setPending] = useState<Request | null>(() => {
    try {
      return JSON.parse(sessionStorage.getItem(storageKey) ?? "null");
    } catch {
      return null;
    }
  });
  const [quantity, setQuantity] = useState(pending?.quantity ?? 1);
  const [info, setInfo] = useState<AttendeeInfo>(pending?.attendeeInfo ?? {});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const now = useNow();
  const beforeOpening = now < Date.parse(opensAt);
  const [message, setMessage] = useState("");
  const [applying, setApplying] = useState(false);
  const requestedPreRegistration =
    new URLSearchParams(location.search).get("preRegistration") ===
    ticketTypeId;
  const [loadingSaved, setLoadingSaved] = useState(
    requestedPreRegistration && !pending,
  );
  useEffect(() => {
    if (!token || !requestedPreRegistration || pending) {
      setLoadingSaved(false);
      return;
    }
    let active = true;
    setLoadingSaved(true);
    apiRequest<PreRegistration>(
      `/api/v1/pre-registrations/${eventId}`,
      {},
      token,
    )
      .then((saved) => {
        if (!active) return;
        if (saved.ticketTypeId !== ticketTypeId) {
          setError(
            "Your saved ticket selection has changed. Return to My pre-registrations.",
          );
          return;
        }
        setInfo(saved.attendeeInfo);
        setQuantity(saved.quantity);
        setMessage(
          "Saved pre-registration loaded. Review your details before confirming.",
        );
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoadingSaved(false);
      });
    return () => {
      active = false;
    };
  }, [eventId, ticketTypeId, token, requestedPreRegistration]);
  async function applyProfile() {
    if (busy || pending || applying || loadingSaved) return;
    setApplying(true);
    setMessage("");
    try {
      const saved = await apiRequest<AttendeeInfo>(
        "/api/v1/profile",
        {},
        token!,
      );
      const selected = Object.fromEntries(
        registrationFields
          .filter((f) => requirements[f.rule] && saved[f.key])
          .map((f) => [f.key, saved[f.key]]),
      );
      setInfo((current) => ({ ...current, ...selected }));
      setMessage(
        Object.keys(selected).length
          ? "Saved details applied. Review and edit them for this registration."
          : "No matching saved details. Add them in My profile.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setApplying(false);
    }
  }
  const open = now >= Date.parse(opensAt) && now < Date.parse(closesAt);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy || applying || loadingSaved) return;
    if (beforeOpening && !pending) {
      setBusy(true);
      setError("");
      setMessage("");
      try {
        await apiRequest(
          `/api/v1/pre-registrations/${eventId}`,
          {
            method: "PUT",
            body: JSON.stringify({
              ticketTypeId,
              quantity,
              attendeeInfo: info,
            }),
          },
          token!,
        );
        setMessage(
          "Pre-registration saved. No places are held. Return when registration opens to confirm.",
        );
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
      return;
    }
    const request = pending ?? {
      requestKey: crypto.randomUUID(),
      eventId,
      ticketTypeId,
      quantity,
      attendeeInfo: Object.fromEntries(
        Object.entries(info).map(([key, value]) => [
          key,
          value?.trim() || null,
        ]),
      ),
    };
    sessionStorage.setItem(storageKey, JSON.stringify(request));
    setPending(request);
    setBusy(true);
    setError("");
    try {
      const booking = await apiRequest<{ id: string }>(
        "/api/v1/bookings",
        { method: "POST", body: JSON.stringify(request) },
        token!,
      );
      sessionStorage.removeItem(storageKey);
      setPending(null);
      navigate(`/bookings/${booking.id}`);
    } catch (e) {
      // A transport/server failure may have happened after commit: keep the same key and payload.
      if (e instanceof ApiError && e.status >= 400 && e.status < 500) {
        sessionStorage.removeItem(storageKey);
        setPending(null);
      }
      setError(
        e instanceof Error
          ? e.message
          : "Unable to confirm booking. Retry the same request.",
      );
    } finally {
      setBusy(false);
    }
  }
  if (!user && !beforeOpening && !open) return <p>Registration has closed.</p>;
  if (!user && available === 0) return <p>This ticket type is sold out.</p>;
  if (!user)
    return (
      <Link
        className="secondary-button"
        to="/login"
        state={{ from: { pathname: `/events/${eventId}` } }}
      >
        {beforeOpening ? "Sign in to pre-register" : "Sign in to book"}
      </Link>
    );
  return (
    <form onSubmit={submit} className="booking-form">
      <label>
        Quantity
        <input
          aria-label={`Quantity for ticket ${ticketTypeId}`}
          type="number"
          min={1}
          max={10}
          required
          value={quantity}
          disabled={busy || applying || loadingSaved || !!pending}
          onChange={(e) => setQuantity(Number(e.target.value))}
        />
      </label>
      {(registrationFields.some((f) => requirements[f.rule]) ||
        requirements.customFieldLabel) && (
        <fieldset
          className="registration-settings"
          disabled={busy || applying || loadingSaved || !!pending}
        >
          <legend>Registration contact</legend>
          <p className="muted">
            One contact for this booking. These details are shared with the
            event organizer.
          </p>
          <div className="actions">
            <button
              type="button"
              className="secondary-button"
              onClick={applyProfile}
            >
              Apply saved details
            </button>
            <Link to="/profile">Manage saved details</Link>
          </div>
          {registrationFields
            .filter((f) => requirements[f.rule])
            .map((f) => (
              <label key={f.key}>
                {f.label}
                <input
                  type={f.type}
                  required
                  maxLength={f.max}
                  value={info[f.key] ?? ""}
                  onChange={(e) =>
                    setInfo({ ...info, [f.key]: e.target.value })
                  }
                />
              </label>
            ))}
          {requirements.customFieldLabel && (
            <label>
              {requirements.customFieldLabel}
              <textarea
                required
                maxLength={500}
                value={info.customAnswer ?? ""}
                onChange={(e) =>
                  setInfo({ ...info, customAnswer: e.target.value })
                }
              />
            </label>
          )}
          {!registrationFields.some((f) => requirements[f.rule]) &&
            !requirements.customFieldLabel && (
              <p>No additional information required.</p>
            )}
        </fieldset>
      )}
      <p className="muted">Free admission · Up to 10 places per booking.</p>
      {beforeOpening ? (
        <>
          <Countdown target={opensAt} label="Registration opens in" />
          <p>
            Pre-fill your details now. Confirm after opening; pre-registration
            does not hold tickets.
          </p>
        </>
      ) : open ? (
        <Countdown target={closesAt} label="Registration closes in" />
      ) : (
        <p>Registration is closed for this ticket type.</p>
      )}
      {loadingSaved && <p role="status">Loading pre-registration…</p>}
      {message && (
        <p role="status">
          {message} <Link to="/pre-registrations">My pre-registrations →</Link>
        </p>
      )}
      {available === 0 && <p>This ticket type is sold out.</p>}
      {pending && (
        <p role="status">
          A request is saved. Retry to retrieve its result before making another
          booking. You can also check <Link to="/bookings">My tickets</Link>.
        </p>
      )}
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
      <button
        className="primary-button"
        disabled={
          busy ||
          applying ||
          loadingSaved ||
          (!pending && ((!open && !beforeOpening) || available < quantity))
        }
      >
        {busy
          ? beforeOpening && !pending
            ? "Saving…"
            : "Confirming…"
          : pending
            ? "Retry booking"
            : beforeOpening
              ? "Save pre-registration"
              : "Confirm free booking"}
      </button>
    </form>
  );
}
