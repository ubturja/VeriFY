import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";

export function DashboardPage() {
  const { t } = useTranslation();
  const [metrics, setMetrics] = useState<{
    total: number;
    by_status: Record<string, number>;
    confirmed: number;
    corrected: number;
    automation_rate?: number;
    llm_calls_per_100?: number;
    estimated_cost_per_1000_usd?: number;
    median_latency_ms?: number;
  } | null>(null);

  useEffect(() => {
    api
      .metrics()
      .then(setMetrics)
      .catch(() => setMetrics({ total: 0, by_status: {}, confirmed: 0, corrected: 0 }));
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
        <article className="card">
          <div className="label">{t("dashboard.corrected")}</div>
          <div className="value">{metrics?.corrected ?? 0}</div>
        </article>
        <article className="card">
          <div className="label">{t("dashboard.automation")}</div>
          <div className="value">{Math.round((metrics?.automation_rate ?? 0) * 100)}%</div>
        </article>
        <article className="card">
          <div className="label">{t("dashboard.llmPer100")}</div>
          <div className="value">{metrics?.llm_calls_per_100 ?? 0}</div>
        </article>
        <article className="card">
          <div className="label">{t("dashboard.cost")}</div>
          <div className="value">{metrics?.estimated_cost_per_1000_usd ?? 0}</div>
        </article>
        <article className="card">
          <div className="label">{t("dashboard.latency")}</div>
          <div className="value">{metrics?.median_latency_ms ?? 0}</div>
        </article>
      </div>
    </section>
  );
}
