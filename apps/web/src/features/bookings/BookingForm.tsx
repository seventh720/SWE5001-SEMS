import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, apiRequest } from "../../shared/api/client";
import { useAuth } from "../auth/AuthContext";
interface Request {
  requestKey: string;
  eventId: string;
  ticketTypeId: string;
  quantity: number;
}
export function BookingForm({
  eventId,
  ticketTypeId,
  available,
  opensAt,
  closesAt,
}: {
  eventId: string;
  ticketTypeId: string;
  available: number;
  opensAt: string;
  closesAt: string;
}) {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const storageKey = `sems-booking:${user?.id}:${eventId}:${ticketTypeId}`;
  const [pending, setPending] = useState<Request | null>(() => {
    try {
      return JSON.parse(sessionStorage.getItem(storageKey) ?? "null");
    } catch {
      return null;
    }
  });
  const [quantity, setQuantity] = useState(pending?.quantity ?? 1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const now = Date.now();
  const open = now >= Date.parse(opensAt) && now < Date.parse(closesAt);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    const request = pending ?? {
      requestKey: crypto.randomUUID(),
      eventId,
      ticketTypeId,
      quantity,
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
  if (!user)
    return (
      <Link
        className="secondary-button"
        to="/login"
        state={{ from: { pathname: `/events/${eventId}` } }}
      >
        Sign in to book
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
          disabled={busy || !!pending}
          onChange={(e) => setQuantity(Number(e.target.value))}
        />
      </label>
      <p className="muted">Free admission · Up to 10 places per booking.</p>
      {!open && <p>Sales are currently closed for this ticket type.</p>}
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
        disabled={busy || (!pending && (!open || available < quantity))}
      >
        {busy
          ? "Confirming…"
          : pending
            ? "Retry booking"
            : "Confirm free booking"}
      </button>
    </form>
  );
}
