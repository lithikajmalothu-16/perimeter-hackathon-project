import { useState } from "react";
import type { ChatResponse } from "../types";

// Collapsible "how I got this" panel under each answer: plan, searches, refetch, verification, timings.
export default function TracePanel({ trace, verification }: Pick<ChatResponse, "trace" | "verification">) {
  const [open, setOpen] = useState(false);
  const total = trace.reduce((s, t) => s + t.ms, 0);
  return (
    <div className="self-start w-full max-w-[85%]">
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open} className="text-xs font-semibold underline decoration-dashed underline-offset-4">
        {open ? "Hide" : "Show"} how I found this · {trace.length} steps · {(total / 1000).toFixed(1)}s
      </button>
      {open && (
        <ol className="mt-2 rounded-2xl border-2 border-dashed border-ink bg-cream px-4 py-3 flex flex-col gap-1.5">
          {trace.map((t, i) => (
            <li key={i} className="text-xs leading-snug flex gap-2">
              <span className="font-display font-extrabold uppercase w-[86px] shrink-0">{t.step}</span>
              <span className="flex-1">{t.detail}</span>
              <span className="text-muted tabular-nums">{t.ms}ms</span>
            </li>
          ))}
          <li className="text-xs leading-snug flex gap-2 border-t border-dashed border-ink pt-1.5 mt-0.5">
            <span className="font-display font-extrabold uppercase w-[86px] shrink-0">grounded</span>
            <span className="flex-1">checked by {verification.checker}{verification.removed_sentences.length ? ` · removed: “${verification.removed_sentences.join("” “")}”` : " · every sentence supported"}</span>
          </li>
        </ol>
      )}
    </div>
  );
}
