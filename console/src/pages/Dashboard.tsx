import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";

type Health = {
  status: string;
  llm: string;
  mailboxes: number;
  imap_autopoll: boolean;
};

export function DashboardPage() {
  const { t } = useTranslation();
  const [metrics, setMetrics] = useState<{
    total: number;
    by_status: Record<string, number>;
    by_category?: Record<string, number>;
    confirmed: number;
    corrected: number;
    automation_rate?: number;
    llm_calls_per_100?: number;
    estimated_cost_per_1000_usd?: number;
    median_latency_ms?: number;
  } | null>(null);
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    api
      .metrics()
      .then(setMetrics)
      .catch(() =>
        setMetrics({
          total: 0,
          by_status: {},
          by_category: {},
          confirmed: 0,
          corrected: 0,
        }),
      );
    api
      .health()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  const by = metrics?.by_status ?? {};
  
  const total = metrics?.total ?? 0;
  const review = by.NEEDS_REVIEW ?? 0;
  const mismatch = by.MISMATCH ?? 0;
  const confirmed = metrics?.confirmed ?? 0;

  return (
    <div className="section-blur-enter h-full overflow-y-auto space-y-6">
      <div>
        <p className="font-mono text-xs tracking-[0.25em] text-[#8a7470] uppercase mb-1">
          {t("dashboard.subtitle", "Dashboard")}
        </p>
        <h2 className="text-3xl font-display text-[#f0ebe9]">{t("dashboard.title")}</h2>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        {[
          { label: t("dashboard.total", "Total"), value: total, sub: "All time processed", pct: total ? 100 : 0 },
          { label: t("dashboard.review", "Needs Review"), value: review, sub: "Pending manual check", pct: total ? (review / total) * 100 : 0 },
          { label: t("dashboard.mismatch", "Mismatch"), value: mismatch, sub: "Errors found", pct: total ? (mismatch / total) * 100 : 0 },
          { label: t("dashboard.confirmed", "Confirmed"), value: confirmed, sub: "Verified safe", pct: total ? (confirmed / total) * 100 : 0 },
        ].map((s) => (
          <div
            key={s.label}
            className="card-glass rounded-xl p-5 space-y-3"
          >
            <p className="text-xs font-mono text-[#8a7470] tracking-wide uppercase">{s.label}</p>
            <p className="text-4xl font-semibold font-display text-[#e5cf80]">
              {s.value}
            </p>
            <div className="h-1 rounded-full bg-[#251c1a] overflow-hidden">
              <div
                className="h-full progress-bar-fill"
                style={{ width: `${s.pct}%` }}
              />
            </div>
            <p className="text-xs text-[#8a7470]">{s.sub}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
        {[
          { label: t("dashboard.clear"), value: String(by.OK ?? 0) },
          { label: t("dashboard.corrected"), value: String(metrics?.corrected ?? 0) },
          { label: t("dashboard.automation"), value: `${Math.round((metrics?.automation_rate ?? 0) * 100)}%` },
          { label: t("dashboard.llmPer100"), value: String(metrics?.llm_calls_per_100 ?? 0) },
          { label: t("dashboard.cost"), value: String(metrics?.estimated_cost_per_1000_usd ?? 0) },
          { label: t("dashboard.latency"), value: String(metrics?.median_latency_ms ?? 0) },
        ].map((item) => (
          <div key={item.label} className="card-glass rounded-xl p-5 space-y-2">
            <p className="text-xs font-mono text-[#8a7470] tracking-wide uppercase">{item.label}</p>
            <p className="text-3xl font-semibold font-display text-[#f0ebe9]">{item.value}</p>
          </div>
        ))}
      </div>

      <div className="card-glass rounded-xl p-6 space-y-4">
        <p className="text-xs font-mono text-[#8a7470] uppercase tracking-wide">Service</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-xs text-[#8a7470] font-mono mb-1">Status</p>
            <p className="text-sm font-semibold text-[#7ecfa0]">{health?.status ?? "unknown"}</p>
          </div>
          <div>
            <p className="text-xs text-[#8a7470] font-mono mb-1">Model</p>
            <p className="text-sm font-semibold text-[#e5cf80]">{health?.llm ?? "rules"}</p>
          </div>
          <div>
            <p className="text-xs text-[#8a7470] font-mono mb-1">Mailboxes</p>
            <p className="text-sm font-semibold text-[#f0ebe9]">{health?.mailboxes ?? 0}</p>
          </div>
          <div>
            <p className="text-xs text-[#8a7470] font-mono mb-1">Mailbox poll</p>
            <p className="text-sm font-semibold text-[#f0ebe9]">{health?.imap_autopoll ? "On" : "Off"}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
