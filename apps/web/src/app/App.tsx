import { useEffect, useRef, useState } from "react";
import { Link, Route, Routes, useLocation } from "react-router-dom";
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
  const organizer = user?.roles.some((r) => r === "ORGANIZER" || r === "ADMIN");
  return (
    <main className="app-shell home-shell" id="main-content">
      <section className="home-hero">
        <div className="hero-copy">
          <p className="eyebrow">
            <span className="live-dot" /> GOOD THINGS HAPPEN TOGETHER
          </p>
          <h1>
            Go out.
            <br />
            Find your <em>people.</em>
          </h1>
          <p className="hero-description">
            A new interest. A shared moment. Your next favourite community. Find
            an event that feels like you.
          </p>
          <div className="actions hero-actions">
            <Link className="primary-button" to="/events">
              Explore events <span aria-hidden="true">↗</span>
            </Link>
            <Link
              className="secondary-button"
              to={
                user ? (organizer ? "/organizer/events" : "/events") : "/login"
              }
            >
              {user
                ? organizer
                  ? "Manage my events"
                  : "Browse with your community"
                : "Join the community"}
            </Link>
          </div>
          <p className="hero-footnote">
            Independent organizers. Shared experiences.
          </p>
        </div>
        <div className="event-art" aria-hidden="true">
          <div className="art-orbit orbit-one" />
          <div className="art-orbit orbit-two" />
          <div className="art-star">✳</div>
          <div className="art-note note-top">MAKE SOME MEMORIES ↗</div>
          <div className="art-ticket ticket-back">
            <span>MEET / MAKE / CONNECT</span>
            <div className="ticket-flower">✳</div>
          </div>
          <div className="art-ticket ticket-front">
            <div className="ticket-top">
              <span>SEMS / COMMUNITY</span>
              <span>↗</span>
            </div>
            <div className="ticket-title">
              You had
              <br />
              to be there.
            </div>
            <div className="ticket-bottom">
              <span>
                YOUR NEXT
                <br />
                GOOD STORY
              </span>
              <div className="ticket-barcode" />
            </div>
          </div>
          <div className="art-note note-bottom">
            <span className="live-dot" /> A LITTLE MORE TOGETHER.
          </div>
        </div>
      </section>
      {user && (
        <section className="welcome-strip">
          <div>
            <p className="eyebrow">YOUR SPACE</p>
            <h2>Welcome back, {user.username}.</h2>
            <p className="muted">
              {organizer
                ? "Give your next idea a place to happen."
                : "Take a look at what your community has planned."}
            </p>
          </div>
          <div className="actions">
            {organizer && (
              <Link className="secondary-button" to="/organizer/events">
                My events ↗
              </Link>
            )}
            {user.roles.includes("ADMIN") && (
              <Link className="text-link" to="/admin/users">
                Manage users and roles →
              </Link>
            )}
          </div>
        </section>
      )}
      <section className="discovery-section" aria-labelledby="discovery-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">LESS SCROLLING. MORE SHOWING UP.</p>
            <h2 id="discovery-title">Make room for something new.</h2>
          </div>
          <Link className="text-link" to="/events">
            Browse events ↗
          </Link>
        </div>
        <div className="discovery-grid">
          <Link className="discovery-card discovery-lilac" to="/events">
            <span className="discovery-symbol" aria-hidden="true">
              ✳
            </span>
            <span className="card-kicker">01 / DISCOVER</span>
            <h3>Follow your curiosity.</h3>
            <p>Find upcoming events from independent organizers.</p>
            <span className="card-arrow" aria-hidden="true">
              ↗
            </span>
          </Link>
          <Link
            className="discovery-card discovery-lime"
            to={organizer ? "/organizer/events" : "/login"}
          >
            <span className="discovery-symbol" aria-hidden="true">
              ↗
            </span>
            <span className="card-kicker">02 / CREATE</span>
            <h3>Bring people together.</h3>
            <p>
              {organizer
                ? "Turn your idea into an event worth sharing."
                : "Sign in to get started. Organizer access is assigned by an administrator."}
            </p>
            <span className="card-arrow" aria-hidden="true">
              ↗
            </span>
          </Link>
        </div>
      </section>
      <footer className="home-footer">
        <span>SEMS — Made for getting together.</span>
        <span>Smart Event Management and Ticketing Platform</span>
      </footer>
    </main>
  );
}

