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

export const chatApi = {
  ask: async (question: string): Promise<ChatResponse> =>
    (await api.post<ChatResponse>("/chat", { question })).data,
  history: async () => (await api.get("/chat/history")).data,
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
