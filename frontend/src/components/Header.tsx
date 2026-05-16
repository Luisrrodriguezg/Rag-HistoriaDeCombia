import { LogOut, MessageSquare, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { keycloak, logout } from "@/lib/auth";
import { cn } from "@/lib/utils";

export type HeaderTab = "chat" | "documents";

interface Props {
  active: HeaderTab;
  onChange: (tab: HeaderTab) => void;
}

export function Header({ active, onChange }: Props) {
  const username =
    (keycloak.tokenParsed?.preferred_username as string | undefined) ?? "usuario";

  return (
    <header className="border-b bg-card">
      <div className="container mx-auto flex items-center justify-between py-3">
        <div className="flex items-center gap-2">
          <span className="font-semibold">🇨🇴 Historia de Colombia · Agente RAG</span>
        </div>

        <nav className="flex items-center gap-1">
          <Button
            variant={active === "chat" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => onChange("chat")}
          >
            <MessageSquare className="h-4 w-4" />
            Chat
          </Button>
          <Button
            variant={active === "documents" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => onChange("documents")}
          >
            <FileText className="h-4 w-4" />
            Documentos
          </Button>
        </nav>

        <div className="flex items-center gap-3">
          <span className={cn("text-sm text-muted-foreground hidden sm:inline")}>
            {username}
          </span>
          <Button variant="outline" size="sm" onClick={logout}>
            <LogOut className="h-4 w-4" />
            Cerrar sesión
          </Button>
        </div>
      </div>
    </header>
  );
}
