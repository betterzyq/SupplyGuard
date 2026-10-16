"use client";

import { errorLabel, securityLevelLabel } from "@/lib/labels";
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
      if (!file) throw new Error("请先选择文件");
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
      <PageHeader title="文档管理" description="上传文档并设置访问权限，建立 Secure RAG 索引。" />
      <SectionCard title="上传文档">
        <div className="grid gap-4 max-w-lg">
          <div className="flex items-center gap-3 text-sm">
            <label htmlFor="document-file" className="cursor-pointer rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-700 hover:bg-slate-50">
              选择文档
            </label>
            <input id="document-file" type="file" accept=".txt,.md,.pdf" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] || null)} />
            <span className="truncate text-slate-500">{file?.name || "未选择文件（支持 TXT、Markdown、PDF）"}</span>
          </div>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="文档标题" className="rounded border p-2 text-sm" />
          <select value={securityLevel} onChange={(e) => setSecurityLevel(e.target.value)} className="rounded border p-2 text-sm">
            {["public", "internal", "department", "confidential", "executive"].map((l) => (
              <option key={l} value={l}>{securityLevelLabel(l)}</option>
            ))}
          </select>
          <SecurityLevelBadge level={securityLevel} />
          <input value={allowedRoles} onChange={(e) => setAllowedRoles(e.target.value)} className="rounded border p-2 text-sm font-mono" placeholder='允许访问的角色（JSON 数组）' />
          <button type="button" onClick={() => mutation.mutate()} disabled={!file || mutation.isPending} className="rounded-lg bg-brand-600 py-2 text-sm text-white disabled:opacity-50">
            {mutation.isPending ? "上传并索引中…" : "上传并建立索引"}
          </button>
          {mutation.data && (
            <pre className="text-xs bg-green-50 p-3 rounded">{JSON.stringify(mutation.data, null, 2)}</pre>
          )}
          {mutation.error && <p className="text-sm text-red-600">{errorLabel((mutation.error as Error).message)}</p>}
        </div>
      </SectionCard>
    </div>
  );
}
