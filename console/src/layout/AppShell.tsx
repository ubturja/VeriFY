import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { useAuth } from "../auth";

interface NavItem {
  id: string;
  label: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: "/",        label: "Home",     icon: "⬡" },
  { id: "/queue",   label: "Queue",    icon: "📨" },
  { id: "/overview",label: "Overview", icon: "📊" },
  { id: "/submit",  label: "Submit",   icon: "📤" },
  { id: "/audit",   label: "Audit",    icon: "📋" },
  { id: "/profile", label: "Profile",  icon: "👤" },
];

function getLabel(_key: string, fallback: string): string {
  return fallback;
}

export function AppShell() {
  const { t } = useTranslation();
  const { session, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const isWelcome = location.pathname === "/";

  useEffect(() => {
    function onUnauthorized() {
      logout();
      navigate("/login", { replace: true });
    }
    window.addEventListener("verify:unauthorized", onUnauthorized as EventListener);
    return () =>
      window.removeEventListener("verify:unauthorized", onUnauthorized as EventListener);
  }, [logout, navigate]);

  async function onSignOut() {
    try {
      await api.logout();
    } catch {
      /* even if the server rejects it, drop the token locally */
    }
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="mesh-bg h-screen w-screen flex overflow-hidden relative text-[#f0ebe9] font-body text-[15px]">
      {/* Background cinematic orb */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full blur-[120px] opacity-[0.12] pointer-events-none"
           style={{ background: 'radial-gradient(circle, #8e3b31, #e5cf80)', animation: 'pulse 10s infinite alternate' }} />

      {sidebarOpen && (
        <div
          className="absolute inset-0 z-20 bg-black/40 backdrop-blur-[2px]"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar Sliding Panel */}
      <div
        className="absolute left-0 top-0 h-full z-30 sidebar-slide flex-shrink-0"
        style={{
          transform: sidebarOpen ? "translateX(0)" : "translateX(-100%)",
          opacity: sidebarOpen ? 1 : 0,
          width: "264px",
        }}
      >
        <div
          className="h-full flex flex-col"
          style={{
            background: "rgba(10,7,6,0.96)",
            backdropFilter: "blur(24px)",
            borderRight: "1px solid rgba(142,59,49,0.25)",
          }}
        >
          <div className="px-6 py-6 border-b border-[rgba(142,59,49,0.2)]">
            <div className="flex items-center gap-3">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center font-bold"
                style={{ background: "linear-gradient(135deg, #8e3b31, #b8963a)", boxShadow: "0 0 16px rgba(142,59,49,0.5)" }}
              >
                <span className="text-sm">⬡</span>
              </div>
              <div>
                <p className="text-sm font-semibold font-display text-[#f0ebe9]">VeriFY AI</p>
                <p className="text-xs font-mono text-[#8a7470]">Scanner Engine</p>
              </div>
            </div>
          </div>

          <nav className="flex-1 py-4 space-y-1 px-3">
            {NAV_ITEMS.map((item) => {
              const active = location.pathname === item.id || (item.id !== "/" && location.pathname.startsWith(item.id));
              return (
                <NavLink
                  key={item.id}
                  to={item.id}
                  onClick={() => setSidebarOpen(false)}
                  className="w-full flex items-center gap-3 px-3 py-3 rounded-lg text-sm transition-all duration-200 text-left"
                  style={
                    active
                      ? {
                          background:
                            "linear-gradient(135deg, rgba(142,59,49,0.35), rgba(229,207,128,0.06))",
                          borderLeft: "2px solid #e5cf80",
                          color: "#e5cf80",
                        }
                      : { color: "#8a7470", borderLeft: "2px solid transparent" }
                  }
                >
                  <span className="text-base w-5 text-center">{item.icon}</span>
                  <span className="font-medium">{getLabel(item.label, item.label)}</span>
                </NavLink>
              );
            })}
          </nav>

          {/* Sign out button */}
          <div className="px-3 py-4 border-t border-[rgba(142,59,49,0.2)]">
            <button
              onClick={() => void onSignOut()}
              className="w-full flex items-center gap-3 px-3 py-3 rounded-lg text-sm transition-all duration-200 text-left cursor-pointer"
              style={{ color: "#8a7470", borderLeft: "2px solid transparent" }}
            >
              <span className="text-base w-5 text-center">🚪</span>
              <span className="font-medium">{t("nav.signOut", "Sign Out")}</span>
            </button>
            {session && (
              <p className="text-xs font-mono text-[#8a7470] px-3 mt-1 truncate">
                {session.email ?? ""}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Circular Floating Toggle Button */}
      {!isWelcome && (
        <button
          onClick={() => setSidebarOpen((s) => !s)}
          className="toggle-btn absolute z-40 w-12 h-12 rounded-full flex items-center justify-center cursor-pointer"
          style={{ left: sidebarOpen ? "276px" : "20px", top: "24px" }}
          aria-label="Toggle navigation"
        >
          <span
            className="text-[#f0ebe9] text-xl transition-transform duration-300"
            style={{
              transform: sidebarOpen ? "rotate(90deg)" : "rotate(0deg)",
              display: "block",
              lineHeight: 1,
            }}
          >
            {sidebarOpen ? "×" : "≡"}
          </span>
        </button>
      )}

      {/* Main content Container */}
      <div className="flex-1 h-full relative overflow-y-auto">
        <main className={`h-full relative z-10 ${isWelcome ? "" : "p-6 md:p-8 pt-20"}`}>
          <Outlet key={location.pathname} />
        </main>
      </div>
    </div>
  );
}
