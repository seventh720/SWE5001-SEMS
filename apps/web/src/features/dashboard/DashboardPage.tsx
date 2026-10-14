import { EventArtwork } from "../events/EventArtwork";
import { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { apiRequest } from "../../shared/api/client";
import { formatDateTime } from "../../shared/components/dateTime";
import { Countdown, useNow } from "../../shared/components/Countdown";
import type { Booking } from "../bookings/BookingsPage";
import type { PreRegistration } from "../bookings/PreRegistrationsPage";
interface OwnEvent {
  id: string;
  title: string;
  status: string;
  startsAt: string;
}
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
  const { token } = useAuth();
  const data = useItems<OwnEvent>(
    "/api/v1/organizer/events?page=0&size=4",
    token,
  );
  return (
    <section className="card dashboard-panel">
      <div className="section-heading">
        <h2>Organizer workspace</h2>
        <Link to="/organizer/events">Manage all →</Link>
      </div>
      <Feedback state={data} />
      {data.items.map((e) => (
        <Link
          className="dashboard-row"
          key={e.id}
          to={`/organizer/events/${e.id}/setup`}
        >
          <span>
            <strong>{e.title}</strong>
            <small>{formatDateTime(e.startsAt)}</small>
          </span>
          <span className="status-chip">{e.status}</span>
        </Link>
      ))}
      {!data.loading && !data.error && !data.items.length && (
        <p>
          Create your first event, or reuse one of your events as a template.
        </p>
      )}
      <Link className="secondary-button" to="/organizer/events">
        Create or reuse an event
      </Link>
    </section>
  );
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
  const organizer = user.roles.some((r) => r === "ORGANIZER" || r === "ADMIN");
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
                <strong>{b.eventTitle}</strong>
                <small>
                  {formatDateTime(b.startsAt)} · {b.eventLocation}
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
                <strong>{p.eventTitle}</strong>
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
            <p>Manage platform accounts and assign organizer or staff roles.</p>
            <Link className="secondary-button" to="/admin/users">
              Manage users
            </Link>
          </section>
        )}
        {user.roles.includes("STAFF") && (
          <section className="card dashboard-panel">
            <p className="eyebrow">STAFF WORKSPACE</p>
            <h2>Event operations</h2>
            <p>
              Staff assignment and check-in are not available yet. Your assigned
              event workspace will appear here when that workflow is released.
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
