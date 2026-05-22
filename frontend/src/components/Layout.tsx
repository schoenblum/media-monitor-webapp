import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

const navItems = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/searches", label: "Searches" },
  { to: "/languages", label: "Languages" },
  { to: "/outlets", label: "Outlets" },
  { to: "/runs", label: "Run History" },
  { to: "/settings", label: "Settings" },
  { to: "/manual", label: "Manual" },
];

const APP_VERSION = "2.2.0";

export default function Layout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-brand text-white shadow">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <span className="text-xl font-semibold tracking-tight">Media Monitor</span>
          </div>
          <nav className="hidden md:flex items-center gap-1 text-sm">
            {navItems.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 transition ${
                    isActive ? "bg-white/15 font-semibold" : "hover:bg-white/10"
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
            {user?.role === "admin" && (
              <NavLink
                to="/admin"
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 transition ${
                    isActive ? "bg-white/15 font-semibold" : "hover:bg-white/10"
                  }`
                }
              >
                Admin
              </NavLink>
            )}
          </nav>
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden md:inline opacity-80">{user?.email}</span>
            <button
              onClick={() => {
                logout();
                nav("/login");
              }}
              className="rounded-md px-3 py-1.5 ring-1 ring-white/30 hover:bg-white/10"
            >
              Sign out
            </button>
          </div>
        </div>
        <nav className="md:hidden border-t border-white/15 bg-brand-dark">
          <div className="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-2 py-2 text-xs">
            {navItems.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-md px-3 py-1.5 ${
                    isActive ? "bg-white/15 font-semibold" : "hover:bg-white/10"
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
            {user?.role === "admin" && (
              <NavLink to="/admin" className="whitespace-nowrap rounded-md px-3 py-1.5 hover:bg-white/10">
                Admin
              </NavLink>
            )}
          </div>
        </nav>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
      <footer className="py-6 text-center text-xs text-slate-500">
        Media Monitor v{APP_VERSION} &middot; Daniel Schenz &middot;{" "}
        <a href="mailto:mm@schenz.eu" className="hover:underline">
          mm@schenz.eu
        </a>{" "}
        &middot; {new Date().getFullYear()}
      </footer>
    </div>
  );
}
