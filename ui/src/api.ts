// Typed client for the FastAPI copilot. Paths are relative so the Vite proxy (dev) or
// the same origin (Docker) serves them.

export interface AskResult {
  intents: string[];
  answer_parts: string[];
  citations: string[];
  warnings: string[];
  missing_inputs: string[];
  escalated: boolean;
  draft_id: string | null;
  safety_flags: string[];
}

export interface Customer {
  customer_id: string;
  city: string;
  renewal_date: string;
  synthetic_segment: string;
  consent_status: string;
  fictional_plan_id: string | null;
  policy_renewal_date: string | null;
}

export interface Draft {
  draft_id: string;
  customer_id: string;
  template_id: string;
  text: string;
  citations: string[];
  status: "pending_approval" | "approved" | "simulated_sent";
  approved_by: string | null;
  simulated_sent_at: string | null;
}

export interface AuditEvent {
  ts: string;
  event: string;
  [key: string]: unknown;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof body.detail === "string" ? body.detail : `Request failed (${res.status})`;
    throw new Error(detail);
  }
  return body as T;
}

export const api = {
  ask: (message: string, customer_id?: string) =>
    request<AskResult>("/ask", {
      method: "POST",
      body: JSON.stringify({ message, customer_id: customer_id || null }),
    }),
  customer: (id: string) => request<Customer>(`/customers/${id}`),
  draft: (id: string) => request<Draft>(`/drafts/${id}`),
  approve: (id: string, agent_id: string) =>
    request<Draft>(`/drafts/${id}/approve`, { method: "POST", body: JSON.stringify({ agent_id }) }),
  send: (id: string, agent_id: string) =>
    request<Draft>(`/drafts/${id}/send`, { method: "POST", body: JSON.stringify({ agent_id }) }),
  audit: () => request<AuditEvent[]>("/audit"),
};
