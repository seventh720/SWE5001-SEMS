import {
  createContext,
  type PropsWithChildren,
  useContext,
  useMemo,
  useState,
} from "react";
import { apiRequest } from "../../shared/api/client";
import type { AuthResponse, User } from "../../shared/types/auth";

interface AuthState {
  token: string;
  user: User;
}

interface AuthContextValue {
  token: string | null;
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  register: (
    username: string,
    email: string,
    password: string,
  ) => Promise<void>;
  logout: () => void;
}

const STORAGE_KEY = "sems-auth";
const AuthContext = createContext<AuthContextValue | null>(null);

function loadStoredState(): AuthState | null {
  const value = sessionStorage.getItem(STORAGE_KEY);
  if (!value) return null;
  try {
    return JSON.parse(value) as AuthState;
  } catch {
    sessionStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [state, setState] = useState<AuthState | null>(loadStoredState);

  async function login(email: string, password: string) {
    const response = await apiRequest<AuthResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    const next = { token: response.accessToken, user: response.user };
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

  function logout() {
    const prefix = `sems-booking:${state?.user.id}:`;
    Object.keys(sessionStorage)
      .filter((key) => key.startsWith(prefix))
      .forEach((key) => sessionStorage.removeItem(key));
    sessionStorage.removeItem(STORAGE_KEY);
    setState(null);
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      token: state?.token ?? null,
      user: state?.user ?? null,
      login,
      register,
      logout,
    }),
    [state],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
