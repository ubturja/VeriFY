import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";

export function DashboardPage() {
  const { t } = useTranslation();
  const [metrics, setMetrics] = useState<{
    total: number;
    by_status: Record<string, number>;
    confirmed: number;
  } | null>(null);

  useEffect(() => {
    api
      .metrics()
      .then(setMetrics)
      .catch(() => setMetrics({ total: 0, by_status: {}, confirmed: 0 }));
  }, []);

  const by = metrics?.by_status ?? {};
  return (
    <section>
      <div className="page-head">
        <h1>{t("dashboard.title")}</h1>
      </div>
      <div className="cards">
        <article className="card">
          <div className="label">{t("dashboard.total")}</div>
          <div className="value">{metrics?.total ?? 0}</div>
        </article>
        <article className="card">
          <div className="label">{t("dashboard.review")}</div>
          <div className="value">{by.NEEDS_REVIEW ?? 0}</div>
        </article>
        <article className="card">
          <div className="label">{t("dashboard.mismatch")}</div>
          <div className="value">{by.MISMATCH ?? 0}</div>
        </article>
        <article className="card">
          <div className="label">{t("dashboard.clear")}</div>
          <div className="value">{by.OK ?? 0}</div>
        </article>
        <article className="card">
          <div className="label">{t("dashboard.confirmed")}</div>
          <div className="value">{metrics?.confirmed ?? 0}</div>
        </article>
      </div>
    </section>
  );
}
