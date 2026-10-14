import { Link } from "react-router-dom";
import { useAuth } from "../../features/auth/AuthContext";

export function HomeLink() {
  const { user } = useAuth();
  return <Link className="back-link" to="/">← Back to {user ? "dashboard" : "home"}</Link>;
}
