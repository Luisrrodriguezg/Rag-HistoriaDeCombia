import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { Header } from "@/components/Header";
import { LoginPage } from "@/pages/LoginPage";
import { ChatPage } from "@/pages/ChatPage";
import { DocumentsPage } from "@/pages/DocumentsPage";

type Tab = "chat" | "documents";

function AppShell() {
  const [tab, setTab] = useState<Tab>("chat");
  return (
    <div className="min-h-screen flex flex-col">
      <Header active={tab} onChange={setTab} />
      <main className="flex-1 container mx-auto py-6">
        {tab === "chat" ? <ChatPage /> : <DocumentsPage />}
      </main>
    </div>
  );
}

export default function App() {
  const auth = useAuth();

  if (!auth.ready) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        Cargando…
      </div>
    );
  }
  if (!auth.authenticated) {
    return <LoginPage />;
  }
  return <AppShell />;
}
