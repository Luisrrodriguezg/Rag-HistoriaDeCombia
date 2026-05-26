import { useEffect, useState } from "react";
import {
  Send,
  AlertTriangle,
  BookOpen,
  Eraser,
  Loader2,
  CheckCircle2,
  Search,
  Brain,
  PenLine,
  Lightbulb,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { chatApi, type AgentNode, type ChatSource } from "@/lib/api";
import { cn } from "@/lib/utils";

interface NodeStep {
  node: AgentNode;
  label: string;
  status: "running" | "done";
  meta?: Record<string, unknown>;
}

interface Turn {
  id: string;
  question: string;
  answer: string;
  grounded: boolean;
  sources: ChatSource[];
  loading?: boolean;
  steps?: NodeStep[];
}

const STORAGE_KEY = "rag-chat-turns";

const NODE_ICON: Record<AgentNode, typeof Search> = {
  retrieve: Search,
  classify: Brain,
  generate: PenLine,
  refuse_with_topics: Lightbulb,
};

function loadPersistedTurns(): Turn[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Turn[];
    // Backfill ids for turns persisted before this field existed.
    return parsed
      .filter((t) => !t.loading)
      .map((t) => ({ ...t, id: t.id ?? newId() }));
  } catch {
    return [];
  }
}

function newId(): string {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}-${Math.random().toString(36).slice(2)}`
  );
}

export function ChatWindow() {
  const [turns, setTurns] = useState<Turn[]>(loadPersistedTurns);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);

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
    const pendingId = newId();
    const draftTurn: Turn = {
      id: pendingId,
      question,
      answer: "",
      grounded: false,
      sources: [],
      loading: true,
      steps: [],
    };
    setTurns((t) => [...t, { ...draftTurn }]);

    // Stable id lookup: previous implementation used reference equality
    // (`turn === pending`), which broke after the first `setTurns` replaced
    // the array entry — subsequent stream events couldn't find the turn to
    // update, leaving the UI stuck on "Pensando…".
    const flush = () => {
      setTurns((t) =>
        t.map((turn) => (turn.id === pendingId ? { ...draftTurn } : turn)),
      );
    };

    try {
      await chatApi.askStream(question, (event) => {
        if (event.type === "node_start") {
          draftTurn.steps = [
            ...(draftTurn.steps ?? []),
            { node: event.node, label: event.label, status: "running" },
          ];
          flush();
        } else if (event.type === "node_end") {
          draftTurn.steps = (draftTurn.steps ?? []).map((s) =>
            s.node === event.node && s.status === "running"
              ? { ...s, status: "done", meta: event.meta }
              : s,
          );
          flush();
        } else if (event.type === "token") {
          draftTurn.answer = (draftTurn.answer ?? "") + event.value;
          draftTurn.loading = false;
          flush();
        } else if (event.type === "done") {
          draftTurn.answer = event.answer;
          draftTurn.grounded = event.grounded;
          draftTurn.sources = event.sources;
          draftTurn.loading = false;
          flush();
        } else if (event.type === "error") {
          throw new Error(event.message);
        }
      });
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        (err as Error)?.message ??
        "No se pudo obtener respuesta. Intenta de nuevo.";
      toast.error(message);
      setTurns((t) => t.filter((turn) => turn.id !== pendingId));
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
              {turns.map((turn) => (
                <ChatTurn key={turn.id} turn={turn} />
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
  const showTrace = (turn.steps?.length ?? 0) > 0;
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
            turn.grounded ? "bg-secondary" : "bg-muted",
          )}
        >
          {showTrace && <AgentTrace steps={turn.steps!} />}

          {turn.loading && !turn.answer ? (
            <span className="text-muted-foreground italic">Pensando…</span>
          ) : (
            <>
              {turn.answer && (
                <p className="whitespace-pre-wrap">{turn.answer}</p>
              )}

              {!turn.loading && !turn.grounded && (
                <Badge variant="destructive" className="gap-1">
                  <AlertTriangle className="h-3 w-3" />
                  Sin información suficiente
                </Badge>
              )}

              {!turn.loading && turn.sources.length > 0 && (
                <details className="text-xs text-muted-foreground pt-2 border-t">
                  <summary className="cursor-pointer flex items-center gap-1">
                    <BookOpen className="h-3 w-3" />
                    Fuentes ({turn.sources.length})
                  </summary>
                  <ul className="mt-2 space-y-1.5">
                    {turn.sources.map((s) => (
                      <li
                        key={s.chunk_id}
                        className="border-l-2 pl-2 border-border"
                      >
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

function AgentTrace({ steps }: { steps: NodeStep[] }) {
  const allDone = steps.every((s) => s.status === "done");
  return (
    <details
      className="text-xs text-muted-foreground border-b pb-2 mb-1"
      open={!allDone}
    >
      <summary className="cursor-pointer flex items-center gap-1 select-none">
        <Brain className="h-3 w-3" />
        Proceso del agente ({steps.length})
      </summary>
      <ol className="mt-2 space-y-1">
        {steps.map((step, idx) => {
          const Icon = NODE_ICON[step.node];
          return (
            <li key={idx} className="flex items-start gap-2">
              <span className="mt-0.5">
                {step.status === "running" ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                )}
              </span>
              <span className="flex items-center gap-1 min-w-0">
                <Icon className="h-3 w-3 opacity-70" />
                <span>{step.label}</span>
                {step.status === "done" && step.meta && (
                  <span className="opacity-60 ml-1 truncate">
                    {formatMeta(step.node, step.meta)}
                  </span>
                )}
              </span>
            </li>
          );
        })}
      </ol>
    </details>
  );
}

function formatMeta(node: AgentNode, meta: Record<string, unknown>): string {
  if (node === "retrieve") {
    const kept = meta.kept as number | undefined;
    const total = meta.candidates as number | undefined;
    const top = meta.top_similarity as number | undefined;
    if (kept !== undefined && total !== undefined) {
      const sim = top !== undefined ? ` · top ${(top * 100).toFixed(0)}%` : "";
      return `· ${kept}/${total} chunks${sim}`;
    }
  }
  if (node === "classify") {
    const rel = meta.is_relevant as boolean | undefined;
    if (rel !== undefined) return `· ${rel ? "relevante" : "no relevante"}`;
  }
  if (node === "generate") {
    const chars = meta.chars as number | undefined;
    if (chars !== undefined) return `· ${chars} chars`;
  }
  return "";
}
