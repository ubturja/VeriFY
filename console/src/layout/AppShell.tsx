import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";

export function AppShell() {
  const { t } = useTranslation();
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
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
