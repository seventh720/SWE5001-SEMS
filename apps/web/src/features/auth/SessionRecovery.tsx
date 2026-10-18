import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function SessionRecovery() {
  const { user, sessionExpired } = useAuth();
  const location = useLocation();
  return sessionExpired && !user && location.pathname !== "/login"
    ? <Navigate to="/login" replace state={{ from: location }} />
    : null;
}
