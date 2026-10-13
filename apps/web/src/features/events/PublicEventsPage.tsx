import { Countdown, useNow } from "../../shared/components/Countdown";
import { Select } from "../../shared/components/Select";
import { formatDateTime } from "../../shared/components/dateTime";
import { categories, EventArtwork } from "./EventArtwork";
import type { Requirements } from "../bookings/registration";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { apiRequest } from "../../shared/api/client";
import { BookingForm } from "../bookings/BookingForm";
interface Event {
  id: string;
  title: string;
  description: string;
  location: string;
  startsAt: string;
  endsAt: string;
  capacity: number;
  category?: string;
  cardTheme?: string;
  registrationRequirements?: Requirements;
}
interface Page {
  items: Event[];
  totalPages: number;
}
export function PublicEventsPage() {
  const [data, setData] = useState<Page>({ items: [], totalPages: 0 });
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [keyword, setKeyword] = useState("");
  const [category, setCategory] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    apiRequest<Page>(
      `/api/v1/events?page=${page}&size=10&keyword=${encodeURIComponent(keyword)}${category ? `&category=${category}` : ""}`,
    )
      .then((d) => {
        if (active) setData(d);
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
  }, [page, keyword, category]);
  function submit(e: FormEvent) {
    e.preventDefault();
    setPage(0);
    setKeyword(search);
  }
  return (
    <main className="app-shell">
      <p className="eyebrow">DISCOVER YOUR COMMUNITY</p>
      <h1>Upcoming events</h1>
      <form className="actions" onSubmit={submit}>
        <label>
          Search events
          <input
            value={search}
            maxLength={200}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <button type="submit">Search</button>
      </form>
      <Select
        label="Filter by category"
        value={category}
        options={[
          { value: "", label: "All categories" },
          ...categories.map(([value, label]) => ({ value, label })),
        ]}
        onChange={(value) => {
          setCategory(value);
          setPage(0);
        }}
      />
      {error && (
        <p role="alert" className="error-message">
          {error}
        </p>
      )}
      {loading ? (
        <p role="status">Loading events…</p>
      ) : data.items.length === 0 ? (
        <p>No upcoming events found.</p>
      ) : (
        <section className="offering-grid">
          {data.items.map((e) => (
            <article key={e.id} className="card offering-card">
              <EventArtwork category={e.category} theme={e.cardTheme} />
              <h2>
                <Link to={`/events/${e.id}`}>{e.title}</Link>
              </h2>
              <dl className="event-facts">
                <div>
                  <dt>When</dt>
                  <dd>{formatDateTime(e.startsAt)}</dd>
                </div>
                <div>
                  <dt>Where</dt>
                  <dd>{e.location}</dd>
                </div>
              </dl>
              <p className="event-excerpt">{e.description}</p>
              <div className="event-card-footer">
                <span className="status-chip">Free admission</span>
                <Link to={`/events/${e.id}`}>Details & registration ↗</Link>
              </div>
            </article>
          ))}
        </section>
      )}
      <div className="actions">
        <button disabled={page === 0} onClick={() => setPage((n) => n - 1)}>
          Previous
        </button>
        <span>Page {page + 1}</span>
        <button
          disabled={page + 1 >= data.totalPages}
          onClick={() => setPage((n) => n + 1)}
        >
          Next
        </button>
      </div>
    </main>
  );
}
export function PublicEventDetail() {
  const now = useNow();
  const { id } = useParams();
  const [event, setEvent] = useState<Event | null>(null);
  const [tickets, setTickets] = useState<
    {
      id: string;
      name: string;
      available: number;
      opensAt: string;
      closesAt: string;
    }[]
  >([]);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([
      apiRequest<Event>(`/api/v1/events/${id}`),
      apiRequest<{ ticketTypes: typeof tickets }>(
        `/api/v1/events/${id}/ticket-types`,
      ),
    ])
      .then(([e, i]) => {
        setEvent(e);
        setTickets(i.ticketTypes);
      })
      .catch((e) => setError(e.message));
  }, [id]);
  return (
    <main className="app-shell">
      <Link to="/events">← All events</Link>
      {error && <p role="alert">{error}</p>}
      {event && (
        <>
          <header className="event-detail-hero">
            <div>
              <p className="eyebrow">
                {categories.find((c) => c[0] === event.category)?.[1] ??
                  "Community event"}{" "}
                / FREE ADMISSION
              </p>
              <h1>{event.title}</h1>
              <dl className="event-facts">
                <div>
                  <dt>When · Singapore time</dt>
                  <dd>
                    {formatDateTime(event.startsAt)}
                    <br />
                    to {formatDateTime(event.endsAt)}
                  </dd>
                </div>
                <div>
                  <dt>Where</dt>
                  <dd>{event.location}</dd>
                </div>
              </dl>
              {now < Date.parse(event.startsAt) ? (
                <Countdown target={event.startsAt} label="Event starts in" />
              ) : (
                <span className="status-chip">
                  {now < Date.parse(event.endsAt)
                    ? "Event in progress"
                    : "Event ended"}
                </span>
              )}
            </div>
            <EventArtwork category={event.category} theme={event.cardTheme} />
          </header>
          <div className="event-detail-grid">
            <section className="card event-description">
              <p className="eyebrow">THE EXPERIENCE</p>
              <h2>About this event</h2>
              <p>{event.description}</p>
              <h3>How registration works</h3>
              <p>
                Choose a ticket option and complete the requested contact
                details. Before opening, save a pre-registration; once open,
                confirm to receive your tickets.
              </p>
            </section>
            <section aria-label="Admission options" className="admission-panel">
              <h2>Admission options</h2>
              {tickets.map((t) => (
                <article key={t.id} className="card admission-card">
                  <div className="event-card-footer">
                    <h3>{t.name}</h3>
                    <strong className="ticket-price">Free</strong>
                  </div>
                  <span className="status-chip">
                    {now < Date.parse(t.opensAt)
                      ? "Opening soon"
                      : now >= Date.parse(t.closesAt)
                        ? "Registration closed"
                        : t.available === 0
                          ? "Sold out"
                          : "Registration open"}
                  </span>
                  <p>
                    <strong>{t.available}</strong>{" "}
                    {t.available === 1 ? "place" : "places"} available
                  </p>
                  <dl className="sales-facts">
                    <div>
                      <dt>Opens</dt>
                      <dd>{formatDateTime(t.opensAt)}</dd>
                    </div>
                    <div>
                      <dt>Closes</dt>
                      <dd>{formatDateTime(t.closesAt)}</dd>
                    </div>
                  </dl>
                  <BookingForm
                    requirements={event.registrationRequirements}
                    eventId={event.id}
                    ticketTypeId={t.id}
                    available={t.available}
                    opensAt={t.opensAt}
                    closesAt={t.closesAt}
                  />
                </article>
              ))}
            </section>
          </div>
        </>
      )}
    </main>
  );
}
