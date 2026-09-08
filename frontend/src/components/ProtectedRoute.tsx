import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

/** Guards a route for authenticated volunteers. */
export function RequireUser({ children }: { children: React.ReactNode }) {
  const { isUser } = useAuth();
  const location = useLocation();
  if (!isUser) return <Navigate to="/login" state={{ from: location }} replace />;
  return <>{children}</>;
}

/** Guards a route for authenticated admins. */
export function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { isAdmin } = useAuth();
  if (!isAdmin) return <Navigate to="/admin/login" replace />;
  return <>{children}</>;
}