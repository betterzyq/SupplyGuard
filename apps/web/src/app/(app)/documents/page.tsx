"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { SecurityLevelBadge } from "@/components/badges/SecurityLevelBadge";
import { uploadDocument } from "@/lib/api";

export default function DocumentsPage() {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [securityLevel, setSecurityLevel] = useState("internal");
  const [allowedRoles, setAllowedRoles] = useState('["procurement_manager"]');

  const mutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("No file");
      const form = new FormData();
      form.append("file", file);
      form.append("title", title || file.name);
      form.append("doc_type", "contract");
      form.append("department", "procurement");
      form.append("security_level", securityLevel);
      form.append("access_scope", "role_based");
      form.append("allowed_roles", allowedRoles);
      form.append("chunk_size", "512");
      return uploadDocument(form);
    },
  });

  return (
    <div>
      <PageHeader title="Documents" description="Upload documents with security metadata for Secure RAG indexing." />
      <SectionCard title="Upload">
        <div className="grid gap-4 max-w-lg">
          <input type="file" accept=".txt,.md,.pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title" className="rounded border p-2 text-sm" />
          <select value={securityLevel} onChange={(e) => setSecurityLevel(e.target.value)} className="rounded border p-2 text-sm">
            {["public", "internal", "department", "confidential", "executive"].map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
          <SecurityLevelBadge level={securityLevel} />
          <input value={allowedRoles} onChange={(e) => setAllowedRoles(e.target.value)} className="rounded border p-2 text-sm font-mono" placeholder='allowed_roles JSON' />
          <button type="button" onClick={() => mutation.mutate()} disabled={!file || mutation.isPending} className="rounded-lg bg-brand-600 py-2 text-sm text-white disabled:opacity-50">
            Upload & Index
          </button>
          {mutation.data && (
            <pre className="text-xs bg-green-50 p-3 rounded">{JSON.stringify(mutation.data, null, 2)}</pre>
          )}
          {mutation.error && <p className="text-sm text-red-600">{(mutation.error as Error).message}</p>}
        </div>
      </SectionCard>
    </div>
  );
}
