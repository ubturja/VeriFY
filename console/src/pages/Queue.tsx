import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, type CaseRow } from "../api";
import { StatusPill } from "../components/StatusPill";

export function QueuePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [rows, setRows] = useState<CaseRow[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState<"replay" | "poll" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const query = status ? `?status=${status}` : "";
      setRows(await api.cases(query));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load cases");
    }
  }

  useEffect(() => {
    void load();
  }, [status]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((row) =>
      `${row.email_id} ${row.subject} ${row.from}`.toLowerCase().includes(needle),
    );
  }, [rows, q]);

  async function replay() {
    setBusy("replay");
    setError(null);
    try {
      await api.replay();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Replay failed");
    } finally {
      setBusy(null);
    }
  }

  async function pollMailbox() {
    setBusy("poll");
    setError(null);
    try {
      await api.pollMailbox();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Mailbox poll failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section>
      <div className="page-head">
        <h1>{t("queue.title")}</h1>
        <p>{t("queue.subtitle")}</p>
      </div>
      <div className="toolbar">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t("queue.search")}
        />
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">{t("queue.allStatuses")}</option>
          <option value="NEEDS_REVIEW">{t("status.NEEDS_REVIEW")}</option>
          <option value="MISMATCH">{t("status.MISMATCH")}</option>
          <option value="OK">{t("status.OK")}</option>
        </select>
        <button className="btn" onClick={() => void replay()} disabled={busy !== null}>
          {busy === "replay" ? t("queue.replaying") : t("queue.replay")}
        </button>
        <button className="btn secondary" onClick={() => void pollMailbox()} disabled={busy !== null}>
          {busy === "poll" ? t("queue.polling") : t("queue.poll")}
        </button>
      </div>
      {error ? <p className="muted">{error}</p> : null}
      {filtered.length === 0 ? (
        <div className="empty">{t("queue.empty")}</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Id</th>
              <th>Subject</th>
              <th>Category</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <tr key={row.email_id} onClick={() => navigate(`/cases/${row.email_id}`)}>
                <td>{row.email_id}</td>
                <td>
                  {row.subject}
                  <div className="muted">{row.from}</div>
                </td>
                <td>{t(`category.${row.result.category}`)}</td>
                <td>
                  <StatusPill status={row.result.status} />
                  {row.review?.action === "confirm" ? (
                    <span className="pill confirmed" style={{ marginLeft: 8 }}>
                      {t("queue.confirmed")}
                    </span>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
