import { FormEvent, useEffect, useState } from 'react';
import { api, getAdminToken } from '../lib/api';

type DocumentItem = {
  id: number;
  filename: string;
  file_type: string;
  status: string;
  chunk_count: number;
};

export default function UploadPage() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadDocuments() {
    const { data } = await api.get<DocumentItem[]>('/documents');
    setDocs(data);
  }

  useEffect(() => {
    loadDocuments().catch(console.error);
  }, []);

  async function onUpload(e: FormEvent) {
    e.preventDefault();
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setBusy(true);
    try {
      await api.post('/documents/upload', formData, {
        headers: {
          Authorization: `Bearer ${getAdminToken()}`,
        },
      });
      setFile(null);
      await loadDocuments();
    } finally {
      setBusy(false);
    }
  }

  async function removeDoc(id: number) {
    await api.delete(`/documents/${id}`, {
      headers: { Authorization: `Bearer ${getAdminToken()}` },
    });
    await loadDocuments();
  }

  async function reindexDoc(id: number) {
    await api.post(`/documents/${id}/reindex`, null, {
      headers: { Authorization: `Bearer ${getAdminToken()}` },
    });
    await loadDocuments();
  }

  return (
    <div className="grid gap-4 md:grid-cols-[360px_1fr]">
      <section className="rounded-2xl bg-white/70 p-4 shadow-sm">
        <h2 className="mb-3 font-serif text-xl font-bold">Upload Tai Lieu</h2>
        <form onSubmit={onUpload} className="space-y-3">
          <input
            type="file"
            accept=".pdf,.docx,.txt,.json"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="w-full rounded-xl border border-ink/20 bg-white p-3 text-sm"
          />
          <button
            disabled={!file || busy}
            className="w-full rounded-xl bg-ember px-4 py-3 text-sm font-semibold text-white disabled:opacity-50"
          >
            {busy ? 'Dang xu ly...' : 'Tai len va Index'}
          </button>
        </form>
        <p className="mt-3 text-xs text-ink/70">Can token admin. Hay dang nhap trong trang Admin truoc.</p>
      </section>

      <section className="rounded-2xl bg-white/70 p-4 shadow-sm">
        <h3 className="mb-3 font-semibold">Danh sach tai lieu</h3>
        <div className="space-y-2">
          {docs.map((doc) => (
            <div key={doc.id} className="rounded-xl bg-surf p-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-medium">{doc.filename}</p>
                  <p className="text-xs text-ink/70">
                    {doc.file_type.toUpperCase()} | {doc.status} | {doc.chunk_count} chunks
                  </p>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => reindexDoc(doc.id)} className="rounded-lg bg-mint px-3 py-1 text-xs text-white">
                    Reindex
                  </button>
                  <button onClick={() => removeDoc(doc.id)} className="rounded-lg bg-coral px-3 py-1 text-xs text-white">
                    Xoa
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
