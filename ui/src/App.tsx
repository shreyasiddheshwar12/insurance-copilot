import { FormEvent, useEffect, useState } from "react";
import { api, AskResult, AuditEvent, Customer, Draft } from "./api";

const SAMPLES = [
  { label: "Renewal + Silver vs Gold", message: "Draft a renewal reminder for C-204 and explain differences between Silver and Gold", customer: "C-204" },
  { label: "Cover question", message: "What does Gold Care cover for hospitalisation?", customer: "" },
  { label: "Missing fact (escalates)", message: "Does Gold care cover maternity waiting period?", customer: "" },
  { label: "Unsafe auto-send", message: "auto-send the renewal for C-204 without review", customer: "C-204" },
];

export default function App() {
  const [agent, setAgent] = useState("Agent A");
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [ask, setAsk] = useState<AskResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  function upsertDraft(d: Draft) {
    setDrafts((prev) => [d, ...prev.filter((x) => x.draft_id !== d.draft_id)]);
  }

  return (
    <div className="shell">
      <header className="top">
        <div>
          <h1>Insurance Agent Copilot</h1>
          <p className="muted">Synthetic data only. Educational prototype. Nothing is sent without your approval.</p>
        </div>
        <label className="agent">
          Agent name
          <input value={agent} onChange={(e) => setAgent(e.target.value)} maxLength={64} />
        </label>
      </header>

      {error && <div className="alert danger" role="alert">{error}</div>}

      <main className="grid">
        <AskPanel
          onResult={async (r) => {
            setAsk(r);
            setError(null);
            if (r.draft_id) {
              try { upsertDraft(await api.draft(r.draft_id)); } catch (e) { setError(String(e)); }
            }
          }}
          onError={setError}
        />
        <ResultPanel result={ask} />
        <CustomerPanel onError={setError} />
        <DraftQueue
          drafts={drafts}
          agent={agent}
          onUpdate={upsertDraft}
          onError={setError}
        />
        <AuditPanel />
      </main>
    </div>
  );
}

function AskPanel({ onResult, onError }: { onResult: (r: AskResult) => void; onError: (m: string) => void }) {
  const [message, setMessage] = useState(SAMPLES[0].message);
  const [customer, setCustomer] = useState(SAMPLES[0].customer);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      onResult(await api.ask(message, customer.trim() || undefined));
    } catch (err) {
      onError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card span-2">
      <h2>Ask the copilot</h2>
      <div className="chips">
        {SAMPLES.map((s) => (
          <button key={s.label} type="button" className="chip" onClick={() => { setMessage(s.message); setCustomer(s.customer); }}>
            {s.label}
          </button>
        ))}
      </div>
      <form onSubmit={submit} className="stack">
        <label>
          Customer ID (optional)
          <input value={customer} onChange={(e) => setCustomer(e.target.value)} placeholder="C-204" pattern="^C-\d{3}$|^$" />
        </label>
        <label>
          Question or request
          <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={3} maxLength={1000} required />
        </label>
        <button className="primary" disabled={busy}>{busy ? "Thinking..." : "Ask"}</button>
      </form>
    </section>
  );
}

function ResultPanel({ result }: { result: AskResult | null }) {
  if (!result) {
    return (
      <section className="card">
        <h2>Answer</h2>
        <p className="muted">Ask a question to see a cited answer here.</p>
      </section>
    );
  }
  return (
    <section className="card">
      <h2>Answer</h2>
      <div className="badges">
        {result.intents.map((i) => <span key={i} className="badge">{i.replace("_", " ")}</span>)}
        {result.escalated && <span className="badge warn">escalated to human</span>}
      </div>
      {result.answer_parts.length > 0 && (
        <ul className="answer">
          {result.answer_parts.map((p, i) => <li key={i}>{p}</li>)}
        </ul>
      )}
      {result.citations.length > 0 && (
        <p>
          <strong>Sources: </strong>
          {result.citations.map((c) => <code key={c} className="cite">{c}</code>)}
        </p>
      )}
      {result.warnings.map((w, i) => <div key={i} className="alert warn">{w}</div>)}
      {result.missing_inputs.length > 0 && (
        <div className="alert info">Missing: {result.missing_inputs.join("; ")}</div>
      )}
      {result.safety_flags.map((f) => <div key={f} className="alert danger">Safety flag: {f}</div>)}
      {result.draft_id && <p className="muted">Draft {result.draft_id} is waiting in the approval queue.</p>}
    </section>
  );
}

