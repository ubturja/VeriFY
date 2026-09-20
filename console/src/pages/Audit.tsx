import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, type AuditEvent } from "../api";

export function AuditPage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .audit()
      .then(setRows)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load audit"));
  }, []);

  return (
    <section>
      <div className="page-head">
        <h1>{t("audit.title")}</h1>
        <p>{t("audit.subtitle")}</p>
      </div>
      {error ? <p className="muted">{error}</p> : null}
      {rows.length === 0 ? (
        <div className="empty">{t("audit.empty")}</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>{t("audit.when")}</th>
              <th>{t("audit.case")}</th>
              <th>{t("audit.action")}</th>
              <th>{t("audit.by")}</th>
            </tr>
          </thead>
          <tbody>
            {[...rows].reverse().map((row, index) => (
              <tr key={`${row.at}-${row.email_id}-${index}`}>
                <td>{row.at.replace("T", " ").replace("Z", " UTC")}</td>
                <td>
                  <Link to={`/cases/${encodeURIComponent(row.email_id)}`}>{row.email_id}</Link>
                </td>
                <td>{row.action}</td>
                <td>
                  {row.by}
                  {row.note ? <div className="muted">{row.note}</div> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
