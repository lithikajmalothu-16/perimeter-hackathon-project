import { useEffect, useState } from "react";
import { api } from "../api";
import type { DraftEmail } from "../types";

export default function EmailDraftModal({ resourceId, onClose }: { resourceId: string; onClose: () => void }) {
  const [d, setD] = useState<DraftEmail | null>(null);
  const [err, setErr] = useState("");
  const [copied, setCopied] = useState(false);
  useEffect(() => { api.draftEmail(resourceId).then(setD).catch((e) => setErr(String(e))); }, [resourceId]);
  const copy = async () => { if (!d) return; await navigator.clipboard.writeText(`Subject: ${d.subject}\n\n${d.body}`); setCopied(true); setTimeout(() => setCopied(false), 1800); };
  const mailto = d?.to ? `mailto:${d.to}?subject=${encodeURIComponent(d.subject)}&body=${encodeURIComponent(d.body)}` : null;

  return (
    <div role="dialog" aria-modal="true" aria-label="Draft email" className="fixed inset-0 z-50 bg-ink/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="card shadow-hardlg w-full max-w-xl p-6 flex flex-col gap-3" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 className="wide font-black text-2xl m-0">DRAFT EMAIL</h2>
          <button onClick={onClose} aria-label="Close" className="text-2xl font-bold leading-none">×</button>
        </div>
        {err && <span className="text-sm text-danger">{err}</span>}
        {!d && !err && <span className="text-sm">Writing it from your profile…</span>}
        {d && (<>
          <label className="text-sm font-semibold">To</label>
          <div className="text-[15px]">{d.to || <>No email listed. {d.contact_url ? <a href={d.contact_url} target="_blank" rel="noreferrer" className="font-semibold underline">Use the contact page ↗</a> : "Use the office's contact page."}</>}</div>
          <label htmlFor="subj" className="text-sm font-semibold">Subject</label>
          <input id="subj" value={d.subject} onChange={(e) => setD({ ...d, subject: e.target.value })} className="h-12 rounded-[14px] border-2.5 border-ink bg-white px-4 text-[16px]" />
          <label htmlFor="body" className="text-sm font-semibold">Message</label>
          <textarea id="body" value={d.body} onChange={(e) => setD({ ...d, body: e.target.value })} rows={10} className="rounded-[14px] border-2.5 border-ink bg-white px-4 py-3 text-[15px] leading-relaxed" />
          <div className="flex flex-wrap gap-2 justify-end">
            <button onClick={copy} className="btn-ghost h-11 px-5">{copied ? "Copied!" : "Copy"}</button>
            {mailto && <a href={mailto} className="btn-ink h-11 px-5 inline-flex items-center no-underline !text-cream">Open in email</a>}
          </div>
        </>)}
      </div>
    </div>
  );
}
