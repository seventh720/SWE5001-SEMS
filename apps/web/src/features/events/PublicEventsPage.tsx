import {useAuth} from "../auth/AuthContext";
import { HomeLink } from "../../shared/components/HomeLink";
import { Countdown, useNow } from "../../shared/components/Countdown";
import { Select } from "../../shared/components/Select";
import { formatDateTime } from "../../shared/components/dateTime";
import { categories, EventArtwork } from "./EventArtwork";
import type { Requirements } from "../bookings/registration";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams, useLocation, useSearchParams } from "react-router-dom";
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
  organizationId?: string;
  visibility?: string;
  organizationName?: string;
}
interface Page {
  items: Event[];
  totalPages: number;
}
export function PublicEventsPage() {
  const {token}=useAuth();const [params]=useSearchParams();const organizationId=params.get("organizationId");
  const [data, setData] = useState<Page>({ items: [], totalPages: 0 });
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [keyword, setKeyword] = useState("");
  const [category, setCategory] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setData({items:[],totalPages:0});
    setLoading(true);
    setError("");
    apiRequest<Page>(
      `/api/v1/events?page=${page}&size=10&keyword=${encodeURIComponent(keyword)}${category ? `&category=${category}` : ""}${organizationId ? `&organizationId=${organizationId}` : ""}`,{},token??undefined,
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
  }, [page, keyword, category,organizationId,token]);
  function submit(e: FormEvent) {
    e.preventDefault();
    setPage(0);
    setKeyword(search);
  }
  return (
    <main className="app-shell discovery-workspace">
      <HomeLink />
      <p className="eyebrow">DISCOVER YOUR COMMUNITY</p>
      <h1>Upcoming events</h1>
      <div className="discovery-filters">
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
      </div>
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
              <p className="muted">{e.organizationName} · {e.visibility === "ORGANIZATION_ONLY" ? "Members only" : "Public event"}</p>
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
                <Link to={`/events/${e.id}`}>Details &amp; registration ↗</Link>
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
  const {token}=useAuth();
  const now = useNow();
  const { id } = useParams();
  const location = useLocation();
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
    let active=true;setEvent(null);setTickets([]);setError("");
    Promise.all([
      apiRequest<Event>(`/api/v1/events/${id}`,{},token??undefined),
      apiRequest<{ ticketTypes: typeof tickets }>(
        `/api/v1/events/${id}/ticket-types`,{},token??undefined,
      ),
    ])
      .then(([e, i]) => {
        if(!active)return;
        setEvent(e);
        setTickets(i.ticketTypes);
      })
      .catch((e) => {if(active)setError(e.message)});
    return()=>{active=false};
  }, [id,token]);
  useEffect(() => {
    const selected = new URLSearchParams(location.search).get("preRegistration");
    if (!event || !selected || !tickets.some(t => t.id === selected)) return;
    const timer = window.setTimeout(() => {
      const target = document.getElementById(`ticket-${selected}`);
      target?.scrollIntoView({block:"start", behavior:"auto"});
      target?.focus({preventScroll:true});
    }, 0);
    return () => window.clearTimeout(timer);
  }, [event, tickets, location.search]);
  return (
    <main className="app-shell event-detail-page">
      <div className="page-breadcrumbs">
        <HomeLink />
        <Link to="/events">All events →</Link>
      </div>
      {error && <p role="alert">{error}</p>}
      {event && (
        <>
          <div className="event-detail-grid">
          <section className="card event-overview">
          <EventArtwork category={event.category} theme={event.cardTheme} />
          <header className="event-detail-hero">
            <div>
              <p className="eyebrow">
                {categories.find((c) => c[0] === event.category)?.[1] ??
                  "Community event"}{" "}
                / FREE ADMISSION
              </p>
              <h1>{event.title}</h1><p>{event.organizationName} · {event.visibility === "ORGANIZATION_ONLY" ? "Members only" : "Public"}</p>
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
          </header>
            <section className="event-description">
              <h2>About this event</h2>
              <p>{event.description}</p>

            </section>
          </section>
            <section aria-label="Admission options" className="admission-panel">
              <h2>Admission options</h2>
              {tickets.map((t) => (
                <article key={t.id} id={`ticket-${t.id}`} tabIndex={-1} className="card admission-card">
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
