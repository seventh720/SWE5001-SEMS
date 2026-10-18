import { SessionRecovery } from "../features/auth/SessionRecovery";
import {OrganizationMembersPage} from "../features/organizations/OrganizationMembersPage";
import {NotificationBell,NotificationsPage} from "../features/notifications/Notifications";
import {OrganizationsPage,AdminOrganizationsPage,AcceptInvitationPage} from "../features/organizations/OrganizationsPage";
import {StaffTasksPage,CheckInPage,EventStaffPage} from "../features/organizations/StaffPage";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { ProfilePage } from "../features/profile/ProfilePage";
import { PreRegistrationsPage } from "../features/bookings/PreRegistrationsPage";
import { OrganizerBookingsPage } from "../features/bookings/OrganizerBookingsPage";
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

import { BookingDetail, BookingsPage } from "../features/bookings/BookingsPage";
function Home() {
  const { user } = useAuth();
  return user ? <DashboardPage /> : <Landing />;
}
function Landing() {
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
            <Link className="secondary-button" to="/bookings">
              My tickets ↗
            </Link>
            {organizer && (
              <Link className="secondary-button" to="/organizer/events">
                My events ↗
              </Link>
            )}
            <Link to="/staff">My check-in tasks <span>Assigned events</span></Link>
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
  const { user } = useAuth();
  return (
    <nav
      id="explore-navigation"
      className="explore-expanded"
      aria-label="Explore navigation"
    >
      <Link to="/" onClick={onClose}>
        Home <span>Start here</span>
      </Link>
      <Link to="/events" onClick={onClose}>
        Discover events <span>Find your next experience</span>
      </Link>
      {user ? (
        <>
          <Link to="/bookings" onClick={onClose}>
            My tickets <span>Confirmed bookings</span>
          </Link>
          <Link to="/pre-registrations" onClick={onClose}>
            My pre-registrations <span>Get ready for opening</span>
          </Link>
          <Link to="/profile" onClick={onClose}>
            My profile <span>Saved registration details</span>
          </Link>
          {true && (
            <Link to="/organizations" onClick={onClose}>
              My organizations <span>Memberships and events</span>
            </Link>
          )}
          <Link to="/staff" onClick={onClose}>My check-in tasks <span>Assigned events</span></Link>
          {user.roles.includes("ADMIN") && (
            <Link to="/admin/users" onClick={onClose}>
              Manage users <span>Roles and access</span>
            </Link>
          )}
        </>
      ) : (
        <Link to="/login" onClick={onClose}>
          Join the community <span>Sign in or create an account</span>
        </Link>
      )}
    </nav>
  );
}

export function App() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const exploreTrigger = useRef<HTMLButtonElement>(null);
  const [menu, setMenu] = useState(false);
  useEffect(() => {
    if (!menu) return;
    const dismiss = (e: PointerEvent) => {
      if (e.target instanceof Element && !e.target.closest(".site-header"))
        setMenu(false);
    };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, [menu]);
  const [paused, setPaused] = useState(
    () =>
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false,
  );
  useEffect(() => {
    setMenu(false);
  }, [location.pathname]);
  return (
    <div
      className={paused ? "platform motion-paused" : "platform"}
      onKeyDown={(e) => {
        if (e.key === "Escape" && menu) {
          setMenu(false);
          exploreTrigger.current?.focus();
        }
      }}
    >
      <div className="ambient-background" aria-hidden="true">
        <div className="ambient-orb orb-lilac" />
        <div className="ambient-orb orb-peach" />
        <div className="ambient-grid" />
      </div>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="site-header">
        <nav className="topbar" aria-label="Main navigation">
          <Link to="/" className="brand">
            <img className="brand-icon" src="/favicon.svg" alt="" />
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
                <NotificationBell/><span className="nav-username">{user.username}</span>
                <button onClick={logout}>Sign out</button>
              </>
            ) : (
              <Link className="nav-signin" to="/login">
                Sign in ↗
              </Link>
            )}
            <button
              className="menu-toggle"
              ref={exploreTrigger}
              aria-controls="explore-navigation"
              aria-expanded={menu}
              onClick={() => setMenu(!menu)}
            >
              Explore <span aria-hidden="true">☰</span>
            </button>
          </div>
        </nav>
        {menu && <ExploreMenu onClose={() => setMenu(false)} />}
      </header>
      <div
        className="route-surface"
        key={location.pathname}
        id={location.pathname === "/" ? undefined : "main-content"}
        tabIndex={-1}
      >
        <SessionRecovery />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/events" element={<PublicEventsPage />} />
          <Route path="/events/:id" element={<PublicEventDetail />} />
          <Route path="/login" element={<AuthPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/organizations" element={<OrganizationsPage/>}/><Route path="/organizations/:id/members" element={<OrganizationMembersPage/>}/><Route path="/admin/organizations" element={<AdminOrganizationsPage/>}/><Route path="/invitations/accept" element={<AcceptInvitationPage/>}/><Route path="/staff" element={<StaffTasksPage/>}/><Route path="/staff/events/:id" element={<CheckInPage/>}/><Route path="/organizer/events/:id/staff" element={<EventStaffPage/>}/>
            <Route path="/notifications" element={<NotificationsPage/>}/><Route path="/profile" element={<ProfilePage />} />
            <Route
              path="/pre-registrations"
              element={<PreRegistrationsPage />}
            />
            <Route
              path="/organizer/events/:id/bookings"
              element={<OrganizerBookingsPage />}
            />
            <Route path="/bookings" element={<BookingsPage />} />
            <Route path="/bookings/:id" element={<BookingDetail />} />
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
