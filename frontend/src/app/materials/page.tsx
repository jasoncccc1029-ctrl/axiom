"use client";

import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState, ErrorState, LoadingBlock, UploadProgress } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import {
  apiDelete,
  apiGet,
  apiPostJson,
  uploadMaterial,
  type Material,
} from "@/lib/api";

const SUBJECTS = ["高二數學", "英文", "物理"];

export default function MaterialsPage() {
  const { push } = useToast();
  const [items, setItems] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [subject, setSubject] = useState(SUBJECTS[0]);
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await apiGet<Material[]>("/api/materials"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "無法載入");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) {
      push("請輸入標題", "error");
      return;
    }

    try {
      setUploading(true);
      setProgress(0);
      if (file) {
        const form = new FormData();
        form.append("file", file);
        form.append("title", title.trim());
        form.append("subject", subject);
        if (description.trim()) form.append("description", description.trim());
        await uploadMaterial(form, setProgress);
      } else {
        await apiPostJson<Material>("/api/materials", {
          title: title.trim(),
          subject,
          description: description.trim() || null,
        });
        setProgress(100);
      }
      setOpen(false);
      setTitle("");
      setDescription("");
      setFile(null);
      await load();
    } catch (err) {
      push(err instanceof Error ? err.message : "新增失敗", "error");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(id: number) {
    try {
      await apiDelete(`/api/materials/${id}`);
      await load();
    } catch (err) {
      push(err instanceof Error ? err.message : "刪除失敗", "error");
    }
  }

  return (
    <div>
      <PageHeader
        title="教材"
        action={
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="rounded-xl bg-ink-950 px-4 py-2.5 text-sm text-white transition hover:bg-ink-800"
          >
            新增
          </button>
        }
      />

      {loading ? <LoadingBlock rows={4} /> : null}
      {error ? <ErrorState message={error} onRetry={load} /> : null}

      {!loading && !error && items.length === 0 ? (
        <EmptyState
          action={
            <button
              type="button"
              onClick={() => setOpen(true)}
              className="rounded-xl bg-ink-950 px-4 py-2.5 text-sm text-white"
            >
              新增
            </button>
          }
        />
      ) : null}

      {!loading && !error && items.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((item, i) => (
            <article
              key={item.id}
              className="panel flex flex-col p-5 animate-fadeUp"
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs text-accent-700">{item.subject}</p>
                  <h2 className="mt-2 font-display text-xl text-ink-950">{item.title}</h2>
                </div>
                {item.file_type === "pdf" && item.ingestion_status && item.ingestion_status !== "ready" ? (
                  <span className="rounded-lg bg-ink-50 px-2 py-1 text-xs text-ink-500">
                    {item.ingestion_status}
                  </span>
                ) : null}
              </div>
              {item.description ? (
                <p className="mt-3 flex-1 text-sm text-ink-500">{item.description}</p>
              ) : (
                <div className="flex-1" />
              )}
              <div className="mt-5 flex items-center justify-between border-t border-ink-100 pt-4">
                <span className="text-xs text-ink-400">
                  {new Date(item.created_at).toLocaleDateString()}
                </span>
                <button
                  type="button"
                  onClick={() => void handleDelete(item.id)}
                  className="text-sm text-red-600 transition hover:text-red-800"
                >
                  刪除
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : null}

      {open ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink-950/35 p-4 sm:items-center">
          <form
            onSubmit={handleSubmit}
            className="w-full max-w-lg animate-fadeUp rounded-2xl bg-white p-6 shadow-panel"
          >
            <h2 className="font-display text-2xl text-ink-950">新增</h2>

            <div className="mt-5 space-y-4">
              <label className="block text-sm">
                <span className="sr-only">標題</span>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full rounded-xl border border-ink-200 bg-ink-50/40 px-3 py-2.5 outline-none ring-accent-400 focus:ring-2"
                  placeholder="標題"
                />
              </label>
              <label className="block text-sm">
                <span className="sr-only">科目</span>
                <select
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="w-full rounded-xl border border-ink-200 bg-ink-50/40 px-3 py-2.5 outline-none ring-accent-400 focus:ring-2"
                >
                  {SUBJECTS.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                <span className="sr-only">描述</span>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  className="w-full rounded-xl border border-ink-200 bg-ink-50/40 px-3 py-2.5 outline-none ring-accent-400 focus:ring-2"
                  placeholder="描述"
                />
              </label>
              <label className="block text-sm">
                <span className="sr-only">檔案</span>
                <input
                  type="file"
                  accept=".pdf,image/*"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="block w-full text-sm text-ink-600 file:mr-3 file:rounded-lg file:border-0 file:bg-ink-950 file:px-3 file:py-2 file:text-white"
                />
              </label>
              {uploading ? <UploadProgress percent={progress} /> : null}
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-xl px-4 py-2.5 text-sm text-ink-600 hover:bg-ink-50"
                disabled={uploading}
              >
                取消
              </button>
              <button
                type="submit"
                disabled={uploading}
                className="rounded-xl bg-ink-950 px-4 py-2.5 text-sm text-white disabled:opacity-60"
              >
                {uploading ? "…" : "儲存"}
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}
