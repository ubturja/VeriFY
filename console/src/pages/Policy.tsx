import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { COMPARE_FIELDS, api } from "../api";

export function PolicyPage() {
  const { t } = useTranslation();
  const [tolerance, setTolerance] = useState(0);
  const [mandatory, setMandatory] = useState<string[]>([...COMPARE_FIELDS]);
  const [mayDiffer, setMayDiffer] = useState<string[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .policy()
      .then((policy) => {
        setTolerance(policy.weight_tolerance_kg);
        setMandatory(policy.mandatory_fields);
        setMayDiffer(policy.fields_may_differ);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Unable to load policy");
      });
  }, []);

  function toggle(list: string[], field: string, set: (next: string[]) => void) {
    set(list.includes(field) ? list.filter((item) => item !== field) : [...list, field]);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    try {
      await api.savePolicy({
        weight_tolerance_kg: tolerance,
        mandatory_fields: mandatory,
        fields_may_differ: mayDiffer,
      });
      setMessage(t("policy.saved"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  }

  return (
    <section>
      <div className="page-head">
        <h1>{t("policy.title")}</h1>
        <p>{t("policy.subtitle")}</p>
      </div>
      <form className="correct-panel" onSubmit={(event) => void onSubmit(event)}>
        <label className="field">
          <span>{t("policy.tolerance")}</span>
          <input
            type="number"
            min={0}
            value={tolerance}
            onChange={(event) => setTolerance(Number(event.target.value))}
          />
        </label>
        <fieldset className="defect-fields">
          <legend>{t("policy.mandatory")}</legend>
          {COMPARE_FIELDS.map((field) => (
            <label key={field}>
              <input
                type="checkbox"
                checked={mandatory.includes(field)}
                onChange={() => toggle(mandatory, field, setMandatory)}
              />
              {field.replaceAll("_", " ")}
            </label>
          ))}
        </fieldset>
        <fieldset className="defect-fields">
          <legend>{t("policy.mayDiffer")}</legend>
          {COMPARE_FIELDS.map((field) => (
            <label key={field}>
              <input
                type="checkbox"
                checked={mayDiffer.includes(field)}
                onChange={() => toggle(mayDiffer, field, setMayDiffer)}
              />
              {field.replaceAll("_", " ")}
            </label>
          ))}
        </fieldset>
        <button className="btn" type="submit">
          {t("policy.save")}
        </button>
        {error ? <p className="form-error">{error}</p> : null}
        {message ? <p className="muted">{message}</p> : null}
      </form>
    </section>
  );
}
