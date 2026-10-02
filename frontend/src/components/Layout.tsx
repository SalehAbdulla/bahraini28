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
    `px-3 py-1.5 rounded-md text-sm font-medium whitespace-nowrap transition ${
      isActive
        ? "bg-brand-100 text-brand-800"
        : "text-ink-800/70 hover:bg-brand-50 hover:text-brand-800"
    }`;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-40 border-b border-brush/25 bg-cream-50/90 backdrop-blur">
        <nav className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5">
            {/* Official Bahraini 28 mark (green brush lettering + "28").
                The 240px `logo-sm` variant covers every on-screen slot — 36px
                here, 44px and 56px on the landing page — at up to 4× DPR, so
                the 480px master is kept in the repo but never shipped. */}
            <img src="/brand/logo-sm.png" alt="Bahraini 28" className="h-9 w-auto" />
            {/* The mark already contains the wordmark — hide the redundant
                English lock-up on narrow screens so the nav never wraps. */}
            <span className="hidden whitespace-nowrap text-lg font-semibold tracking-tight text-ink-900 sm:inline">
              Bahraini <span className="text-brand-600">28</span>
            </span>
          </Link>
          <div className="flex items-center gap-2 sm:gap-3">
            <NavLink to="/directory" className={navLink}>
              Directory
            </NavLink>
            {isUser ? (
              <>
                <NavLink to="/profile" className={navLink}>
                  My Profile
                </NavLink>
                <button onClick={handleLogout} className="btn-secondary whitespace-nowrap">
                  Logout
                </button>
              </>
            ) : (
              <Link to="/login" className="btn-primary whitespace-nowrap">
                Member Login
              </Link>
            )}
            {isAdmin && (
              <Link to="/admin" className="btn-secondary whitespace-nowrap">
                Admin
              </Link>
            )}
          </div>
        </nav>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8 flex-1 w-full">{children}</main>

      <footer className="mt-6 border-t border-brush/25 bg-cream-100/70">
        <div className="max-w-6xl mx-auto px-4 py-8 flex flex-wrap items-center justify-between gap-5">
          <div className="flex items-center gap-3">
            {/* 44 px slot -> the 160 px variant. Reusing the 768 px hero badge
                would add ~115 KB to every page for no visible gain. */}
            <img
              src="/brand/badge-sm.png"
              alt=""
              aria-hidden="true"
              className="h-11 w-11"
            />
            <div className="text-sm text-ink-800/80">
              <p className="font-script text-2xl leading-none text-brand-700">
                Bahraini 28
              </p>
              <p className="mt-1.5">
                © {new Date().getFullYear()} Bahraini 28 · bahraini28.com — volunteer
                discount tracking portal
              </p>
            </div>
          </div>
          {/* The organisation's tagline, exactly as set in the brand deck. */}
          <p dir="rtl" lang="ar" className="text-sm font-medium text-brand-700">
            شراكة مجتمعية معطاءة.. بين شغف مواطن، ووقفة وطن!
          </p>
        </div>
      </footer>
    </div>
  );
}