function ExploreMenu({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const { user } = useAuth();
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const element = dialog.current!;
    element.showModal();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      element.close();
      document.body.style.overflow = overflow;
      opener?.focus();
    };
  }, []);
  return (
    <dialog
      ref={dialog}
      className="explore-dialog"
      aria-labelledby="explore-title"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <div className="overlay-top">
        <span className="brand">
          SEMS <span>MAKE IT A MOMENT</span>
        </span>
        <button
          onClick={onClose}
          className="close-menu"
          aria-label="Close navigation"
        >
          Close ×
        </button>
      </div>
      <div className="overlay-content">
        <p className="eyebrow">WHERE TO NEXT?</p>
        <h2 id="explore-title">
          A world of
          <br />
          <em>possibilities.</em>
        </h2>
        <nav aria-label="Explore navigation" className="overlay-links">
          <Link to="/" onClick={onClose}>
            <span className="overlay-index">01</span>
            <span className="overlay-label">Home</span>
            <span className="overlay-arrow" aria-hidden="true">
              ↗
            </span>
          </Link>
          <Link to="/events" onClick={onClose}>
            <span className="overlay-index">02</span>
            <span className="overlay-label">Discover events</span>
            <span className="overlay-arrow" aria-hidden="true">
              ↗
            </span>
          </Link>
          {user?.roles.some((r) => r === "ORGANIZER" || r === "ADMIN") && (
            <Link to="/organizer/events" onClick={onClose}>
              <span className="overlay-index">03</span>
              <span className="overlay-label">My events</span>
              <span className="overlay-arrow" aria-hidden="true">
                ↗
              </span>
            </Link>
          )}
          {user?.roles.includes("ADMIN") && (
            <Link to="/admin/users" onClick={onClose}>
              <span className="overlay-index">04</span>
              <span className="overlay-label">Manage users</span>
              <span className="overlay-arrow" aria-hidden="true">
                ↗
              </span>
            </Link>
          )}
          {!user && (
            <Link to="/login" onClick={onClose}>
              <span className="overlay-index">03</span>
              <span className="overlay-label">Join the community</span>
              <span className="overlay-arrow" aria-hidden="true">
                ↗
              </span>
            </Link>
          )}
        </nav>
      </div>
      <p className="overlay-footer">Find something worth stepping out for.</p>
    </dialog>
  );
}

export function App() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [menu, setMenu] = useState(false);
  const [paused, setPaused] = useState(
    () =>
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false,
  );
  useEffect(() => {
    setMenu(false);
  }, [location.pathname]);
  return (
    <div className={paused ? "platform motion-paused" : "platform"}>
      <div className="ambient-background" aria-hidden="true">
        <div className="ambient-orb orb-lilac" />
        <div className="ambient-orb orb-peach" />
        <div className="ambient-grid" />
      </div>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <nav className="topbar" aria-label="Main navigation">
        <Link to="/" className="brand">
          SEMS<span>GET TOGETHER</span>
        </Link>
        <div className="nav-actions">
          <button
            className="motion-toggle"
            aria-pressed={paused}
            onClick={() => setPaused(!paused)}
          >
            {paused ? "Enable motion" : "Pause motion"}
          </button>
          {user ? (
            <>
              <span className="nav-username">{user.username}</span>
              <button onClick={logout}>Sign out</button>
            </>
          ) : (
            <Link className="nav-signin" to="/login">
              Sign in ↗
            </Link>
          )}
          <button
            className="menu-toggle"
            aria-haspopup="dialog"
            aria-expanded={menu}
            onClick={() => setMenu(true)}
          >
            Explore <span aria-hidden="true">☰</span>
          </button>
        </div>
      </nav>
      {menu && <ExploreMenu onClose={() => setMenu(false)} />}
      <div
        className="route-surface"
        key={location.pathname}
        id={location.pathname === "/" ? undefined : "main-content"}
        tabIndex={-1}
      >
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
      </div>
    </div>
  );
}
