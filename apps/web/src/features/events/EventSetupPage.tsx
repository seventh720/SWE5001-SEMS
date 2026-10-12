import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { apiRequest } from "../../shared/api/client";
interface Event {
  id: string;
  title: string;
  startsAt: string;
  endsAt: string;
  capacity: number;
  version: number;
  status: string;
  salesConfigured: boolean;
  publicationError: string | null;
}
interface Ticket {
  name: string;
  quota: number;
  opensAt: string;
  closesAt: string;
}
interface Inventory {
  version: number;
  state: string;
  ticketTypes: Ticket[];
}
function local(value: string) {
  const d = new Date(value);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}
export function EventSetupPage() {
  const { id } = useParams();
  const { token } = useAuth();
  const [event, setEvent] = useState<Event | null>(null);
  const [inventory, setInventory] = useState<Inventory | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [dirty, setDirty] = useState(false);
  async function load() {
    const [e, i] = await Promise.all([
      apiRequest<Event>(`/api/v1/organizer/events/${id}`, {}, token!),
      apiRequest<Inventory>(
        `/api/v1/organizer/events/${id}/ticket-types`,
        {},
        token!,
      ),
    ]);
    setEvent(e);
    setInventory(i);
    setTickets(
      i.ticketTypes.length
        ? i.ticketTypes.map((t) => ({
            ...t,
            opensAt: local(t.opensAt),
            closesAt: local(t.closesAt),
          }))
        : [
            {
              name: "General admission",
              quota: e.capacity,
              opensAt: local(new Date().toISOString()),
              closesAt: local(e.startsAt),
            },
          ],
    );
    setDirty(false);
  }
  useEffect(() => {
    if (token) load().catch((e) => setError(e.message));
  }, [id, token]);
  useEffect(() => {
    if (event?.status !== "PUBLISHING") return;
    const timer = setInterval(() => {
      load().catch((e) => setError(e.message));
    }, 3000);
    return () => clearInterval(timer);
  }, [event?.status, id, token]);
  function change(index: number, key: keyof Ticket, value: string | number) {
    setTickets((rows) =>
      rows.map((t, n) => (n === index ? { ...t, [key]: value } : t)),
    );
    setDirty(true);
    setConfirm(false);
  }
  async function save(e: FormEvent) {
    e.preventDefault();
    if (!event || !inventory) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await apiRequest(
        `/api/v1/organizer/events/${id}/ticket-types`,
        {
          method: "PUT",
          body: JSON.stringify({
            eventVersion: event.version,
            version: inventory.version,
            ticketTypes: tickets.map((t) => ({
              ...t,
              opensAt: new Date(t.opensAt).toISOString(),
              closesAt: new Date(t.closesAt).toISOString(),
            })),
          }),
        },
        token!,
      );
      await load();
      setMessage("Ticket configuration saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to save tickets");
    } finally {
      setBusy(false);
    }
  }
  async function publish() {
    if (!event || !inventory) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await apiRequest<Event>(
        `/api/v1/organizer/events/${id}/publish`,
        {
          method: "POST",
          body: JSON.stringify({
            version: event.version,
            ticketVersion: inventory.version,
          }),
        },
        token!,
      );
      setEvent(result);
      setConfirm(false);
      setMessage(
        result.status === "PUBLISHED"
          ? "Event published."
          : "Publication is pending. This page will update automatically.",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to publish");
    } finally {
      setBusy(false);
    }
  }
  const editable = event?.status === "DRAFT";
  const total = tickets.reduce((n, t) => n + t.quota, 0);
  return (
    <main className="app-shell">
      <Link to="/organizer/events">← My events</Link>
      <h1>{event?.title ?? "Event setup"}</h1>
      {error && (
        <p role="alert" className="error-message">
          {error}
          <button
            onClick={() => {
              setError("");
              load().catch((e) => setError(e.message));
            }}
          >
            Reload saved configuration
          </button>
        </p>
      )}
      {message && <p role="status">{message}</p>}
      {event && inventory && (
        <>
          <p>
            <span className="badge">{event.status}</span> · Event capacity:{" "}
            {event.capacity}
          </p>
          {event.publicationError && (
            <p role="alert">{event.publicationError}</p>
          )}
          {event.status === "PUBLISHING" && (
            <p role="status">
              Publishing is in progress. The event stays private until ticket
              setup is confirmed.
            </p>
          )}
          {event.status === "PUBLISHED" && (
            <Link className="primary-button" to={`/events/${id}`}>
              View public event
            </Link>
          )}
          <section className="card">
            <h2>Free ticket types</h2>
            <p>
              Starting ticket setup fixes the event time and capacity. Ticket
              types remain editable until publication.
            </p>
            <p className="muted">
              Times use {Intl.DateTimeFormat().resolvedOptions().timeZone}.
              Sales must close by the event start.
            </p>
            <form onSubmit={save}>
              <fieldset disabled={!editable || busy} className="ticket-fields">
                {tickets.map((t, n) => (
                  <div className="ticket-row" key={n}>
                    <div className="form-grid">
                      <label>
                        Ticket name {n + 1}
                        <input
                          required
                          maxLength={100}
                          value={t.name}
                          onChange={(e) => change(n, "name", e.target.value)}
                        />
                      </label>
                      <label>
                        Quota {n + 1}
                        <input
                          type="number"
                          required
                          min={1}
                          max={event.capacity}
                          value={t.quota}
                          onChange={(e) =>
                            change(n, "quota", Number(e.target.value))
                          }
                        />
                      </label>
                      <label>
                        Sales open {n + 1}
                        <input
                          type="datetime-local"
                          required
                          value={t.opensAt}
                          onChange={(e) => change(n, "opensAt", e.target.value)}
                        />
                      </label>
                      <label>
                        Sales close {n + 1}
                        <input
                          type="datetime-local"
                          required
                          value={t.closesAt}
                          onChange={(e) =>
                            change(n, "closesAt", e.target.value)
                          }
                        />
                      </label>
                    </div>
                    {tickets.length > 1 && (
                      <button
                        type="button"
                        onClick={() => {
                          setTickets((rows) => rows.filter((_, i) => i !== n));
                          setDirty(true);
                        }}
                      >
                        Remove ticket type {n + 1}
                      </button>
                    )}
                  </div>
                ))}
                <p>
                  Total allocation: {total} / {event.capacity}
                </p>
                {total > event.capacity && (
                  <p role="alert">
                    Reduce the total quota to fit the event capacity.
                  </p>
                )}
                <div className="actions">
                  <button
                    type="button"
                    disabled={tickets.length >= 20}
                    onClick={() => {
                      setTickets((rows) => [
                        ...rows,
                        {
                          name: "",
                          quota: 1,
                          opensAt: local(new Date().toISOString()),
                          closesAt: local(event.startsAt),
                        },
                      ]);
                      setDirty(true);
                    }}
                  >
                    Add ticket type
                  </button>
                  <button
                    type="submit"
                    className="primary-button"
                    disabled={total > event.capacity}
                  >
                    Save ticket types
                  </button>
                </div>
              </fieldset>
            </form>
          </section>
          {editable && (
            <section className="card">
              <h2>Ready to publish?</h2>
              <p>
                Publication makes this event visible to everyone and fixes its
                ticket configuration.
              </p>
              {dirty && <p>Save ticket changes before publishing.</p>}
              <button
                className="primary-button"
                disabled={busy || dirty || inventory.version === 0}
                onClick={() => setConfirm(true)}
              >
                Publish event
              </button>
              {confirm && (
                <div role="group" aria-label="Confirm publication">
                  <p>Publish this event with the saved ticket types?</p>
                  <button onClick={publish} disabled={busy}>
                    Confirm publication
                  </button>
                  <button onClick={() => setConfirm(false)} disabled={busy}>
                    Keep draft
                  </button>
                </div>
              )}
            </section>
          )}
        </>
      )}
    </main>
  );
}
