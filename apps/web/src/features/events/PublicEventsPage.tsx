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
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    apiRequest<Page>(
      `/api/v1/events?page=${page}&size=10&keyword=${encodeURIComponent(keyword)}`,
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
  }, [page, keyword]);
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
        data.items.map((e) => (
          <article key={e.id} className="card">
            <h2>
              <Link to={`/events/${e.id}`}>{e.title}</Link>
            </h2>
            <p>
              {e.location} · {new Date(e.startsAt).toLocaleString()}
            </p>
            <p>{e.description}</p>
            <Link to={`/events/${e.id}`}>View event →</Link>
          </article>
        ))
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
          <h1>{event.title}</h1>
          <p>{event.location}</p>
          <p>
            {new Date(event.startsAt).toLocaleString()} –{" "}
            {new Date(event.endsAt).toLocaleString()}
          </p>
          <section className="card">
            <p>{event.description}</p>
          </section>
          <h2>Admission options</h2>
          {tickets.map((t) => (
            <article key={t.id} className="card">
              <h3>{t.name} · Free</h3>
              <p>{t.available} places available</p>
              <p>
                Sales: {new Date(t.opensAt).toLocaleString()} –{" "}
                {new Date(t.closesAt).toLocaleString()}
              </p>
              <BookingForm
                eventId={event.id}
                ticketTypeId={t.id}
                available={t.available}
                opensAt={t.opensAt}
                closesAt={t.closesAt}
              />
            </article>
          ))}
        </>
      )}
    </main>
  );
}
