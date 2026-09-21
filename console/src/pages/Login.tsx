import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { useAuth } from "../auth";

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { setSession } = useAuth();
  const [email, setEmail] = useState("");
  const [appPassword, setAppPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const session = await api.login({ email: email.trim(), app_password: appPassword });
      setSession(session);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-shell">
      <section className="login-card">
        <div className="brand" style={{ marginBottom: 20 }}>
          <strong>{t("app.name")}</strong>
          <span>{t("app.product")}</span>
        </div>
        <h1>{t("login.title")}</h1>
        <p className="muted">{t("login.subtitle")}</p>
        <form className="stack" onSubmit={(e) => void onSubmit(e)} style={{ marginTop: 20 }}>
          <label className="field">
            <span>{t("login.email")}</span>
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />
          </label>
          <label className="field">
            <span>{t("login.appPassword")}</span>
            <input
              type="password"
              autoComplete="current-password"
              value={appPassword}
              onChange={(e) => setAppPassword(e.target.value)}
              placeholder={t("login.appPasswordHint")}
              required
            />
          </label>
          {error ? <p className="muted login-error">{error}</p> : null}
          <div>
            <button className="btn" type="submit" disabled={busy}>
              {busy ? t("login.signingIn") : t("login.submit")}
            </button>
          </div>
          <p className="muted small">
            {t("login.help.gmailPrefix")}{" "}
            <a
              href="https://myaccount.google.com/apppasswords"
              target="_blank"
              rel="noreferrer"
              className="link"
            >
              {t("login.help.gmailLink")}
            </a>{" "}
            {t("login.help.gmailSuffix")}
          </p>
        </form>
      </section>
    </div>
  );
}
