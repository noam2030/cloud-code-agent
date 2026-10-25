const API_URL = import.meta.env.VITE_API_URL;

export type RunEvent = {
  type: string;
  t: number;
  text?: string;
  intent?: string;
  round?: number;
  summary?: string;
  files?: string[];
  approved?: boolean;
  url?: string;
};

export type Proposal = { summary: string; files: { path: string; content: string }[] };

export type Stats = { llm_calls: number; input_tokens: number; output_tokens: number; tool_calls: number };

export type Run = {
  id: string;
  message: string;
  status: string;
  events: RunEvent[];
  proposal: Proposal | null;
  pr_url: string | null;
  stats: Stats;
  duration_s: number;
};

export class AuthError extends Error {}
export class NotFoundError extends Error {}

async function request(path: string, token: string, init: { method?: string; body?: string; signal?: AbortSignal } = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
  });
  if (res.status === 401 || res.status === 403) throw new AuthError(await res.text());
  if (res.status === 404) throw new NotFoundError(await res.text());
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res;
}

export async function createRun(token: string, message: string): Promise<string> {
  const res = await request("/runs", token, { method: "POST", body: JSON.stringify({ message }) });
  return (await res.json()).id;
}

export async function getRun(token: string, id: string): Promise<Run> {
  return (await request(`/runs/${id}`, token)).json();
}

export async function approveRun(token: string, id: string): Promise<void> {
  await request(`/runs/${id}/approve`, token, { method: "POST" });
}

export async function rejectRun(token: string, id: string): Promise<void> {
  await request(`/runs/${id}/reject`, token, { method: "POST" });
}

// Streams the run's events from the beginning until the server ends the stream.
export async function streamRun(token: string, id: string, onEvent: (e: RunEvent) => void, signal: AbortSignal) {
  const res = await request(`/runs/${id}/events`, token, { signal });
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let end: number;
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      if (block.startsWith("event: end")) return;
      const line = block.split("\n").find((l) => l.startsWith("data: "));
      if (line) onEvent(JSON.parse(line.slice("data: ".length)));
    }
  }
}
