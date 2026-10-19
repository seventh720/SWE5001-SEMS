import { HomeLink } from "../../shared/components/HomeLink";
import { type FormEvent, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { ApiError } from "../../shared/api/client";
import { useAuth } from "./AuthContext";

const passwordHelp = "Password must contain 8–16 characters using English letters, numbers or symbols. Spaces are not allowed.";

export function AuthPage() {
  const { user, login, register, sessionExpired } = useAuth();
  const location = useLocation();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (user) {
    const from = (
      location.state as { from?: { pathname?: string; search?: string; hash?: string } } | null
    )?.from;
    const destination = from?.pathname
      ? `${from.pathname}${from.search ?? ""}${from.hash ?? ""}`
      : "/";
    return <Navigate to={destination} replace />;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const validationError =
      mode === "register" && !/^[A-Za-z0-9._-]{3,50}$/.test(username)
        ? "Choose a username with 3–50 letters, numbers, dots, underscores or hyphens."
        : !email.trim() || !/^[^\s@]+@[^\s@]+$/.test(email.trim())
          ? "Enter a valid email address, such as name@example.com."
          : mode === "register" && (password.length < 8 || password.length > 16 || /[^!-~]/.test(password))
            ? passwordHelp
            : password.length < 8 || password.length > 72
              ? "Password must contain 8–72 characters."
              : "";
    if (validationError) {
      setError(validationError);
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      if (mode === "register") {
        await register(username, email, password);
      } else {
        await login(email, password);
      }
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Unable to complete the request",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="brand-panel">
        <p className="eyebrow">SEMS · Discover and connect</p>
        <h1>Smart Event Management and Ticketing Platform</h1>
        <p>
          Discover events, explore new interests, and bring people together.
        </p>
        <ul>
          <li>Create an attendee account</li>
          <li>Organize your next event</li>
          <li>Sign in to your personal dashboard</li>
        </ul>
      </section>

      <section className="form-panel">
        <HomeLink />
        <div
          className="auth-tabs"
          role="tablist"
          aria-label="Authentication mode"
        >
          <button
            className={mode === "login" ? "active" : ""}
            onClick={() => setMode("login")}
          >
            Login
          </button>
          <button
            className={mode === "register" ? "active" : ""}
            onClick={() => setMode("register")}
          >
            Register
          </button>
        </div>

        {sessionExpired && <p role="status">Your session has expired. Sign in again to continue. Pending bookings are preserved.</p>}
        <form noValidate onSubmit={submit}>
          <h2>
            {mode === "login" ? "Welcome back" : "Create attendee account"}
          </h2>
          {mode === "register" && (
            <label>
              Username
              <input
                autoComplete="username"
                pattern={"[A-Za-z0-9._\\-]+"}
                aria-describedby="username-help"
                minLength={3}
                maxLength={50}
                required
                value={username}
                onChange={(event) => setUsername(event.target.value)}
              />
            </label>
          )}
          {mode === "register" && (
            <p className="muted" id="username-help">
              Choose a unique username (3–50 letters, numbers, dots, underscores
              or hyphens). Usernames are saved in lowercase and shown on your
              dashboard.
            </p>
          )}
          <label>
            Email
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete={
                mode === "login" ? "current-password" : "new-password"
              }
              minLength={8}
              maxLength={mode === "register" ? 16 : 72}
              pattern={mode === "register" ? "[!-~]{8,16}" : undefined}
              aria-describedby={mode === "register" ? "password-help" : undefined}
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {mode === "register" && <p className="muted" id="password-help">{passwordHelp}</p>}
          {error && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}
          <button
            className="primary-button"
            disabled={submitting}
            type="submit"
          >
            {submitting
              ? "Please wait..."
              : mode === "login"
                ? "Login"
                : "Register and login"}
          </button>
        </form>
      </section>
    </main>
  );
}
