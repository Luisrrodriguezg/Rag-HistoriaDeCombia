import { Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { documentsApi, type DocumentItem } from "@/lib/api";

interface Props {
  items: DocumentItem[];
  onChange: () => void;
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function DocumentList({ items, onChange }: Props) {
  async function remove(id: string, filename: string) {
    if (!confirm(`¿Eliminar "${filename}" y todos sus fragmentos?`)) return;
    try {
      await documentsApi.remove(id);
      toast.success("Documento eliminado.");
      onChange();
    } catch {
      toast.error("No se pudo eliminar el documento.");
    }
  }

  if (items.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          Aún no hay documentos. Sube uno para empezar.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-0">
        <table className="w-full text-sm">
          <thead className="text-left text-muted-foreground border-b">
            <tr>
              <th className="p-3">Archivo</th>
              <th className="p-3">Tamaño</th>
              <th className="p-3">Fragmentos</th>
              <th className="p-3">Subido</th>
              <th className="p-3 text-right"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((d) => (
              <tr key={d.id} className="border-b last:border-b-0">
                <td className="p-3 font-medium">{d.filename}</td>
                <td className="p-3">{formatBytes(d.size_bytes)}</td>
                <td className="p-3">
                  <Badge variant="secondary">{d.chunk_count}</Badge>
                </td>
                <td className="p-3 text-muted-foreground">
                  {new Date(d.created_at).toLocaleString()}
                </td>
                <td className="p-3 text-right">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => remove(d.id, d.filename)}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
