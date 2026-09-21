export const COMPARE_FIELDS = [
  "shipper",
  "consignee",
  "notify_party",
  "port_of_loading",
  "port_of_discharge",
  "container_count",
  "gross_weight_kg",
] as const;

export type FieldEvidence = {
  attachment: string;
  locator: string;
  snippet?: string;
};

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
      confidence?: number;
      note?: string | null;
      si_evidence?: FieldEvidence | null;
      bl_evidence?: FieldEvidence | null;
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

import { getStoredToken } from "./auth";

const explicit = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "");
const base = explicit || "/api";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init?.headers as Record<string, string>) ?? {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const response = await fetch(`${base}${path}`, { ...init, headers });
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
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("verify:unauthorized"));
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export type MailboxSession = {
  token: string;
  email: string;
};

export type MailboxProfile = {
  email: string;
  role: "supervisor" | "reviewer" | "auditor";
  imap_ready: boolean;
  last_login_at: string | null;
  poll: {
    last_at?: string | null;
    ingested?: number;
    failed?: number;
    error?: string | null;
  };
};

export const api = {
  health: () =>
    request<{
      status: string;
      service: string;
      env: string;
      llm: string;
      mailboxes: number;
      imap_autopoll: boolean;
    }>("/health"),
  login: (body: { email: string; app_password: string }) =>
    request<MailboxSession>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  me: () => request<MailboxProfile>("/auth/me"),
  setRole: (role: "supervisor" | "reviewer" | "auditor") =>
    request<{ email: string; role: MailboxProfile["role"] }>("/auth/role", {
      method: "POST",
      body: JSON.stringify({ role }),
    }),
  policy: () =>
    request<{
      weight_tolerance_kg: number;
      mandatory_fields: string[];
      fields_may_differ: string[];
    }>("/policy"),
  savePolicy: (body: {
    weight_tolerance_kg: number;
    mandatory_fields: string[];
    fields_may_differ: string[];
  }) => request<Record<string, unknown>>("/policy", { method: "PUT", body: JSON.stringify(body) }),
  webhooks: () =>
    request<{ email_id: string; subject: string; webhook: { delivered: boolean; error: string | null } }[]>(
      "/webhooks",
    ),
  deadLetters: () =>
    request<{ id: string; attempts: number; last_error: string | null; body: { email_id: string } }[]>(
      "/queue/dead",
    ),
  retryDeadLetter: (id: string) =>
    request<{ retried: string }>(`/queue/dead/${encodeURIComponent(id)}/retry`, { method: "POST" }),
  cases: (query = "") => request<CaseRow[]>(`/cases${query}`),
  case: (id: string) => request<CaseRow>(`/cases/${encodeURIComponent(id)}`),
  replay: () => request<{ ingested: number }>("/inbox/replay", { method: "POST" }),
  pollMailbox: () =>
    request<{ ingested: number; mailbox: string }>("/inbox/imap", { method: "POST" }),
  submit: (body: Record<string, unknown>) =>
    request<CaseRow>("/inbox/submit", { method: "POST", body: JSON.stringify(body) }),
  confirm: (id: string, body: { note?: string } = {}) =>
    request<CaseRow>(`/cases/${encodeURIComponent(id)}/confirm`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  correct: (
    id: string,
    body: {
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
  replyDraft: (id: string) =>
    request<{ subject: string; body: string; to: string }>(
      `/cases/${encodeURIComponent(id)}/reply-draft`,
    ),
  related: (id: string) =>
    request<{
      shipment_id: string | null;
      matches: { email_id: string; subject: string; status: string; from: string }[];
      timeline: {
        email_id: string;
        subject: string;
        status: string;
        pending_draft?: boolean;
        paired_with?: string | null;
        processed_at?: string;
      }[];
    }>(`/cases/${encodeURIComponent(id)}/related`),
  audit: () => request<AuditEvent[]>("/audit"),
  metrics: () =>
    request<{
      total: number;
      by_status: Record<string, number>;
      by_category: Record<string, number>;
      confirmed: number;
      corrected: number;
      automation_rate: number;
      llm_calls_per_100: number;
      estimated_cost_per_1000_usd: number;
      median_latency_ms: number;
      trend: { day: string; cases: number; automated: number; llm_calls: number }[];
    }>("/metrics"),
};
