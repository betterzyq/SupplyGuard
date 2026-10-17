"use client";

import { errorLabel } from "@/lib/labels";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { uploadDocument } from "@/lib/api";

export default function DocumentsPage() {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const mutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("请先选择文件");
      const form = new FormData();
      form.append("file", file);
      form.append("title", title || file.name);
      form.append("doc_type", "contract");
      form.append("department", "enterprise");
      form.append("security_level", "internal");
      form.append("access_scope", "role_based");
      form.append("allowed_roles", '["admin","enterprise"]');
      form.append("chunk_size", "512");
      return uploadDocument(form);
    },
  });
  return (
    <div>
      <PageHeader
        title="企业知识库"
        description="集中企业证据，为风险研判与决策助手提供可引用的依据。"
      />
      <SectionCard title="上传企业文档">
        <div className="grid max-w-lg gap-4">
          <p className="rounded-lg bg-brand-50 p-3 text-sm leading-relaxed text-brand-700">
            上传内容在本企业内共享。部门与岗位仅作业务分工，不限制同企业成员查阅；其他企业无法访问。
          </p>
          <p className="text-xs leading-relaxed text-slate-500">
            文档索引需要已配置的 Embedding
            服务；本阶段经营总览使用独立演示数据，不依赖文档上传。
          </p>
          <label htmlFor="document-file" className="text-sm text-slate-600">
            选择文档（TXT、Markdown、PDF）
          </label>
          <input
            id="document-file"
            type="file"
            accept=".txt,.md,.pdf"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="text-sm"
          />
          <label htmlFor="document-title" className="text-sm text-slate-600">
            文档标题
          </label>
          <input
            id="document-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="默认使用文件名"
            className="rounded-lg border border-slate-300 p-2 text-sm"
          />
          <button
            type="button"
            onClick={() => mutation.mutate()}
            disabled={!file || mutation.isPending}
            className="rounded-lg bg-brand-600 py-2 text-sm text-white disabled:opacity-50"
          >
            {mutation.isPending ? "上传并索引中…" : "上传并建立索引"}
          </button>
          {mutation.data && (
            <p
              role="status"
              className="rounded-lg bg-green-50 p-3 text-sm text-green-700"
            >
              文档上传完成，可前往证据检索查看。
            </p>
          )}
          {mutation.error && (
            <p role="alert" className="text-sm text-red-600">
              {errorLabel((mutation.error as Error).message)}
            </p>
          )}
        </div>
      </SectionCard>
    </div>
  );
}
