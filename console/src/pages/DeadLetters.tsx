import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";

type Job = {
  id: string;
  attempts: number;
  last_error: string | null;
  body: { email_id: string };
};

export function DeadLettersPage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api.deadLetters().then(setRows).catch((err: unknown) => {
      setError(err instanceof Error ? err.message : "Failed");
    });
  }

  useEffect(() => {
    load();
  }, []);

  async function retry(id: string) {
    setError(null);
    try {
      await api.retryDeadLetter(id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Retry failed");
    }
  }

  return (
    <section>
      <div className="page-head">
        <h1>{t("dead.title")}</h1>
        <p>{t("dead.subtitle")}</p>
      </div>
      {error ? <p className="muted">{error}</p> : null}
      {rows.length === 0 ? (
        <div className="empty">{t("dead.empty")}</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>{t("dead.case")}</th>
              <th>{t("dead.attempts")}</th>
              <th>{t("dead.error")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.body.email_id}</td>
                <td>{row.attempts}</td>
                <td>{row.last_error}</td>
                <td>
                  <button className="btn secondary small" type="button" onClick={() => void retry(row.id)}>
                    {t("dead.retry")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
