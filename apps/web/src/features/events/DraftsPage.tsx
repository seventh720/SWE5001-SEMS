import { type FormEvent, useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { apiRequest, ApiError } from "../../shared/api/client";
interface Draft {
  id: string;
  title: string;
  description: string;
  location: string;
  startsAt: string;
  endsAt: string;
  capacity: number;
  version: number;
  status: string;
  salesConfigured?: boolean;
}
interface Page {
  items: Draft[];
  totalPages: number;
  totalElements: number;
}
const empty = {
  title: "",
  description: "",
  location: "",
  startsAt: "",
  endsAt: "",
  capacity: 1,
};
function localDate(value: string) {
  const d = new Date(value);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}
export function DraftsPage() {
  const { user, token } = useAuth();
  const allowed = user?.roles.some((r) => r === "ORGANIZER" || r === "ADMIN");
  const [data, setData] = useState<Page>({
    items: [],
    totalPages: 0,
    totalElements: 0,
  });
  const [page, setPage] = useState(0);
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState<Draft | null>(null);
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    if (!allowed || !token) return;
    let active = true;
    setLoading(true);
    apiRequest<Page>(`/api/v1/organizer/events?page=${page}&size=10`, {}, token)
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
  }, [token, allowed, page, refresh]);
  if (!allowed) return <Navigate to="/" replace />;
  async function edit(id: string) {
    setError("");
    try {
      const d = await apiRequest<Draft>(
        `/api/v1/organizer/events/${id}`,
        {},
        token!,
      );
      setEditing(d);
      setForm({
        ...d,
        startsAt: localDate(d.startsAt),
        endsAt: localDate(d.endsAt),
      });
      setShow(true);
      setMessage("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load draft");
    }
  }
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await apiRequest<Draft>(
        `/api/v1/organizer/events${editing ? `/${editing.id}` : ""}`,
        {
          method: editing ? "PUT" : "POST",
          body: JSON.stringify({
            ...form,
            startsAt: new Date(form.startsAt).toISOString(),
            endsAt: new Date(form.endsAt).toISOString(),
            ...(editing ? { version: editing.version } : {}),
          }),
        },
        token!,
      );
      setShow(false);
      setEditing(null);
      setMessage("Draft saved.");
      setRefresh((v) => v + 1);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to save draft");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">ORGANIZER WORKSPACE</p>
          <h1>My events</h1>
          <p className="muted">Your drafts are private to your account.</p>
        </div>
        <button
          className="primary-button"
          onClick={() => {
            setForm(empty);
            setEditing(null);
            setShow(true);
            setError("");
            setMessage("");
          }}
        >
          Create event
        </button>
      </header>
      {error && (
        <p role="alert" className="error-message">
          {error}
          {editing && (
            <button onClick={() => edit(editing.id)}>
              Reload latest draft
            </button>
          )}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      {show && (
        <section className="card">
          <h2>{editing ? "Edit draft" : "New event draft"}</h2>
          <form onSubmit={save}>
            <label>
              Title
              <input
                required
                maxLength={200}
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </label>
            <label>
              Description
              <textarea
                required
                maxLength={10000}
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
              />
            </label>
            <label>
              Location
              <input
                required
                maxLength={500}
                value={form.location}
                onChange={(e) => setForm({ ...form, location: e.target.value })}
              />
            </label>
            {editing?.salesConfigured && (
              <p>Event time and capacity are fixed after ticket setup.</p>
            )}
            <p className="muted">
              Times use your browser timezone:{" "}
              {Intl.DateTimeFormat().resolvedOptions().timeZone}.
            </p>
            <div className="form-grid">
              <label>
                Starts at
                <input
                  type="datetime-local"
                  required
                  value={form.startsAt}
                  onChange={(e) =>
                    setForm({ ...form, startsAt: e.target.value })
                  }
                />
              </label>
              <label>
                Ends at
                <input
                  type="datetime-local"
                  required
                  value={form.endsAt}
                  onChange={(e) => setForm({ ...form, endsAt: e.target.value })}
                />
              </label>
              <label>
                Capacity
                <input
                  disabled={editing?.salesConfigured}
                  type="number"
                  min={1}
                  max={2147483647}
                  required
                  value={form.capacity}
                  onChange={(e) =>
                    setForm({ ...form, capacity: Number(e.target.value) })
                  }
                />
              </label>
            </div>
            <div className="actions">
              <button type="submit" className="primary-button" disabled={busy}>
                {busy ? "Saving…" : "Save draft"}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => setShow(false)}
              >
                Close editor
              </button>
            </div>
          </form>
        </section>
      )}
      {loading ? (
        <p role="status">Loading drafts…</p>
      ) : (
        <section className="event-list">
          {data.items.length === 0 ? (
            <p>No event drafts yet. Create your first event.</p>
          ) : (
            data.items.map((d) => (
              <article className="card event-card" key={d.id}>
                <div>
                  <span className="badge">{d.status}</span>
                  <h2>{d.title}</h2>
                  <p>
                    {d.location} · {new Date(d.startsAt).toLocaleString()}
                  </p>
                  <p className="muted">Capacity {d.capacity}</p>
                </div>
                <div className="actions">
                  {d.status === "DRAFT" && (
                    <button onClick={() => edit(d.id)}>Edit draft</button>
                  )}
                  <Link to={`/organizer/events/${d.id}/setup`}>
                    Ticket setup & publication →
                  </Link>
                </div>
              </article>
            ))
          )}
        </section>
      )}
      <div className="actions">
        <button disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
          Previous
        </button>
        <span>
          Page {page + 1} · {data.totalElements} events
        </span>
        <button
          disabled={page + 1 >= data.totalPages}
          onClick={() => setPage((p) => p + 1)}
        >
          Next
        </button>
      </div>
    </main>
  );
}
