import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";

type Row = {
  email_id: string;
  subject: string;
  webhook: { delivered: boolean; error: string | null };
};

export function WebhooksPage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<Row[]>([]);

  useEffect(() => {
    api.webhooks().then(setRows).catch(() => setRows([]));
  }, []);

  return (
    <section>
      <div className="page-head">
        <h1>{t("webhooks.title")}</h1>
        <p>{t("webhooks.subtitle")}</p>
      </div>
      {rows.length === 0 ? (
        <p className="empty">{t("webhooks.empty")}</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>{t("webhooks.case")}</th>
              <th>{t("webhooks.delivered")}</th>
              <th>{t("webhooks.error")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.email_id}>
                <td>
                  {row.subject || row.email_id}
                  <div className="muted">{row.email_id}</div>
                </td>
                <td>{row.webhook?.delivered ? t("webhooks.yes") : t("webhooks.no")}</td>
                <td>{row.webhook?.error || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
