import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { DocumentList } from "@/components/DocumentList";
import { UploadDialog } from "@/components/UploadDialog";
import { documentsApi, type DocumentItem } from "@/lib/api";

export function DocumentsPage() {
  const [items, setItems] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setItems(await documentsApi.list());
    } catch {
      toast.error("No se pudieron cargar los documentos.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Documentos</h1>
        <UploadDialog onUploaded={refresh} />
      </div>

      {loading ? (
        <div className="text-sm text-muted-foreground">Cargando…</div>
      ) : (
        <DocumentList items={items} onChange={refresh} />
      )}
    </div>
  );
}
