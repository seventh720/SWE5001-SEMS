import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { apiRequest, ApiError } from "../../shared/api/client";
import { hasRole, roleLabel } from "../../shared/auth/roles";
import { roles, type Role, type User } from "../../shared/types/auth";

export function AdminUsersPage() {
  const { user: currentUser, token } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState("");
  const [savingId, setSavingId] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !currentUser || !hasRole(currentUser.roles, "ADMIN")) return;
    apiRequest<User[]>("/api/v1/admin/users", {}, token)
      .then(setUsers)
      .catch((caught) =>
        setError(
          caught instanceof ApiError ? caught.message : "Unable to load users",
        ),
      );
  }, [currentUser, token]);

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
    setSavingId(target.id);
    setError("");
    try {
      const updated = await apiRequest<User>(
        `/api/v1/admin/users/${target.id}/roles`,
        { method: "PUT", body: JSON.stringify({ roles: target.roles }) },
        token!,
      );
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
          <Link className="text-link" to="/">
            Back to dashboard
          </Link>
          <h1>User and role management</h1>
        </div>
      </header>

      <p className="muted">
        Role changes take effect after the user signs in again. Existing tokens
        expire within 30 minutes.
      </p>
      {error && <p className="error-message">{error}</p>}
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
              {roles.map((role) => (
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
    </main>
  );
}
