import { HomeLink } from "../../shared/components/HomeLink";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiRequest } from "../../shared/api/client";
import { Countdown, useNow } from "../../shared/components/Countdown";
import { formatDateTime } from "../../shared/components/dateTime";
import { useAuth } from "../auth/AuthContext";
import type { AttendeeInfo } from "./registration";
export interface PreRegistration {
  eventId: string;
  ticketTypeId: string;
  quantity: number;
  attendeeInfo: AttendeeInfo;
  eventTitle: string;
  eventLocation: string;
  ticketName: string;
  opensAt: string;
  closesAt: string;
  startsAt: string;
  status: string;
}
export function PreRegistrationsPage() {
  const { token } = useAuth();
  const now = useNow();
  const [page, setPage] = useState(0);
  const [revision, setRevision] = useState(0);
  const [data, setData] = useState<{
    items: PreRegistration[];
    totalPages: number;
  } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    setData(null);
    setError("");
    apiRequest<{ items: PreRegistration[]; totalPages: number }>(
      `/api/v1/pre-registrations?page=${page}&size=10`,
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
  }, [page, revision, token]);
  async function remove(event: string) {
    setBusy(true);
    try {
      await apiRequest(
        `/api/v1/pre-registrations/${event}`,
        { method: "DELETE" },
        token!,
      );
      setRevision((n) => n + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="app-shell">
      <HomeLink />
      <p className="eyebrow">READY WHEN YOU ARE</p>
      <h1>My pre-registrations</h1>
      <p>
        Saved details do not hold places. Return when registration opens and
        confirm your booking.
      </p>
      {error && (
        <div role="alert">
          {error}
          <button onClick={() => setRevision((n) => n + 1)}>Retry</button>
        </div>
      )}
      {!data && !error && <p role="status">Loading pre-registrations…</p>}
      {data?.items.length === 0 && (
        <p className="card">
          No pre-registrations on this page.{" "}
          <Link to="/events">Discover events →</Link>
        </p>
      )}
      {data?.items.map((item) => {
        const waiting = now < Date.parse(item.opensAt);
        const closed =
          now >= Date.parse(item.closesAt) ||
          now >= Date.parse(item.startsAt) ||
          item.status === "CLOSED";
        return (
          <article className="card" key={item.eventId}>
            <span className="status-chip">
              {closed ? "Closed" : waiting ? "Opening soon" : "Ready to review"}
            </span>
            <h2>{item.eventTitle}</h2>
            <p>
              {item.eventLocation} · {formatDateTime(item.startsAt)}
            </p>
            <p>
              {item.ticketName} · {item.quantity}{" "}
              {item.quantity === 1 ? "place" : "places"}
            </p>
            {waiting && !closed && (
              <Countdown target={item.opensAt} label="Registration opens in" />
            )}
            <div className="actions">
              {!closed && (
                <Link
                  className="primary-button"
                  to={`/events/${item.eventId}?preRegistration=${item.ticketTypeId}#ticket-${item.ticketTypeId}`}
                >
                  {waiting ? "Edit pre-registration" : "Review and book"}
                </Link>
              )}
              <button
                disabled={busy}
                className="secondary-button"
                onClick={() => remove(item.eventId)}
              >
                Remove
              </button>
            </div>
          </article>
        );
      })}
      <div className="actions">
        <button disabled={page === 0} onClick={() => setPage((n) => n - 1)}>
          Previous
        </button>
        <span>Page {page + 1}</span>
        <button
          disabled={!data || page + 1 >= data.totalPages}
          onClick={() => setPage((n) => n + 1)}
        >
          Next
        </button>
      </div>
    </main>
  );
}
