import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { useAuth } from "../auth";

interface NavItem {
  id: string;
  label: string;
  icon: string;
  roles?: Array<"supervisor" | "reviewer" | "auditor">;
}

const NAV_ITEMS: NavItem[] = [
  { id: "/queue", label: "nav.queue", icon: "📨" },
  { id: "/overview", label: "nav.dashboard", icon: "📊" },
  { id: "/submit", label: "nav.submit", icon: "📤", roles: ["supervisor", "reviewer"] },
  { id: "/audit", label: "nav.audit", icon: "📋" },
  { id: "/policy", label: "nav.policy", icon: "⚖", roles: ["supervisor"] },
  { id: "/webhooks", label: "nav.webhooks", icon: "↗", roles: ["supervisor"] },
  { id: "/dead-letters", label: "nav.dead", icon: "!", roles: ["supervisor"] },
  { id: "/profile", label: "Profile", icon: "👤" },
];

export function AppShell() {
  const { t } = useTranslation();
  const { session, logout, setSession } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const isWelcome = location.pathname === "/";
  const role = session?.role ?? "supervisor";

  useEffect(() => {
    function onUnauthorized() {
      logout();
      navigate("/login", { replace: true });
    }
    window.addEventListener("verify:unauthorized", onUnauthorized as EventListener);
    return () =>
      window.removeEventListener("verify:unauthorized", onUnauthorized as EventListener);
  }, [logout, navigate]);

  useEffect(() => {
    if (!session) return;
    api
      .me()
      .then((profile) => {
        if (profile.role !== session.role) {
          setSession({ ...session, role: profile.role });
        }
      })
      .catch(() => undefined);
  }, [session, setSession]);

  async function onRole(next: "supervisor" | "reviewer" | "auditor") {
    try {
      const updated = await api.setRole(next);
      if (session) setSession({ ...session, email: updated.email, role: updated.role });
    } catch {
      /* keep the current role if the server rejects the switch */
    }
  }

  async function onSignOut() {
    try {
      await api.logout();
    } catch {
      /* even if the server rejects it, drop the token locally */
    }
    logout();
    navigate("/login", { replace: true });
  }

  const visibleItems = NAV_ITEMS.filter((item) => !item.roles || item.roles.includes(role));

  return (
    <div className="mesh-bg h-screen w-screen flex overflow-hidden relative text-[#f0ebe9] font-body text-[15px]">
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full blur-[120px] opacity-[0.12] pointer-events-none"
        style={{
          background: "radial-gradient(circle, #8e3b31, #e5cf80)",
          animation: "pulse 10s infinite alternate",
        }}
      />

      {sidebarOpen ? (
        <div
          className="absolute inset-0 z-20 bg-black/40 backdrop-blur-[2px]"
          onClick={() => setSidebarOpen(false)}
        />
      ) : null}

      <div
        className="absolute left-0 top-0 h-full z-30 sidebar-slide flex-shrink-0"
        inert={!sidebarOpen}
        aria-hidden={!sidebarOpen}
        style={{
          transform: sidebarOpen ? "translateX(0)" : "translateX(-100%)",
          opacity: sidebarOpen ? 1 : 0,
          pointerEvents: sidebarOpen ? "auto" : "none",
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
                style={{
                  background: "linear-gradient(135deg, #8e3b31, #b8963a)",
                  boxShadow: "0 0 16px rgba(142,59,49,0.5)",
                }}
              >
                <span className="text-sm">⬡</span>
              </div>
              <div>
                <p className="text-sm font-semibold font-display text-[#f0ebe9]">{t("app.name")}</p>
                <p className="text-xs font-mono text-[#8a7470]">{t("app.product")}</p>
              </div>
            </div>
          </div>

          <nav className="flex-1 py-4 space-y-1 px-3 overflow-y-auto">
            {visibleItems.map((item) => {
              const active =
                location.pathname === item.id ||
                (item.id !== "/" && location.pathname.startsWith(item.id));
              return (
                <NavLink
                  key={item.id}
                  to={item.id}
                  end={item.id === "/"}
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
                  <span className="font-medium">
                    {item.label.startsWith("nav.") ? t(item.label) : item.label}
                  </span>
                </NavLink>
              );
            })}
          </nav>

          <div className="px-3 py-4 border-t border-[rgba(142,59,49,0.2)] space-y-3">
            {session ? (
              <label className="block px-3">
                <span className="block text-xs font-mono uppercase tracking-wide text-[#8a7470] mb-1">
                  {t("nav.role")}
                </span>
                <select
                  value={role}
                  onChange={(event) => void onRole(event.target.value as typeof role)}
                  className="w-full rounded-lg px-2 py-2 text-sm"
                  style={{
                    background: "rgba(240,235,233,0.06)",
                    color: "#f0ebe9",
                    border: "1px solid rgba(142,59,49,0.35)",
                  }}
                >
                  <option value="supervisor">{t("roles.supervisor")}</option>
                  <option value="reviewer">{t("roles.reviewer")}</option>
                  <option value="auditor">{t("roles.auditor")}</option>
                </select>
              </label>
            ) : null}
            <button
              type="button"
              onClick={() => void onSignOut()}
              className="w-full flex items-center gap-3 px-3 py-3 rounded-lg text-sm transition-all duration-200 text-left cursor-pointer"
              style={{ color: "#8a7470", borderLeft: "2px solid transparent" }}
            >
              <span className="text-base w-5 text-center">↩</span>
              <span className="font-medium">{t("nav.signOut")}</span>
            </button>
            {session ? (
              <p className="text-xs font-mono text-[#8a7470] px-3 truncate" title={session.email}>
                {session.email}
              </p>
            ) : null}
          </div>
        </div>
      </div>

      <div className="flex-1 h-full min-w-0 relative overflow-y-auto">
        {!isWelcome ? (
          <div
            className="sticky top-0 z-40 flex h-16 items-center"
            style={{
              paddingLeft: sidebarOpen ? 280 : 20,
              background: "linear-gradient(to bottom, rgba(13,10,9,0.92) 55%, transparent)",
            }}
          >
            <button
              type="button"
              onClick={() => setSidebarOpen((open) => !open)}
              className="toggle-btn w-12 h-12 rounded-full flex items-center justify-center cursor-pointer"
              aria-label="Toggle navigation"
              aria-expanded={sidebarOpen}
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
          </div>
        ) : null}
        <main className={`relative z-10 ${isWelcome ? "h-full" : "px-6 md:px-8 pb-10"}`}>
          <Outlet key={location.pathname} />
        </main>
      </div>
    </div>
  );
}
