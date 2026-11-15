// Conversation en flux avec le coach (SSE émis par /api/ai/chat).

export interface ChatMsg { role: "user" | "assistant"; content: string }

export interface ChatOpts {
  messages: ChatMsg[];
  vocal?: boolean;
  images?: boolean;
  seance?: string;          // séance guidée : étape en cours, plan ou débrief (JSON texte)
  signal?: AbortSignal;
  onText?: (full: string) => void;
}

/** Envoie la conversation et renvoie la réponse complète ; lève une erreur lisible en cas d'échec. */
export async function streamChat(o: ChatOpts): Promise<string> {
  const res = await fetch("/api/ai/chat", {
    method: "POST", headers: { "Content-Type": "application/json" }, signal: o.signal,
    body: JSON.stringify({ messages: o.messages, vocal: !!o.vocal, images: !!o.images, seance: o.seance }),
  });
  if (!res.ok || !res.body) throw new Error((await res.json().catch(() => ({}))).detail ?? `${res.status}`);
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "", answer = "", failed = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() ?? "";
    for (const part of parts) {
      if (!part.startsWith("data: ")) continue;
      const ev = JSON.parse(part.slice(6));
      if (ev.t) { answer += ev.t; o.onText?.(answer); } else if (ev.erreur) failed = ev.erreur;
    }
  }
  if (failed) throw new Error(failed);
  return answer;
}
