import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Layout({ children }: { children: React.ReactNode }) {
  const { isUser, isAdmin, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/");
  };

  const navLink = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-1.5 rounded-md text-sm font-medium transition ${
      isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"
    }`;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-40">
        <nav className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 font-semibold text-lg text-brand-700">
            <span className="w-8 h-8 rounded-lg bg-brand-600 text-white grid place-items-center">
              🎓
            </span>
            Bahraini 28
          </Link>
          <div className="flex items-center gap-3">
            <NavLink to="/directory" className={navLink}>
              Directory
            </NavLink>
            {isUser ? (
              <>
                <NavLink to="/profile" className={navLink}>
                  My Profile
                </NavLink>
                <button onClick={handleLogout} className="btn-secondary">
                  Logout
                </button>
              </>
            ) : (
              <Link to="/login" className="btn-primary">
                Member Login
              </Link>
            )}
            {isAdmin && (
              <Link to="/admin" className="btn-secondary">
                Admin
              </Link>
            )}
          </div>
        </nav>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8 flex-1 w-full">{children}</main>

      <footer className="border-t border-slate-200">
        <div className="max-w-6xl mx-auto px-4 py-6 text-sm text-slate-500 flex flex-wrap gap-4 justify-between">
          <span>© Bahraini 28 · bahraini28.com</span>
          <span>Volunteer discount tracking portal</span>
        </div>
      </footer>
    </div>
  );
}