import { HomeLink } from "../../shared/components/HomeLink";
import { FeedbackNotice } from "../../shared/components/FeedbackNotice";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiRequest } from "../../shared/api/client";
import type { User } from "../../shared/types/auth";
import { useAuth } from "../auth/AuthContext";
import { registrationFields } from "../bookings/registration";
import type { SavedContact } from "./contacts";
const blank: SavedContact = { id: "", label: "", version: 0 };
export function ProfilePage() {
  const { token, user, updateUser } = useAuth();
  const [contacts, setContacts] = useState<SavedContact[]>([]);
  const [contact, setContact] = useState<SavedContact | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [username, setUsername] = useState(user?.username ?? "");
  const [usernameSaved, setUsernameSaved] = useState("");
  const [usernameMessage, setUsernameMessage] = useState("");
  const [usernameError, setUsernameError] = useState("");
  const [renaming, setRenaming] = useState(false);
  const checkSequence = useRef(0);
  async function load() {
    setLoading(true);
    try { setContacts(await apiRequest<SavedContact[]>("/api/v1/profile/contacts", {}, token!)); setError(""); }
    catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, [token]);
  async function save(e: FormEvent) {
    e.preventDefault();
    if (!contact) return;
    setBusy(true); setError(""); setMessage(""); setUsernameSaved("");
    try {
      const saved = await apiRequest<SavedContact>(`/api/v1/profile/contacts${contact.id ? `/${contact.id}` : ""}`,
        { method: contact.id ? "PUT" : "POST", body: JSON.stringify(contact) }, token!);
      setContacts(rows => [...rows.filter(c => c.id !== saved.id), saved]);
      setContact(null);
      setMessage("Contact saved. Choose it when applying details to a registration.");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function remove() {
    if (!contact?.id) return;
    setBusy(true); setError(""); setMessage(""); setUsernameSaved("");
    try {
      await apiRequest(`/api/v1/profile/contacts/${contact.id}?version=${contact.version}`, { method: "DELETE" }, token!);
      setContacts(rows => rows.filter(c => c.id !== contact.id));
      setContact(null); setDeleting(false);
      setMessage("Contact deleted. Existing bookings and pre-registrations keep their submitted details.");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function checkUsername() {
    const sequence = ++checkSequence.current;
    setUsernameMessage(""); setUsernameError("");
    try {
      const result = await apiRequest<{username: string; available: boolean}>(`/api/v1/profile/username?value=${encodeURIComponent(username)}`, {}, token!);
      if (sequence !== checkSequence.current) return;
      if (result.available) setUsernameMessage(result.username === user?.username ? "This is your current username." : "Username available.");
      else setUsernameError("Username is already registered.");
    } catch (e) { if (sequence === checkSequence.current) setUsernameError((e as Error).message); }
  }
  async function rename(e: FormEvent) {
    e.preventDefault(); setMessage(""); ++checkSequence.current; setRenaming(true); setUsernameSaved(""); setUsernameError(""); setUsernameMessage("");
    try {
      const updated = await apiRequest<User>("/api/v1/profile/username", {method: "PUT", body: JSON.stringify({username})}, token!);
      updateUser(updated); setUsername(updated.username); setUsernameSaved("Username updated. Your email and bookings are unchanged.");
    } catch (e) { setUsernameError((e as Error).message); }
    finally { setRenaming(false); }
  }
  return <main className="app-shell profile-workspace">
    <HomeLink />
    <p className="eyebrow">YOUR SPACE</p><h1>My profile</h1>
    <section className="card account-settings"><h2>Account</h2>
      <form onSubmit={rename}>
        <label>Username<input required minLength={3} maxLength={50} pattern="[A-Za-z0-9._\-]+" value={username} disabled={renaming}
          onChange={e => { ++checkSequence.current; setUsername(e.target.value); setUsernameError(""); setUsernameMessage(""); }} onBlur={() => { if (!renaming) void checkUsername(); }} /></label>
        <p className="muted">3–50 letters, numbers, dots, underscores or hyphens. Usernames are lowercase and unique.</p>
        <button disabled={renaming} className="primary-button">Save username</button>
        {usernameError && <p role="alert" className="error-message">{usernameError}</p>}
        {usernameMessage && <p role="status">{usernameMessage}</p>}
      </form>
    </section>
    <section aria-labelledby="saved-details-heading">
      <header className="app-header"><div><h2 id="saved-details-heading">Saved registration details</h2><p className="muted">Optional contacts for you and the people you book for.</p></div>
        <button className="secondary-button" disabled={busy || loading} onClick={() => { setContact({...blank}); setDeleting(false); setMessage(""); setError(""); }}>Add contact</button>
      </header>
      <aside className="privacy-note"><span aria-hidden="true">◇</span><div><strong>You choose what to save and share</strong><p>Save another person’s details only with their permission. Saved contacts are private to your account. Applying one fills the form for review; details are sent to the organizer when you confirm a booking. Your account email stays unchanged.</p></div></aside>
      {loading ? <p role="status">Loading saved contacts…</p> : <div className="saved-contact-grid">
        {contacts.map(c => <article className="card saved-contact" key={c.id}><h3>{c.label}</h3><p>{c.realName || "No name saved"}</p><p className="muted">{c.email || "No contact email saved"}</p><button className="secondary-button" disabled={busy} onClick={() => {setContact({...c}); setDeleting(false); setError(""); setMessage("");}}>Edit {c.label}</button></article>)}
        {!contacts.length && <p>No saved contacts yet. Add one to reuse your registration details.</p>}
      </div>}
      {contact && <form className="card profile-form" onSubmit={save}>
        <h3>{contact.id ? "Edit contact" : "New contact"}</h3>
        <fieldset disabled={busy}><legend className="sr-only">Saved contact details</legend>
          <label>Contact label<input required maxLength={60} placeholder="e.g. Myself, Family, Alex" value={contact.label} onChange={e => setContact({...contact, label:e.target.value})} /></label>
          {registrationFields.filter(f => f.key !== "studentId").map(f => <label key={f.key}>{f.label}<input type={f.type} maxLength={f.max} value={contact[f.key] ?? ""} onChange={e => setContact({...contact, [f.key]:e.target.value})} /></label>)}
        </fieldset>
        <div className="actions"><button disabled={busy} className="primary-button">Save contact</button><button type="button" disabled={busy} className="secondary-button" onClick={() => setContact(null)}>Cancel</button>
          {contact.id && <button type="button" disabled={busy} className="secondary-button" onClick={() => setDeleting(true)}>Delete contact</button>}</div>
        {deleting && <div className="editor-notice"><p>Delete “{contact.label}”? Submitted bookings will keep their details.</p><button type="button" disabled={busy} onClick={remove}>Confirm delete</button><button type="button" disabled={busy} onClick={() => setDeleting(false)}>Keep contact</button></div>}
      </form>}
      {error && <div role="alert" className="error-message"><p>{error}</p><button disabled={busy} onClick={() => {setContact(null); void load();}}>Reload contacts</button></div>}
      <FeedbackNotice message={message || usernameSaved} />
    </section>
  </main>;
}
