import { EventArtwork } from "../events/EventArtwork";
import { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { apiRequest } from "../../shared/api/client";
import { formatDateTime } from "../../shared/components/dateTime";
import { Countdown, useNow } from "../../shared/components/Countdown";
import type { Booking } from "../bookings/BookingsPage";
import type { PreRegistration } from "../bookings/PreRegistrationsPage";
interface State<T> {
  items: T[];
  error: string;
  loading: boolean;
}
function useItems<T>(path: string, token: string | null) {
  const [retry, setRetry] = useState(0);
  const [state, setState] = useState<State<T>>({
    items: [],
    error: "",
    loading: true,
  });
  useEffect(() => {
    let active = true;
    setState({ items: [], error: "", loading: true });
    apiRequest<{ items: T[] }>(path, {}, token!)
      .then((d) => {
        if (active) setState({ items: d.items, error: "", loading: false });
      })
      .catch((e) => {
        if (active) setState({ items: [], error: e.message, loading: false });
      });
    return () => {
      active = false;
    };
  }, [path, token, retry]);
  return { ...state, retry: () => setRetry((n) => n + 1) };
}
function Feedback({
  state,
}: {
  state: State<unknown> & { retry: () => void };
}) {
  return state.loading ? (
    <p role="status">Loading…</p>
  ) : state.error ? (
    <div role="alert">
      {state.error} <button onClick={state.retry}>Retry</button>
    </div>
  ) : null;
}
function OrganizerPanel() {
 return <section className="card dashboard-panel"><h2>Organizer workspace</h2><p>Select an organization to manage its events, or view events available to its members.</p><Link className="secondary-button" to="/organizations">My organizations →</Link></section>;
}
export function DashboardPage() {
  const { user, token } = useAuth();
  const now = useNow();
  const bookings = useItems<Booking>("/api/v1/bookings/upcoming", token);
  const pre = useItems<PreRegistration>(
    "/api/v1/pre-registrations?page=0&size=4",
    token,
  );
  const discover = useItems<{
    id: string;
    title: string;
    location: string;
    startsAt: string;
    category: string;
    cardTheme: string;
  }>("/api/v1/events?page=0&size=3", token);
  const checkedOpenings = useRef(new Set<string>());
  useEffect(() => {
    const due=pre.items.filter(p=>p.status==="WAITING" && now>=Date.parse(p.opensAt) && now<Date.parse(p.closesAt) && !checkedOpenings.current.has(`${p.eventId}:${p.opensAt}`));
    if(due.length){due.forEach(p=>checkedOpenings.current.add(`${p.eventId}:${p.opensAt}`));pre.retry();}
  }, [now, pre.items]);
  if (!user) return null;
  const organizer = true;
  return (
    <main className="app-shell dashboard-shell" id="main-content">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">YOUR DASHBOARD</p>
          <h1>Hello, {user.username}.</h1>
          <p>Your plans, tickets and next steps in one place.</p>
          <div className="actions">
            {user.roles.map((r) => (
              <span className="status-chip" key={r}>
                {r}
              </span>
            ))}
          </div>
        </div>
        <Link className="primary-button" to="/events">
          Discover events ↗
        </Link>
      </header>
      <div className="dashboard-grid">
        <section className="card dashboard-panel">
          <div className="section-heading">
            <h2>Your upcoming plans</h2>
            <Link to="/bookings">All tickets →</Link>
          </div>
          <Feedback state={bookings} />
          {bookings.items.map((b) => (
            <Link className="dashboard-row" to={`/bookings/${b.id}`} key={b.id}>
              <span>
                <strong>{b.currentEvent?.title ?? b.eventTitle}</strong>{b.currentEvent === null && <p>Current event details unavailable. Showing saved booking information.</p>}
                <small>
                  {formatDateTime(b.currentEvent?.startsAt ?? b.startsAt)} · {b.currentEvent?.location ?? b.eventLocation}
                </small>
              </span>
              <span>
                {b.quantity} {b.quantity === 1 ? "ticket" : "tickets"} ↗
              </span>
            </Link>
          ))}
          {!bookings.loading && !bookings.error && !bookings.items.length && (
            <p>
              No upcoming bookings yet. <Link to="/events">Find an event</Link>{" "}
              to start your plans.
            </p>
          )}
        </section>
        <section className="card dashboard-panel">
          <div className="section-heading">
            <h2>Pre-registrations</h2>
            <Link to="/pre-registrations">View all →</Link>
          </div>
          <Feedback state={pre} />
          {pre.items.map((p) => {
            const waiting = now < Date.parse(p.opensAt),
              closed = now >= Date.parse(p.closesAt) || now >= Date.parse(p.startsAt) || p.status === "CLOSED",
              soldOut = p.status === "SOLD_OUT";
            return (
              <article className="dashboard-reservation" key={p.eventId}>
                <strong>{p.currentEvent?.title ?? p.eventTitle}</strong>{p.currentEvent === null && <p>Current event details unavailable. Showing saved pre-registration information.</p>}
                {waiting && !closed ? (
                  <Countdown label="Opens in" target={p.opensAt} />
                ) : (
                  <p>
                    {closed
                      ? "Registration closed"
                      : soldOut ? "Currently sold out" : "Registration is open — confirm your place"}
                  </p>
                )}
                <Link
                  className={!closed && !waiting && !soldOut ? "primary-button" : "secondary-button"}
                  to={
                    closed
                      ? "/pre-registrations"
                      : `/events/${p.eventId}?preRegistration=${p.ticketTypeId}#ticket-${p.ticketTypeId}`
                  }
                >
                  {closed
                    ? "Manage saved selection"
                    : waiting
                      ? "Review pre-registration →"
                      : soldOut ? "Check availability →" : "Register now →"}
                </Link>
              </article>
            );
          })}
          {!pre.loading && !pre.error && !pre.items.length && (
            <p>
              No saved pre-registrations. Save your details on an event before
              registration opens.
            </p>
          )}
        </section>
        {organizer && <OrganizerPanel />}
        {user.roles.includes("ADMIN") && (
          <section className="card dashboard-panel">
            <p className="eyebrow">PLATFORM ADMINISTRATION</p>
            <h2>Users & access</h2>
            <p>Open organizations, appoint organization administrators and manage platform accounts.</p>
            <Link className="secondary-button" to="/admin/organizations">
              Manage organizations
            </Link>
          </section>
        )}
        {true && (
          <section className="card dashboard-panel">
            <p className="eyebrow">STAFF WORKSPACE</p>
            <h2>Event operations</h2><Link to="/staff">My check-in tasks →</Link>
            <p>
              Check tickets only for events assigned to you by an organization manager.
            </p>
          </section>
        )}
      </div>
      <section className="dashboard-discover">
        <div className="section-heading">
          <h2>Coming up in the community</h2>
          <Link to="/events">Browse all →</Link>
        </div>
        <Feedback state={discover} />
        <div className="dashboard-discover-grid">
          {discover.items.map((event) => (
            <article className="card" key={event.id}>
              <EventArtwork category={event.category} theme={event.cardTheme} />
              <h3>
                <Link to={`/events/${event.id}`}>{event.title}</Link>
              </h3>
              <p>{formatDateTime(event.startsAt)}</p>
              <p className="muted">{event.location}</p>
            </article>
          ))}
        </div>
        {!discover.loading && !discover.error && !discover.items.length && (
          <p>No upcoming public events yet.</p>
        )}
      </section>
      <div className="dashboard-shortcuts">
        <Link to="/profile">Manage saved details →</Link>
        <Link to="/events">Browse upcoming events →</Link>
      </div>
    </main>
  );
}
