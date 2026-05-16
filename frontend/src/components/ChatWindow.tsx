import { useEffect, useState } from "react";
import { Send, AlertTriangle, BookOpen, Eraser } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { chatApi, type ChatSource } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Turn {
  question: string;
  answer: string;
  grounded: boolean;
  sources: ChatSource[];
  loading?: boolean;
}

const STORAGE_KEY = "rag-chat-turns";

function loadPersistedTurns(): Turn[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Turn[];
    // Discard any turn that was still loading when we last unmounted — its
    // request will not complete in this component instance, and a permanent
    // "Pensando…" bubble is worse than losing the prompt.
    return parsed.filter((t) => !t.loading);
  } catch {
    return [];
  }
}

export function ChatWindow() {
  const [turns, setTurns] = useState<Turn[]>(loadPersistedTurns);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);

  // Persist on every mutation so navigating to Documentos and back preserves
  // the conversation. Quota errors (extremely unlikely for chat text) are
  // swallowed silently.
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(turns));
    } catch {
      /* quota — ignore */
    }
  }, [turns]);

  function clearChat() {
    if (turns.length === 0 || sending) return;
    if (!confirm("¿Borrar la conversación actual?")) return;
    setTurns([]);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const question = draft.trim();
    if (!question || sending) return;

    setDraft("");
    setSending(true);
    const pending: Turn = { question, answer: "", grounded: false, sources: [], loading: true };
    setTurns((t) => [...t, pending]);

    try {
      const resp = await chatApi.ask(question);
      setTurns((t) =>
        t.map((turn) =>
          turn === pending
            ? {
                question,
                answer: resp.answer,
                grounded: resp.grounded,
                sources: resp.sources,
              }
            : turn
        )
      );
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        "No se pudo obtener respuesta. Intenta de nuevo.";
      toast.error(message);
      setTurns((t) => t.filter((turn) => turn !== pending));
    } finally {
      setSending(false);
    }
  }

  return (
    <Card className="h-[calc(100vh-160px)] flex flex-col">
      <CardContent className="flex-1 overflow-hidden p-0">
        <ScrollArea className="h-full p-4">
          {turns.length === 0 ? (
            <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
              Hazle una pregunta al agente sobre Historia de Colombia.
            </div>
          ) : (
            <div className="space-y-6">
              {turns.map((turn, i) => (
                <ChatTurn key={i} turn={turn} />
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>

      <form onSubmit={onSubmit} className="border-t p-3 flex gap-2 items-center">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={clearChat}
          disabled={sending || turns.length === 0}
          title="Limpiar conversación"
          aria-label="Limpiar conversación"
        >
          <Eraser className="h-4 w-4" />
        </Button>
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ej: ¿Qué fue el Bogotazo?"
          disabled={sending}
        />
        <Button type="submit" disabled={sending || !draft.trim()}>
          <Send className="h-4 w-4" />
          Enviar
        </Button>
      </form>
    </Card>
  );
}

function ChatTurn({ turn }: { turn: Turn }) {
  return (
    <div className="space-y-2">
      <div className="flex justify-end">
        <div className="bg-primary text-primary-foreground rounded-lg px-3 py-2 max-w-[80%] text-sm">
          {turn.question}
        </div>
      </div>

      <div className="flex">
        <div
          className={cn(
            "rounded-lg px-3 py-2 max-w-[85%] text-sm space-y-2",
            turn.grounded ? "bg-secondary" : "bg-muted"
          )}
        >
          {turn.loading ? (
            <span className="text-muted-foreground italic">Pensando…</span>
          ) : (
            <>
              <p className="whitespace-pre-wrap">{turn.answer}</p>

              {!turn.grounded && (
                <Badge variant="destructive" className="gap-1">
                  <AlertTriangle className="h-3 w-3" />
                  Sin información suficiente
                </Badge>
              )}

              {turn.sources.length > 0 && (
                <details className="text-xs text-muted-foreground pt-2 border-t">
                  <summary className="cursor-pointer flex items-center gap-1">
                    <BookOpen className="h-3 w-3" />
                    Fuentes ({turn.sources.length})
                  </summary>
                  <ul className="mt-2 space-y-1.5">
                    {turn.sources.map((s) => (
                      <li key={s.chunk_id} className="border-l-2 pl-2 border-border">
                        <div className="font-medium">{s.filename}</div>
                        <div className="opacity-80 italic">"{s.snippet}…"</div>
                        <div className="text-[10px] opacity-60">
                          similitud: {(s.similarity * 100).toFixed(1)}%
                        </div>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
