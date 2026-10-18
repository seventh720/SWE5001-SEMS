import { HomeLink } from "../../shared/components/HomeLink";
import { FeedbackNotice } from "../../shared/components/FeedbackNotice";
import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { apiRequest, ApiError } from "../../shared/api/client";
import { hasRole, roleLabel } from "../../shared/auth/roles";
import { roles, type Role, type User } from "../../shared/types/auth";

export function AdminUsersPage() {
  const { user: currentUser, token } = useAuth();
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [savingId, setSavingId] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !currentUser || !hasRole(currentUser.roles, "ADMIN")) return;
    let active = true;
    setLoading(true); setError(""); setUsers([]);
    apiRequest<{items: User[]; totalPages: number}>(`/api/v1/admin/users?page=${page}&size=20&search=${encodeURIComponent(search)}`, {}, token)
      .then(data => {if(active){setUsers(data.items);setTotalPages(data.totalPages)}})
      .catch((caught) =>
        active && setError(
          caught instanceof ApiError ? caught.message : "Unable to load users",
        ),
      ).finally(() => {if(active)setLoading(false)});
    return () => {active=false};
  }, [currentUser, token, page, search]);

  if (!currentUser || !token) return null;
  if (!hasRole(currentUser.roles, "ADMIN")) return <Navigate to="/" replace />;

  function toggleRole(userId: string, role: Role) {
    setUsers((current) =>
      current.map((item) => {
        if (item.id !== userId) return item;
        const nextRoles = item.roles.includes(role)
          ? item.roles.filter((candidate) => candidate !== role)
          : [...item.roles, role];
        return nextRoles.length === 0 ? item : { ...item, roles: nextRoles };
      }),
    );
  }

  async function saveRoles(target: User) {
    setMessage("");
    setSavingId(target.id);
    setError("");
    try {
      const updated = await apiRequest<User>(
        `/api/v1/admin/users/${target.id}/roles`,
        { method: "PUT", body: JSON.stringify({ roles: target.roles }) },
        token!,
      );
      setMessage(`Roles saved for ${updated.username}. New grants apply after their next sign-in. Removed administrator access stops immediately.`);
      setUsers((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Unable to update roles",
      );
    } finally {
      setSavingId(null);
    }
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <HomeLink />
          <h1>User and role management</h1>
        </div>
      </header>

      <p className="muted">
        Organization roles are managed in My organizations; check-in access is assigned per event. New platform grants take effect after sign-in; administrator revocation takes effect immediately. Sessions expire after one hour.
      </p>
      {error && <p className="error-message">{error}</p>}
      <FeedbackNotice message={message} />
      <label>Search users<input type="search" maxLength={200} value={search} onChange={e=>{setSearch(e.target.value);setPage(0)}} /></label>
      {loading && <p role="status">Loading users…</p>}
      <section className="user-list">
        {users.map((item) => (
          <article className="card user-card" key={item.id}>
            <div>
              <h2>{item.username}</h2>
              <p>{item.email}</p>
              <p className="muted">{item.status}</p>
            </div>
            <fieldset>
              <legend>Roles</legend>
              {roles.filter(role => role === "ATTENDEE" || role === "ADMIN").map((role) => (
                <label className="role-option" key={role}>
                  <input
                    type="checkbox"
                    checked={item.roles.includes(role)}
                    onChange={() => toggleRole(item.id, role)}
                  />
                  {roleLabel(role)}
                </label>
              ))}
            </fieldset>
            <button
              className="primary-button compact"
              disabled={savingId === item.id}
              onClick={() => saveRoles(item)}
            >
              {savingId === item.id ? "Saving..." : "Save roles"}
            </button>
          </article>
        ))}
      </section>
      <nav aria-label="User pages"><button disabled={loading||page===0} onClick={()=>setPage(page-1)}>Previous</button><span>Page {page+1} of {Math.max(1,totalPages)}</span><button disabled={loading||page+1>=totalPages} onClick={()=>setPage(page+1)}>Next</button></nav>
    </main>
  );
}
