import { useEffect } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { useAuth } from "../auth";

export function AppShell() {
  const { t } = useTranslation();
  const { session, logout, setSession } = useAuth();
  const navigate = useNavigate();
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
          {role !== "auditor" ? <NavLink to="/submit">{t("nav.submit")}</NavLink> : null}
          <NavLink to="/audit">{t("nav.audit")}</NavLink>
          {role === "supervisor" ? <NavLink to="/policy">{t("nav.policy")}</NavLink> : null}
          {role === "supervisor" ? <NavLink to="/webhooks">{t("nav.webhooks")}</NavLink> : null}
          {role === "supervisor" ? <NavLink to="/dead-letters">{t("nav.dead")}</NavLink> : null}
        </nav>
        {session ? (
          <div className="mailbox-card">
            <div className="muted small">{t("nav.signedInAs")}</div>
            <div className="mailbox-email" title={session.email}>
              {session.email}
            </div>
            <label className="field">
              <span className="muted small">{t("nav.role")}</span>
              <select value={role} onChange={(event) => void onRole(event.target.value as typeof role)}>
                <option value="supervisor">{t("roles.supervisor")}</option>
                <option value="reviewer">{t("roles.reviewer")}</option>
                <option value="auditor">{t("roles.auditor")}</option>
              </select>
            </label>
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
