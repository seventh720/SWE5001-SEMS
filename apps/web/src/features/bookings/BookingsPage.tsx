import { HomeLink } from "../../shared/components/HomeLink";
import { RegistrationSummary, type AttendeeInfo } from "./registration";
import { formatDateTime } from "../../shared/components/dateTime";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import QRCode from "qrcode";
import { apiRequest } from "../../shared/api/client";
import { useAuth } from "../auth/AuthContext";
export interface Booking {
  id: string;
  eventId: string;
  status: string;
  eventTitle: string;
  eventLocation: string;
  startsAt: string;
  endsAt: string;
  ticketName: string;
  quantity: number;
  amount: number;
  attendeeInfo?: AttendeeInfo;
  eventCancellationReason?: string | null;
  customFieldLabel?: string | null;
  tickets: { id: string; credential: string; state: string }[];
}
function TicketCode({ credential }: { credential: string }) {
  const [image, setImage] = useState("");
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    QRCode.toDataURL(credential, {
      width: 224,
      margin: 4,
      errorCorrectionLevel: "M",
    })
      .then((url) => {
        if (active) setImage(url);
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, [credential]);
  return (
    <>
      {image && (
        <img
          src={image}
          alt="Admission ticket QR code"
          width={224}
          height={224}
        />
      )}
      {error && <p>QR display unavailable. Use the manual code below.</p>}
      <p className="muted">Manual ticket code</p>
      <code className="ticket-credential">{credential}</code>
    </>
  );
}
export function BookingsPage() {
  const { token } = useAuth();
  const [page, setPage] = useState(0);
  const [status, setStatus] = useState("CONFIRMED");
  const [data, setData] = useState<{
    items: Booking[];
    totalPages: number;
  } | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setData(null);
    setError("");
    apiRequest<{ items: Booking[]; totalPages: number }>(
      `/api/v1/bookings?page=${page}&size=10&status=${status}`,
      {},
      token!,
    )
      .then((d) => {
        if (active) setData(d);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [page, status, token, retry]);
  return (
    <main className="app-shell">
      <HomeLink />
      <p className="eyebrow">YOUR NEXT SHARED MOMENT</p>
      <h1>My tickets</h1>
      <p>
        Confirmed bookings and cancelled bookings are shown separately. Saved pre-registrations are not confirmed tickets.
      </p>
      <div className="booking-status-switch" role="group" aria-label="Booking status">
        {(["CONFIRMED", "CANCELLED"] as const).map(value => (
          <button key={value} aria-pressed={status === value} onClick={() => {
            if (status === value) return;
            setData(null);
            setPage(0);
            setStatus(value);
          }}>{value === "CONFIRMED" ? "Confirmed" : "Cancelled"}</button>
        ))}
      </div>
      <h2>{status === "CONFIRMED" ? "Confirmed bookings" : "Cancelled bookings"}</h2>
      {status === "CANCELLED" && <p className="muted">These bookings have been cancelled. Their tickets cannot be used for admission.</p>}
      {error ? (
        <p role="alert" className="error-message">
          {error} <button onClick={() => setRetry(retry + 1)}>Retry</button>
        </p>
      ) : !data ? (
        <p role="status">Loading bookings…</p>
      ) : (
        <>
          {data.items.length === 0 && (
            <section className="card">
              <h3>{status === "CONFIRMED" ? "No confirmed bookings yet." : "No cancelled bookings."}</h3>
              <Link to="/events">Discover events →</Link>
            </section>
          )}
          {data.items.map((b) => (
            <article className="card event-card" key={b.id}>
              <div>
                <span className={`badge ${b.status === "CANCELLED" ? "badge-cancelled" : ""}`}>{b.status === "CANCELLED" ? "Cancelled" : "Confirmed"}</span>
                <h2>{b.eventTitle}</h2>
                <p>
                  {b.ticketName} · {b.quantity}{" "}
                  {b.quantity === 1 ? "ticket" : "tickets"} · Free
                </p>
                <p className="muted">
                  {formatDateTime(b.startsAt)} · {b.eventLocation}
                </p>
              </div>
              <Link className="secondary-button" to={`/bookings/${b.id}`}>
                {b.status === "CANCELLED" ? "View cancellation" : "View tickets"} ↗
              </Link>
            </article>
          ))}
          <div className="actions">
            <button disabled={page === 0} onClick={() => setPage(page - 1)}>
              Previous
            </button>
            <span>Page {page + 1}</span>
            <button
              disabled={page + 1 >= data.totalPages}
              onClick={() => setPage(page + 1)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </main>
  );
}
export function BookingDetail() {
  const { id } = useParams();
  const { token } = useAuth();
  const [booking, setBooking] = useState<Booking | null>(null);
  const [error, setError] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setBooking(null);
    setError("");
    apiRequest<Booking>(`/api/v1/bookings/${id}`, {}, token!)
      .then((b) => {
        if (active) setBooking(b);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [id, token, retry]);
  async function cancel() {
    setBusy(true);
    setError("");
    try {
      setBooking(
        await apiRequest<Booking>(
          `/api/v1/bookings/${id}/cancel`,
          { method: "POST" },
          token!,
        ),
      );
      setConfirm(false);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Cancellation failed. Retry safely.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="app-shell">
      <div className="page-breadcrumbs"><HomeLink /><Link className="back-link" to="/bookings">← Back to my tickets</Link></div>
      {error && (
        <p className="error-message" role="alert">
          {error}{" "}
          <button
            disabled={busy}
            onClick={() => {
              setConfirm(false);
              setRetry(retry + 1);
            }}
          >
            Reload booking
          </button>
        </p>
      )}
      {!booking && !error && <p role="status">Loading booking…</p>}
      {booking && (
        <>
          <p className="eyebrow">BOOKING / {booking.status}</p>
          <h1>{booking.eventTitle}</h1>
          {!booking.eventCancellationReason&&<Link to={`/events/${booking.eventId}`}>
            View current event details →
          </Link>}
          <p>
            {booking.eventLocation} · {formatDateTime(booking.startsAt)}
          </p>
          <p>
            {booking.ticketName} · {booking.quantity} tickets · Total: Free
          </p>
          <p className="muted">Booking reference: {booking.id}</p>
          {booking.status === "CANCELLED" ? (
            <p role="status">
              {booking.eventCancellationReason?`Event cancelled: ${booking.eventCancellationReason} Tickets are no longer valid. Previous check-ins are retained as history.`:"Booking cancelled. Its tickets are no longer valid and the places have been returned."}
            </p>
          ) : (
            <p>
              Each ticket admits one person. Keep its QR and manual code
              private. Show your QR code to event staff for check-in.
            </p>
          )}
          <section className="card">
            <h2>Registration information</h2>
            <RegistrationSummary
              info={booking.attendeeInfo}
              customFieldLabel={booking.customFieldLabel}
            />
          </section>
          <div className="issued-ticket-grid">
            {booking.tickets.map((ticket, n) => (
              <article className="card issued-ticket" key={ticket.id}>
                <span className="badge">{ticket.state}</span>
                <h2>Ticket {n + 1}</h2>
                {booking.status === "CONFIRMED" && ticket.state === "VALID" ? (
                  <TicketCode credential={ticket.credential} />
                ) : (
                  <p>
                    This ticket is{" "}
                    {ticket.state.toLowerCase().replace("_", " ")}.
                  </p>
                )}
              </article>
            ))}
          </div>
          {booking.status === "CONFIRMED" &&
            Date.parse(booking.startsAt) > Date.now() &&
            !booking.tickets.some((t) => t.state === "CHECKED_IN") && (
              <section className="card">
                <h2>Plans changed?</h2>
                <p>
                  You can cancel before the event begins if none of your tickets
                  has been checked in. All tickets in this booking will be
                  cancelled.
                </p>
                {!confirm ? (
                  <button onClick={() => setConfirm(true)}>
                    Cancel booking
                  </button>
                ) : (
                  <div role="group" aria-label="Confirm cancellation">
                    <p>Release all {booking.quantity} places?</p>
                    <div className="actions">
                      <button disabled={busy} onClick={cancel}>
                        {busy ? "Cancelling…" : "Confirm cancellation"}
                      </button>
                      <button disabled={busy} onClick={() => setConfirm(false)}>
                        Keep booking
                      </button>
                    </div>
                  </div>
                )}
              </section>
            )}
        </>
      )}
    </main>
  );
}