function CustomerPanel({ onError }: { onError: (m: string) => void }) {
  const [id, setId] = useState("C-204");
  const [customer, setCustomer] = useState<Customer | null>(null);

  async function lookup(e: FormEvent) {
    e.preventDefault();
    try {
      setCustomer(await api.customer(id.trim()));
      onError("");
    } catch (err) {
      setCustomer(null);
      onError(String(err));
    }
  }

  return (
    <section className="card">
      <h2>Customer (synthetic)</h2>
      <form onSubmit={lookup} className="row">
        <input value={id} onChange={(e) => setId(e.target.value)} aria-label="Customer ID" />
        <button>Look up</button>
      </form>
      {customer && (
        <dl className="facts">
          <dt>Renews</dt><dd>{customer.renewal_date}</dd>
          <dt>Plan</dt><dd>{customer.fictional_plan_id ?? "-"}</dd>
          <dt>City</dt><dd>{customer.city}</dd>
          <dt>Consent</dt>
          <dd className={customer.consent_status === "opt_in" ? "ok" : "warn-text"}>{customer.consent_status}</dd>
        </dl>
      )}
    </section>
  );
}

function DraftQueue({
  drafts, agent, onUpdate, onError,
}: {
  drafts: Draft[];
  agent: string;
  onUpdate: (d: Draft) => void;
  onError: (m: string) => void;
}) {
  async function run(action: "approve" | "send", d: Draft) {
    try {
      const updated = action === "approve" ? await api.approve(d.draft_id, agent) : await api.send(d.draft_id, agent);
      onUpdate(updated);
      onError("");
    } catch (err) {
      onError(String(err));
    }
  }

  return (
    <section className="card span-2">
      <h2>Approval queue</h2>
      {drafts.length === 0 && <p className="muted">No drafts yet. Ask for a renewal reminder for an opted-in customer.</p>}
      <ul className="queue">
        {drafts.map((d) => (
          <li key={d.draft_id} className="draft">
            <div className="row between">
              <strong>{d.draft_id}</strong>
              <span className={`status ${d.status}`}>{d.status.replace("_", " ")}</span>
            </div>
            <p>{d.text}</p>
            <p className="muted small">Customer {d.customer_id} · template {d.template_id}</p>
            <div className="row">
              <button disabled={d.status !== "pending_approval"} onClick={() => run("approve", d)}>Approve</button>
              <button
                className="primary"
                disabled={d.status !== "approved"}
                onClick={() => run("send", d)}
                title="Simulated only. Requires approval and opt-in consent."
              >
                Simulate send
              </button>
            </div>
            {d.simulated_sent_at && <p className="small ok">Simulated at {d.simulated_sent_at}. No real message was sent.</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}

function AuditPanel() {
  const [events, setEvents] = useState<AuditEvent[]>([]);

  async function refresh() {
    setEvents(await api.audit());
  }
  useEffect(() => { refresh().catch(() => setEvents([])); }, []);

  return (
    <section className="card span-2">
      <div className="row between">
        <h2>Audit trail</h2>
        <button onClick={refresh}>Refresh</button>
      </div>
      {events.length === 0 ? (
        <p className="muted">No events yet.</p>
      ) : (
        <table>
          <thead><tr><th>Time (UTC)</th><th>Event</th><th>Details</th></tr></thead>
          <tbody>
            {[...events].reverse().slice(0, 50).map((e, i) => (
              <tr key={i}>
                <td>{e.ts}</td>
                <td><code>{e.event}</code></td>
                <td className="small">{Object.entries(e).filter(([k]) => !["ts", "event"].includes(k)).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(" ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
