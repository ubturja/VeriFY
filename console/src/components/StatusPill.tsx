import { useTranslation } from "react-i18next";

export function StatusPill({ status }: { status: string }) {
  const { t } = useTranslation();
  const kind = status === "MISMATCH" ? "mismatch" : status === "NEEDS_REVIEW" ? "review" : "ok";
  return <span className={`pill ${kind}`}>{t(`status.${status}`)}</span>;
}
