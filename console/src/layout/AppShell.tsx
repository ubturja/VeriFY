import { useEffect } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { useAuth } from "../auth";

export function AppShell() {
  const { t } = useTranslation();
  const { session, logout } = useAuth();
  const navigate = useNavigate();

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
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <strong>{t("app.name")}</strong>
          <span>{t("app.product")}</span>
        </div>
        <nav className="nav">
          <NavLink to="/" end>
            {t("nav.queue")}
          </NavLink>
          <NavLink to="/overview">{t("nav.dashboard")}</NavLink>
          <NavLink to="/submit">{t("nav.submit")}</NavLink>
          <NavLink to="/audit">{t("nav.audit")}</NavLink>
        </nav>
        {session ? (
          <div className="mailbox-card">
            <div className="muted small">{t("nav.signedInAs")}</div>
            <div className="mailbox-email" title={session.email}>
              {session.email}
            </div>
            <button className="btn secondary small" type="button" onClick={() => void onSignOut()}>
              {t("nav.signOut")}
            </button>
          </div>
        ) : null}
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
