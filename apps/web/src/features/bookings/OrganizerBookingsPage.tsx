import { HomeLink } from "../../shared/components/HomeLink";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiRequest } from "../../shared/api/client";
import { formatDateTime } from "../../shared/components/dateTime";
import { useAuth } from "../auth/AuthContext";
import { RegistrationSummary, type AttendeeInfo } from "./registration";
interface Order {
  id: string;
  status: string;
  ticketName: string;
  quantity: number;
  createdAt: string;
  attendeeInfo: AttendeeInfo;
  customFieldLabel: string | null;
}
export function OrganizerBookingsPage() {
  const { id } = useParams();
  const { token } = useAuth();
  const [page, setPage] = useState(0);
  const [data, setData] = useState<{
    items: Order[];
    totalPages: number;
    totalElements: number;
  } | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setData(null);
    setError("");
    apiRequest<typeof data>(
      `/api/v1/organizer/events/${id}/bookings?page=${page}&size=10`,
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
  }, [id, page, token, retry]);
  return (
    <main className="app-shell">
      <div className="page-breadcrumbs"><HomeLink /><Link className="back-link" to="/organizer/events">← Back to my events</Link></div>
      <p className="eyebrow">ORGANIZER WORKSPACE</p>
      <h1>Registration list</h1>
      <p>
        Booking contacts for this event. Each order may include more than one
        place.
      </p>
      {error ? (
        <p role="alert" className="error-message">
          {error} <button onClick={() => setRetry(retry + 1)}>Retry</button>
        </p>
      ) : !data ? (
        <p role="status">Loading registrations…</p>
      ) : (
        <>
          <p>{data.totalElements} bookings</p>
          {data.items.length === 0 && <p>No bookings yet.</p>}
          {data.items.map((b) => (
            <article key={b.id} className="card">
              <span className="badge">{b.status}</span>
              <h2>
                {b.ticketName} · {b.quantity} places
              </h2>
              <p className="muted">
                {formatDateTime(b.createdAt)} · {b.id}
              </p>
              <RegistrationSummary
                info={b.attendeeInfo}
                customFieldLabel={b.customFieldLabel}
              />
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
