import type {Organization} from "../organizations/OrganizationsPage";
import { HomeLink } from "../../shared/components/HomeLink";
import { FeedbackNotice } from "../../shared/components/FeedbackNotice";
import { TicketEditor, initialTicket, type TicketInventory, type TicketRow } from "./TicketEditor";
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
import { Link, Navigate, useSearchParams } from "react-router-dom";
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
  publicationError?: string | null;
  salesConfigured?: boolean;
  category?: string;
  cardTheme?: string;
  registrationRequirements?: Requirements;
  organizationId?: string;
  visibility?: string;
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
  visibility: "PUBLIC",
  category: "GENERAL",
  cardTheme: "LILAC",
  registrationRequirements: noRequirements,
};
export function DraftsPage() {
  const { user, token } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const allowed = !!user;
  const [organizations,setOrganizations]=useState<Organization[]>([]);
  const [organizationId,setOrganizationId]=useState(searchParams.get("organizationId")??"");
  useEffect(()=>{let active=true;apiRequest<Organization[]>("/api/v1/me/organizations",{},token!).then(rows=>{if(active)setOrganizations(rows.filter(o=>o.role!=="MEMBER"))}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[token]);
  const [data, setData] = useState<Page>({
    items: [],
    totalPages: 0,
    totalElements: 0,
  });
  const [page, setPage] = useState(0);
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState<Draft | null>(null);
  const [show, setShow] = useState(searchParams.get("create")==="true");
  const [error, setError] = useState("");
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [tickets, setTickets] = useState<TicketRow[]>([initialTicket()]);
  const [inventory, setInventory] = useState<TicketInventory>({version:0,ticketTypes:[]});
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    if (!allowed || !token || !organizationId) {setLoading(false);return;}
    let active = true;
    setLoading(true);
    apiRequest<Page>(`/api/v1/organizer/events?organizationId=${organizationId}&page=${page}&size=10`, {}, token)
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
  }, [token, allowed, page, refresh,organizationId]);
  useEffect(() => {
    if (!data.items.some((e) => e.status === "UPDATING")) return;
    const timer = window.setInterval(() => setRefresh((v) => v + 1), 3000);
    return () => window.clearInterval(timer);
  }, [data.items]);
  useEffect(() => {
    const id = searchParams.get("edit");
    if (allowed && token && id) { void edit(id); setSearchParams(organizationId?{organizationId}:{}, {replace: true}); }
  }, [allowed, token, searchParams]);
  useEffect(() => {
    if (!pendingId || !token) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function check() {
      try {
        const completed = await apiRequest<Draft>(`/api/v1/organizer/events/${pendingId}`, {}, token!);
        if (!active) return;
        if (completed.status !== "UPDATING") {
          setPendingId(null);
          setMessage(completed.publicationError ? `Update rejected. ${completed.publicationError}` : "Event changes saved. Ticket settings are synchronized.");
          setRefresh(v => v + 1);
          return;
        }
      } catch {
        // Keep the pending notice and retry; a failed read is not a successful save.
      }
      if (active) timer = setTimeout(check, 3000);
    }
    void check();
    return () => { active = false; clearTimeout(timer); };
  }, [pendingId, token]);
  if (!allowed) return <Navigate to="/" replace />;
  async function edit(id: string, template = false, scroll = true) {
    setError("");
    try {
      const d = await apiRequest<Draft>(
        `/api/v1/organizer/events/${id}`,
        {},
        token!,
      );
      const i = template ? {version:0,ticketTypes:[]} : await apiRequest<TicketInventory>(`/api/v1/organizer/events/${id}/ticket-types`,{},token!);
      if(d.organizationId)setOrganizationId(d.organizationId);
      setInventory(i);
      setTickets(i.ticketTypes.length ? i.ticketTypes.map(t=>({...t,opensAt:singaporeInput(t.opensAt),closesAt:singaporeInput(t.closesAt)})) : [initialTicket(d.capacity,template ? "" : singaporeInput(d.startsAt))]);
      setEditing(template ? null : d);
      setForm({
        ...d,
        visibility: d.visibility ?? "PUBLIC",
        category: d.category ?? "GENERAL",
        cardTheme: d.cardTheme ?? "LILAC",
        registrationRequirements: d.registrationRequirements ?? noRequirements,
        title: template ? `${d.title.slice(0, 190)} (copy)` : d.title,
        startsAt: template ? "" : singaporeInput(d.startsAt),
        endsAt: template ? "" : singaporeInput(d.endsAt),
      });
      setShow(true);
      setMessage(
        template
          ? "Template loaded. Choose new dates, save the draft, then configure its ticket types."
          : "",
      );
      if (scroll) window.scrollTo({ top: 0, behavior: "smooth" });
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
      const details = {
        ...form,
        organizationId,
        startsAt: editing && form.startsAt === singaporeInput(editing.startsAt) ? editing.startsAt : toInstant(form.startsAt),
        endsAt: editing && form.endsAt === singaporeInput(editing.endsAt) ? editing.endsAt : toInstant(form.endsAt),
      };
      let target = editing;
      if (!target) {
        target = await apiRequest<Draft>("/api/v1/organizer/events",{method:"POST",body:JSON.stringify(details)},token!);
        // Keep the created ID if ticket validation fails so retry never creates another draft.
        setEditing(target);
      }
      const saved = await apiRequest<Draft>(`/api/v1/organizer/events/${target.id}/revision`,{
        method:"PUT",body:JSON.stringify({...details,version:target.version,ticketConfiguration:{version:inventory.version,ticketTypes:tickets.map(t=>{
          const old=inventory.ticketTypes.find(v=>v.id===t.id);
          return {...t,opensAt:old && t.opensAt===singaporeInput(old.opensAt)?old.opensAt:toInstant(t.opensAt),closesAt:old && t.closesAt===singaporeInput(old.closesAt)?old.closesAt:toInstant(t.closesAt)};
        })}})},token!);
      if(saved.status === "UPDATING") {setPendingId(saved.id);setShow(false);setEditing(saved);}
      else await edit(saved.id, false, false);
      setMessage(
        saved.status === "UPDATING"
          ? "Update is syncing with ticketing. The event is temporarily unavailable for new bookings; this list will refresh automatically."
          : (editing?.status === "PUBLISHED" || editing?.status === "PAUSED")
            ? "Published event updated. Confirmed tickets use the updated event schedule."
            : "Draft saved.",
      );
      setRefresh((v) => v + 1);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to save draft");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="app-shell organizer-workspace">
      <HomeLink />
      <header className="app-header">
        <div>
          <p className="eyebrow">ORGANIZER WORKSPACE</p>
          <h1>{show ? "Event editor" : "My events"}</h1>
          <p className="muted">{show ? "Review the details and tickets, then save all changes below." : "Manage events for the selected organization."}</p>
        </div>
        {!show && <button
          className="primary-button"
          disabled={!organizationId}
          onClick={() => {
            setTickets([initialTicket()]);
            setInventory({version:0,ticketTypes:[]});
            setForm(empty);
            setEditing(null);
            setShow(true);
            setError("");
            setMessage("");
          }}
        >
          Create event
        </button>}
      </header>
      <Select label="Organization" disabled={show||busy} value={organizationId} onChange={value=>{setOrganizationId(value);setSearchParams({organizationId:value});setData({items:[],totalPages:0,totalElements:0});setPage(0);setEditing(null);setMessage("");setError("")}} options={[{value:"",label:"Select an organization"},...organizations.map(o=>({value:o.id,label:o.name}))]} />
      <Link to="/organizations">Organization memberships →</Link>
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
      <FeedbackNotice message={message} tone={message.startsWith("Update rejected") ? "error" : message.includes("syncing") || message.startsWith("Template") ? "info" : "success"} />
      {show && (
        <section className="card event-editor">
          <h2>
            {editing
              ? editing.status !== "DRAFT"
                ? "Edit published event"
                : "Edit draft"
              : "New event draft"}
          </h2>
          {(editing?.status === "PUBLISHED" || editing?.status === "PAUSED") && (
            <p className="editor-notice">
              Event dates and capacity are editable. Confirmed tickets follow
              the updated schedule. Registration requirements stay fixed after
              publication.
            </p>
          )}
          <form onSubmit={save}>
            <fieldset disabled={busy} className="event-detail-fields">
            <Select label="Event visibility" value={form.visibility} onChange={value=>setForm({...form,visibility:value})} options={[{value:"PUBLIC",label:"Public — everyone can discover and book"},{value:"ORGANIZATION_ONLY",label:"Organization only — active members"}]} /><p className="muted">Visibility changes apply when you save. Existing tickets remain valid; organization-only events accept new bookings from active members.</p>
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
              <p>
                Details and tickets are saved together. Review ticket sales windows when changing the event date.
              </p>
            )}
            <p className="muted">
              All event times use Singapore time (UTC+08:00).
            </p>
            <div className="form-grid">
              <DateTimeField
                label="Starts at"
                value={form.startsAt}
                disabled={busy}
                onChange={(value) => {setForm({ ...form, startsAt: value });setTickets(rows=>rows.map(t=>t.closesAt?t:{...t,closesAt:value}));}}
              />
              <DateTimeField
                label="Ends at"
                value={form.endsAt}
                after={form.startsAt}
                disabled={busy}
                onChange={(value) => setForm({ ...form, endsAt: value })}
              />
              <label>
                Capacity
                <input
                  disabled={busy}
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
            <fieldset
              className="registration-settings"
              disabled={busy || (editing?.status === "PUBLISHED" || editing?.status === "PAUSED")}
            >
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
            <TicketEditor tickets={tickets} onChange={setTickets} capacity={form.capacity} startsAt={form.startsAt} disabled={busy} />
            <div className="actions">
              <button type="submit" className="primary-button" disabled={busy || tickets.reduce((n,t)=>n+t.quota,0)>form.capacity}>
                {busy
                  ? "Saving…"
                  : (editing?.status === "PUBLISHED" || editing?.status === "PAUSED")
                    ? "Save event changes"
                    : "Save draft"}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => setShow(false)}
              >
                Close editor
              </button>
            </div>
            </fieldset>
          </form>

        </section>
      )}
      {!show && <>
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
                  {d.publicationError && (
                    <p role="alert">{d.publicationError}</p>
                  )}
                </div>
                <div className="actions">
                  <button
                    className="secondary-button"
                    onClick={() => edit(d.id, true)}
                  >
                    Use as template
                  </button>
                  <Link to={`/organizer/events/${d.id}/staff`}>Staff and attendance →</Link>
                  <Link to={`/organizer/events/${d.id}/bookings`}>
                    Registration list →
                  </Link>
                  <Link to={`/organizer/events/${d.id}/setup`}>
                    {d.status === "DRAFT" ? "Publication preview →" : "Publication management →"}
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
      </>}
    </main>
  );
}
