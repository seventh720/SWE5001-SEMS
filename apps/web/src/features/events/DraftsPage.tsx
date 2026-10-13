import { DateTimeField } from "../../shared/components/DateTimeField";
import { Select } from "../../shared/components/Select";
import {
  singaporeInput,
  toInstant,
  formatDateTime,
} from "../../shared/components/dateTime";
import { categories, themes, EventArtwork } from "./EventArtwork";
import {
  noRequirements,
  registrationFields,
  type Requirements,
} from "../bookings/registration";
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
  category?: string;
  cardTheme?: string;
  registrationRequirements?: Requirements;
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
  category: "GENERAL",
  cardTheme: "LILAC",
  registrationRequirements: noRequirements,
};
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
        category: d.category ?? "GENERAL",
        cardTheme: d.cardTheme ?? "LILAC",
        registrationRequirements: d.registrationRequirements ?? noRequirements,
        startsAt: singaporeInput(d.startsAt),
        endsAt: singaporeInput(d.endsAt),
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
            startsAt: toInstant(form.startsAt),
            endsAt: toInstant(form.endsAt),
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
              All event times use Singapore time (UTC+08:00).
            </p>
            <div className="form-grid">
              <DateTimeField
                label="Starts at"
                value={form.startsAt}
                disabled={busy || editing?.salesConfigured}
                onChange={(value) => setForm({ ...form, startsAt: value })}
              />
              <DateTimeField
                label="Ends at"
                value={form.endsAt}
                after={form.startsAt}
                disabled={busy || editing?.salesConfigured}
                onChange={(value) => setForm({ ...form, endsAt: value })}
              />
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
            <div className="presentation-editor">
              <div>
                <Select
                  label="Event category"
                  value={form.category}
                  options={categories.map(([value, label]) => ({
                    value,
                    label,
                  }))}
                  disabled={busy}
                  onChange={(value) => setForm({ ...form, category: value })}
                />
                <Select
                  label="Card background"
                  value={form.cardTheme}
                  options={themes.map(([value, label]) => ({ value, label }))}
                  disabled={busy}
                  onChange={(value) => setForm({ ...form, cardTheme: value })}
                />
              </div>
              <EventArtwork category={form.category} theme={form.cardTheme} />
            </div>
            <fieldset className="registration-settings" disabled={busy}>
              <legend>Registration information</legend>
              <p>
                Choose what the booking contact must provide. One contact covers
                all places in an order. Only request information your event
                needs.
              </p>
              <div className="registration-options">
                {registrationFields.map((f) => (
                  <label className="role-option" key={f.rule}>
                    <input
                      type="checkbox"
                      checked={form.registrationRequirements[f.rule]}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          registrationRequirements: {
                            ...form.registrationRequirements,
                            [f.rule]: e.target.checked,
                          },
                        })
                      }
                    />
                    {f.label}
                  </label>
                ))}
              </div>
              <label>
                Custom question (optional)
                <input
                  maxLength={100}
                  value={form.registrationRequirements.customFieldLabel ?? ""}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      registrationRequirements: {
                        ...form.registrationRequirements,
                        customFieldLabel: e.target.value || null,
                      },
                    })
                  }
                />
              </label>
              <p className="muted">
                A custom question becomes required when you add it. Registration
                settings are fixed after publication.
              </p>
            </fieldset>
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
                <EventArtwork category={d.category} theme={d.cardTheme} />
                <div>
                  <span className="badge">{d.status}</span>
                  <h2>{d.title}</h2>
                  <p>
                    {d.location} · {formatDateTime(d.startsAt)}
                  </p>
                  <p className="muted">Capacity {d.capacity}</p>
                </div>
                <div className="actions">
                  {d.status === "DRAFT" && (
                    <button onClick={() => edit(d.id)}>Edit draft</button>
                  )}
                  <Link to={`/organizer/events/${d.id}/bookings`}>
                    Registration list →
                  </Link>
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
