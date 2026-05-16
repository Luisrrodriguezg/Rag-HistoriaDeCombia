import { useState } from "react";
import { Upload } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { documentsApi } from "@/lib/api";

interface Props {
  onUploaded: () => void;
}

export function UploadDialog({ onUploaded }: Props) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!file) return;
    setBusy(true);
    try {
      const r = await documentsApi.upload(file);
      toast.success(`Documento procesado: ${r.chunk_count} fragmentos indexados.`);
      setOpen(false);
      setFile(null);
      onUploaded();
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        "No se pudo subir el documento.";
      toast.error(message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Upload className="h-4 w-4" />
          Subir documento
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Subir documento</DialogTitle>
          <DialogDescription>
            Formatos aceptados: PDF, TXT, MD, DOCX. El contenido se dividirá en fragmentos
            y se indexará en la base vectorial.
          </DialogDescription>
        </DialogHeader>

        <Input
          type="file"
          accept=".pdf,.txt,.md,.markdown,.docx"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          disabled={busy}
        />

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={() => setOpen(false)} disabled={busy}>
            Cancelar
          </Button>
          <Button onClick={submit} disabled={!file || busy}>
            {busy ? "Procesando…" : "Subir"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
