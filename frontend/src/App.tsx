import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { AuthError, NotFoundError, approveRun, createRun, getRun, rejectRun, streamRun } from "./api";
import type { Run, RunEvent } from "./api";
import { clearToken, loadToken, renderSignIn, saveToken } from "./auth";

const LAST_RUN_KEY = "cca-last-run";
const WORKING = ["running", "applying"];

function describe(e: RunEvent): ReactNode {
  switch (e.type) {
    case "route":
      return `Routed as: ${e.intent}`;
    case "proposal":
      return (
        <>
          <strong>Writer</strong> proposed round {e.round}: {e.summary}
          <ul>{e.files?.map((f) => <li key={f}><code>{f}</code></li>)}</ul>
        </>
      );
    case "review":
      return (
        <>
          <strong>Reviewer</strong> round {e.round}: {e.approved ? "approved" : "requested changes"}
          <pre>{e.text}</pre>
        </>
      );
    case "answer":
      return <pre>{e.text}</pre>;
    case "awaiting_approval":
      return "Waiting for your approval";
    case "pr":
      return <a href={e.url}>Pull request opened</a>;
    case "rejected":
      return "Proposal rejected";
    case "error":
      return <span className="error">{e.text}</span>;
    default:
      return e.type;
  }
}

export default function App() {
  const [token, setToken] = useState<string | null>(loadToken);
  const [input, setInput] = useState("");
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);
  const signInRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const working = run !== null && WORKING.includes(run.status);

  function fail(err: unknown) {
    if (err instanceof AuthError) {
      clearToken();
      setToken(null);
    }
    if (err instanceof NotFoundError) {
      // The saved run is gone; forget it so the page stops asking for it.
      localStorage.removeItem(LAST_RUN_KEY);
      setRun(null);
      setError("That run is no longer available. Start a new one.");
      return;
    }
    setError(err instanceof Error ? err.message : String(err));
  }

  // Streams a run's events into the UI, then reloads the run for its final state.
  async function attach(t: string, id: string) {
    abortRef.current?.abort();
    const ctl = new AbortController();
    abortRef.current = ctl;
    setRun((prev) => (prev?.id === id ? { ...prev, events: [] } : prev));
    try {
      await streamRun(t, id, (e) => setRun((prev) => (prev?.id === id ? { ...prev, events: [...prev.events, e] } : prev)), ctl.signal);
      setRun(await getRun(t, id));
    } catch (err) {
      if (!ctl.signal.aborted) fail(err);
    }
  }

  // Resume the last run when the page is reopened, e.g. from a phone.
  useEffect(() => {
    if (!token) return;
    const id = localStorage.getItem(LAST_RUN_KEY);
    if (!id) return;
    getRun(token, id)
      .then((r) => {
        setRun(r);
        if (WORKING.includes(r.status)) attach(token, id);
      })
      .catch(fail);
    return () => abortRef.current?.abort();
  }, [token]);

  useEffect(() => {
    if (token || !signInRef.current) return;
    renderSignIn(signInRef.current, (t) => {
      saveToken(t);
      setToken(t);
    });
  }, [token]);

  if (!token) {
    return (
      <main className="center">
        <h1>cloud-code-agent</h1>
        <div ref={signInRef} />
        {error && <p className="error">{error}</p>}
      </main>
    );
  }

  async function send() {
    const message = input.trim();
    if (!message || working) return;
    setError(null);
    try {
      const id = await createRun(token!, message);
      localStorage.setItem(LAST_RUN_KEY, id);
      setInput("");
      setRun({ id, message, status: "running", events: [], proposal: null, pr_url: null, stats: { llm_calls: 0, input_tokens: 0, output_tokens: 0, tool_calls: 0 }, duration_s: 0 });
      attach(token!, id);
    } catch (err) {
      fail(err);
    }
  }

  async function approve() {
    if (!run) return;
    setError(null);
    try {
      await approveRun(token!, run.id);
      setRun({ ...run, status: "applying" });
      attach(token!, run.id);
    } catch (err) {
      fail(err);
    }
  }

  async function reject() {
    if (!run) return;
    try {
      await rejectRun(token!, run.id);
      setRun(await getRun(token!, run.id));
    } catch (err) {
      fail(err);
    }
  }

  function newRun() {
    abortRef.current?.abort();
    localStorage.removeItem(LAST_RUN_KEY);
    setRun(null);
  }

  return (
    <main>
      <header>
        <h1>cloud-code-agent</h1>
        <button className="link" onClick={() => { clearToken(); setToken(null); }}>Sign out</button>
      </header>

      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a code question, or describe code to write…"
          rows={3}
          disabled={working}
        />
        <div className="row">
          <button type="submit" disabled={working || !input.trim()}>Send</button>
          {run && !working && <button type="button" className="secondary" onClick={newRun}>New run</button>}
        </div>
      </form>

      {error && <p className="error">{error}</p>}

      {run && (
        <section className="run">
          <p className="request"><strong>Request:</strong> {run.message}</p>
          {working && <p className="working">Working…</p>}

          <ol className="timeline">
            {run.events.filter((e) => e.type !== "status").map((e, i) => (
              <li key={i}>
                <span className="time">{e.t.toFixed(1)}s</span> {describe(e)}
              </li>
            ))}
          </ol>

          {run.status === "awaiting_approval" && run.proposal && (
            <div className="approval">
              <h2>Proposed change</h2>
              <p>{run.proposal.summary}</p>
              {run.proposal.files.map((f) => (
                <details key={f.path}>
                  <summary><code>{f.path}</code></summary>
                  <pre>{f.content}</pre>
                </details>
              ))}
              <div className="row">
                <button onClick={approve}>Approve and open PR</button>
                <button className="secondary" onClick={reject}>Reject</button>
              </div>
            </div>
          )}

          {run.pr_url && <p><a href={run.pr_url}>Open pull request</a></p>}

          {!working && run.status !== "running" && (
            <footer className="stats">
              {run.status} · {run.duration_s.toFixed(1)}s · {run.stats.llm_calls} LLM calls ·{" "}
              {run.stats.input_tokens + run.stats.output_tokens} tokens · {run.stats.tool_calls} tool calls
            </footer>
          )}
        </section>
      )}
    </main>
  );
}
