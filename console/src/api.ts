export const COMPARE_FIELDS = [
  "shipper",
  "consignee",
  "notify_party",
  "port_of_loading",
  "port_of_discharge",
  "container_count",
  "gross_weight_kg",
] as const;

export type ReviewStamp = {
  action: string;
  at: string;
  by: string;
  note: string | null;
  accepted_status?: string;
  accepted_category?: string;
  previous?: {
    category?: string;
    status?: string;
    has_defect?: boolean;
    defect_fields?: string[];
    review_reason?: string | null;
  };
};

export type CaseRow = {
  email_id: string;
  from: string;
  subject: string;
  body: string;
  attachments: { path: string; filename: string }[];
  review: ReviewStamp | null;
  result: {
    category: string;
    status: string;
    review_reason: string | null;
    has_defect: boolean;
    defect_fields: string[];
    decided_by: string;
    comparisons: {
      field: string;
      si_value: string | null;
      bl_value: string | null;
      match: boolean | null;
    }[];
    notes: string[];
  };
};

export type AuditEvent = {
  at: string;
  email_id: string;
  action: string;
  by: string;
  note: string | null;
};

export type SubmitAttachment = {
  path?: string;
  filename?: string;
  content_base64?: string;
};

const explicit = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "");
const base = explicit || "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (typeof payload.detail === "string" && payload.detail) {
        message = payload.detail;
      }
    } catch {
      /* keep status text */
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () =>
    request<{
      status: string;
      llm: string;
      cases: number;
      imap_ready: boolean;
      imap_autopoll: boolean;
    }>("/health"),
  cases: (query = "") => request<CaseRow[]>(`/cases${query}`),
  case: (id: string) => request<CaseRow>(`/cases/${encodeURIComponent(id)}`),
  replay: () => request<{ ingested: number }>("/inbox/replay", { method: "POST" }),
  pollMailbox: () =>
    request<{ ingested: number; mailbox: string }>("/inbox/imap", { method: "POST" }),
  submit: (body: Record<string, unknown>) =>
    request<CaseRow>("/inbox/submit", { method: "POST", body: JSON.stringify(body) }),
  confirm: (id: string, body: { reviewer?: string; note?: string } = {}) =>
    request<CaseRow>(`/cases/${encodeURIComponent(id)}/confirm`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  correct: (
    id: string,
    body: {
      reviewer?: string;
      note?: string;
      category?: string;
      status?: string;
      review_reason?: string;
      defect_fields?: string[];
    },
  ) =>
    request<CaseRow>(`/cases/${encodeURIComponent(id)}/correct`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  retry: (id: string) =>
    request<CaseRow>(`/cases/${encodeURIComponent(id)}/retry`, { method: "POST" }),
  audit: () => request<AuditEvent[]>("/audit"),
  metrics: () =>
    request<{
      total: number;
      by_status: Record<string, number>;
      by_category: Record<string, number>;
      confirmed: number;
      corrected: number;
    }>("/metrics"),
};
