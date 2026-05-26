import axios, { type AxiosInstance } from "axios";
import { getToken, refreshToken } from "@/lib/auth";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
});

api.interceptors.request.use(async (config) => {
  await refreshToken().catch(() => undefined);
  const token = getToken();
  if (token) {
    config.headers = config.headers ?? {};
    (config.headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (error?.response?.status === 401) {
      // Don't auto-redirect to Keycloak on every 401 — when the backend has
      // a JWT-verification bug this produces an infinite "looks like a
      // refresh" loop that hides the real error. Page-level handlers will
      // surface a toast; the user can manually log in again if needed.
      // eslint-disable-next-line no-console
      console.error(
        "API 401",
        error.config?.method?.toUpperCase(),
        error.config?.url,
        error.response?.data
      );
    }
    return Promise.reject(error);
  }
);

// ── Typed helpers ────────────────────────────────────────────

export interface ChatSource {
  chunk_id: string;
  document_id: string;
  filename: string;
  similarity: number;
  snippet: string;
}

export interface ChatResponse {
  answer: string;
  grounded: boolean;
  sources: ChatSource[];
}

export interface DocumentItem {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  chunk_count: number;
  created_at: string;
}

export type AgentNode =
  | "retrieve"
  | "classify"
  | "generate"
  | "refuse_with_topics";

export type StreamEvent =
  | { type: "node_start"; node: AgentNode; label: string }
  | {
      type: "node_end";
      node: AgentNode;
      meta?: Record<string, unknown>;
    }
  | { type: "token"; value: string }
  | {
      type: "done";
      answer: string;
      grounded: boolean;
      sources: ChatSource[];
    }
  | { type: "error"; message: string };

export const chatApi = {
  ask: async (question: string): Promise<ChatResponse> =>
    (await api.post<ChatResponse>("/chat", { question })).data,
  history: async () => (await api.get("/chat/history")).data,

  /**
   * Stream the agent's answer token by token. Calls `onEvent` for every SSE
   * event the backend emits (`token`, `done`, or `error`). The promise
   * resolves when the stream closes; the caller should rely on the final
   * `done` event for the authoritative answer + grounded flag + sources.
   *
   * EventSource isn't suitable here because it can't send `POST` bodies or
   * `Authorization` headers; we read the body as a stream instead.
   */
  askStream: async (
    question: string,
    onEvent: (event: StreamEvent) => void,
    signal?: AbortSignal,
  ): Promise<void> => {
    await refreshToken().catch(() => undefined);
    const token = getToken();
    const resp = await fetch(`${BASE_URL}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ question }),
      signal,
    });
    if (!resp.ok || !resp.body) {
      throw new Error(`stream failed: HTTP ${resp.status}`);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // SSE events are separated by a blank line.
      let sepIdx: number;
      while ((sepIdx = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, sepIdx);
        buffer = buffer.slice(sepIdx + 2);
        const line = raw.split("\n").find((l) => l.startsWith("data:"));
        if (!line) continue;
        try {
          const payload = JSON.parse(line.slice(5).trim()) as StreamEvent;
          onEvent(payload);
        } catch {
          // ignore malformed line
        }
      }
    }
  },
};

export const documentsApi = {
  list: async (): Promise<DocumentItem[]> =>
    (await api.get<DocumentItem[]>("/documents")).data,
  upload: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return (
      await api.post("/documents", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
    ).data;
  },
  remove: async (id: string) => api.delete(`/documents/${id}`),
};

export const authApi = {
  me: async () => (await api.get("/auth/me")).data,
};
