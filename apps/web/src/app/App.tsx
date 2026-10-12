import { Link, Route, Routes } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";
import { AuthPage } from "../features/auth/AuthPage";
import { AdminUsersPage } from "../features/admin/AdminUsersPage";
import { DraftsPage } from "../features/events/DraftsPage";
import { EventSetupPage } from "../features/events/EventSetupPage";
import {
  PublicEventsPage,
  PublicEventDetail,
} from "../features/events/PublicEventsPage";
import { ProtectedRoute } from "./ProtectedRoute";
function Home() {
  const { user } = useAuth();
  return (
    <main className="app-shell">
      <section className="hero">
        <p className="eyebrow">ONE PLATFORM. YOUR COMMUNITY.</p>
        <h1>Bring your next event to life.</h1>
        <p>A shared home for independent organizers and their communities.</p>
        {user ? (
          <>
            <h2>Welcome, {user.username}</h2>
            <p>{user.roles.join(" · ")}</p>
            {user.roles.some((r) => r === "ORGANIZER" || r === "ADMIN") ? (
              <Link className="primary-button" to="/organizer/events">
                Manage my events
              </Link>
            ) : (
              <p>
                Your attendee account is ready. Contact an administrator to
                request organizer access.
              </p>
            )}
            {user.roles.includes("ADMIN") && (
              <Link className="text-link" to="/admin/users">
                Manage users and roles →
              </Link>
            )}
          </>
        ) : (
          <Link className="primary-button" to="/login">
            Sign in or create an account
          </Link>
        )}
      </section>
      <section className="card">
        <Link to="/events">Browse events →</Link>
        <h2>Discover events from your community</h2>
        <p>
          Browse upcoming events and free admission options from independent
          organizers.
        </p>
      </section>
    </main>
  );
}
export function App() {
  const { user, logout } = useAuth();
  return (
    <>
      <nav className="topbar">
        <Link to="/" className="brand">
          SEMS <span>EVENT PLATFORM</span>
        </Link>
        <div>
          {user && <span>{user.username}</span>}
          {user ? (
            <button onClick={logout}>Sign out</button>
          ) : (
            <Link to="/login">Sign in</Link>
          )}
        </div>
      </nav>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/events" element={<PublicEventsPage />} />
        <Route path="/events/:id" element={<PublicEventDetail />} />
        <Route path="/login" element={<AuthPage />} />
        <Route element={<ProtectedRoute />}>
          <Route
            path="/organizer/events/:id/setup"
            element={<EventSetupPage />}
          />
          <Route path="/admin/users" element={<AdminUsersPage />} />
          <Route path="/organizer/events" element={<DraftsPage />} />
        </Route>
        <Route
          path="*"
          element={
            <main className="app-shell">
              <h1>Page not found</h1>
              <Link to="/">Return home</Link>
            </main>
          }
        />
      </Routes>
    </>
  );
}
