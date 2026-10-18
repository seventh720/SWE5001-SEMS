import {
  createContext,
  type PropsWithChildren,
  useContext,
  useEffect,
  useRef,
  useMemo,
  useState,
} from "react";
import { apiRequest } from "../../shared/api/client";
import type { AuthResponse, User } from "../../shared/types/auth";

interface AuthState {
  token: string;
  user: User;
  expiresAt?: number;
}

interface AuthContextValue {
  sessionExpired: boolean;
  token: string | null;
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  register: (
    username: string,
    email: string,
    password: string,
  ) => Promise<void>;
  logout: () => void;
  updateUser: (user: User) => void;
}

const STORAGE_KEY = "sems-auth";
const AuthContext = createContext<AuthContextValue | null>(null);

function tokenExpiry(token: string): number | undefined {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof payload.exp === "number" ? payload.exp * 1000 : undefined;
  } catch { return undefined; }
}

function loadStoredState(): AuthState | null {
  const value = sessionStorage.getItem(STORAGE_KEY);
  if (!value) return null;
  try {
    const stored = JSON.parse(value) as AuthState;
    stored.expiresAt ??= tokenExpiry(stored.token);
    if (stored.expiresAt !== undefined && stored.expiresAt <= Date.now()) {
      sessionStorage.removeItem(STORAGE_KEY);
      sessionStorage.setItem("sems-session-expired", "true");
      return null;
    }
    return stored;
  } catch {
    sessionStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [state, setState] = useState<AuthState | null>(loadStoredState);

  const current = useRef(state);
  current.current = state;
  const [sessionExpired, setSessionExpired] = useState(() => sessionStorage.getItem("sems-session-expired") === "true");

  useEffect(() => {
    function expire(token: string) {
      if (current.current?.token !== token) return;
      // Preserve user-scoped pending bookings: an earlier request may have committed.
      current.current = null;
      sessionStorage.removeItem(STORAGE_KEY);
      sessionStorage.setItem("sems-session-expired", "true");
      setState(null);
      setSessionExpired(true);
    }
    const unauthorized = (event: Event) => expire((event as CustomEvent<string>).detail);
    const check = () => {
      if (state?.expiresAt !== undefined && state.expiresAt <= Date.now()) expire(state.token);
    };
    window.addEventListener("sems:unauthorized", unauthorized);
    window.addEventListener("focus", check);
    document.addEventListener("visibilitychange", check);
    const timer = state?.expiresAt === undefined ? undefined : window.setTimeout(check, Math.max(0, state.expiresAt - Date.now()));
    return () => {
      window.removeEventListener("sems:unauthorized", unauthorized);
      window.removeEventListener("focus", check);
      document.removeEventListener("visibilitychange", check);
      window.clearTimeout(timer);
    };
  }, [state]);

  async function login(email: string, password: string) {
    const response = await apiRequest<AuthResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    const next = { token: response.accessToken, user: response.user, expiresAt: tokenExpiry(response.accessToken) ?? (response.expiresIn ? Date.now() + response.expiresIn * 1000 : undefined) };
    current.current = next;
    sessionStorage.removeItem("sems-session-expired");
    setSessionExpired(false);
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setState(next);
  }

  async function register(username: string, email: string, password: string) {
    await apiRequest<User>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, email, password }),
    });
    await login(email, password);
  }

  function updateUser(user: User) {
    if (!state) return;
    const next = { ...state, user };
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setState(next);
  }

  function logout() {
    current.current = null;
    sessionStorage.removeItem("sems-session-expired");
    setSessionExpired(false);
    const prefix = `sems-booking:${state?.user.id}:`;
    Object.keys(sessionStorage)
      .filter((key) => key.startsWith(prefix))
      .forEach((key) => sessionStorage.removeItem(key));
    sessionStorage.removeItem(STORAGE_KEY);
    setState(null);
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      sessionExpired,
      token: state?.token ?? null,
      user: state?.user ?? null,
      login,
      register,
      logout,
      updateUser,
    }),
    [state, sessionExpired],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
