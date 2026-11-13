import { useEffect, useState } from "react";
import { api, CAMPUS_LABEL, dateTime } from "../api";
import type { Source } from "../types";

const STATUS: Record<string, string> = { ok: "bg-sticky", unchanged: "bg-page", error: "bg-orange" };

// The watcher proof: per-source status, row counts, "Run now" and "Run all".
export default function SourcesPage({ onAlerts }: { onAlerts: (n: number) => void }) {
  const [rows, setRows] = useState<Source[]>([]);
  const [busy, setBusy] = useState<string>("");
  const load = () => api.sources().then(setRows).catch(() => {});
  useEffect(() => { load(); }, []);

  const run = async (id: string) => {
    setBusy(id);
    try { const r = await api.runSource(id); onAlerts(r.alerts_created); } finally { setBusy(""); load(); }
  };
  const runAll = async () => {
    setBusy("*");
    try { const r = await api.runAll(); onAlerts(r.alerts_created); } finally { setBusy(""); load(); }
  };
  const enabled = rows.filter((r) => r.enabled);
  const total = enabled.reduce((s, r) => s + r.row_count, 0);

  return (
    <main className="mx-auto max-w-[1240px] px-8 pt-9 pb-16 flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="wide font-black m-0 leading-[0.95]" style={{ fontSize: "clamp(40px, 6vw, 80px)" }}>SOURCES</h1>
          <p className="m-0 mt-2 text-[17px]">Only these official GSU pages feed Pathfinder. {total} verified rows from {enabled.filter((r) => r.last_status && r.last_status !== "error").length} of {enabled.length} sources.</p>
        </div>
        <button onClick={runAll} disabled={!!busy} className="btn-ink h-14 px-7 wide-110 text-[17px]">{busy === "*" ? "Running all…" : "Run all"}</button>
      </div>

      <div className="card !rounded-[24px] overflow-x-auto">
        <table className="w-full min-w-[980px] border-collapse text-sm">
          <thead>
            <tr className="text-left border-b-2.5 border-ink">
              {["Source", "Kind", "Campus", "Last run", "Last changed", "Status", "New / changed / dropped", "Rows", ""].map((h) => <th key={h} className="px-4 py-3 font-display font-extrabold">{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.id} className={`border-b border-dashed border-ink align-top ${s.enabled ? "" : "opacity-50"}`}>
                <td className="px-4 py-3">
                  <div className="font-semibold">{s.id}</div>
                  <a href={s.url} target="_blank" rel="noreferrer" className="text-xs break-all text-muted">{s.url}</a>
                  {s.last_status === "error" && s.last_error && <div className="text-xs text-danger mt-1">{s.last_error}</div>}
                </td>
                <td className="px-4 py-3">{s.kind}</td>
                <td className="px-4 py-3">{CAMPUS_LABEL[s.campus] || s.campus}</td>
                <td className="px-4 py-3 whitespace-nowrap">{dateTime(s.last_run_at) || "never"}</td>
                <td className="px-4 py-3 whitespace-nowrap">{dateTime(s.last_changed_at) || "—"}</td>
                <td className="px-4 py-3"><span className={`inline-block rounded-full border-2 border-ink px-2.5 py-0.5 text-xs font-bold ${STATUS[s.last_status || ""] || "bg-cream"}`}>{s.enabled ? s.last_status || "not run" : "disabled"}</span></td>
                <td className="px-4 py-3 tabular-nums">{s.last_run ? `${s.last_run.rows_new} / ${s.last_run.rows_changed} / ${s.last_run.rows_dropped}` : "—"}</td>
                <td className="px-4 py-3 tabular-nums font-semibold">{s.row_count}</td>
                <td className="px-4 py-3">{s.enabled ? <button onClick={() => run(s.id)} disabled={!!busy} className="btn-orange h-9 px-4 text-[13px] whitespace-nowrap">{busy === s.id ? "Running…" : "Run now"}</button> : null}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="m-0 text-sm">Ingestion fetches each page (1 request/second, gsu.edu only), extracts rows with Gemini, keeps a row only if its evidence quote appears word-for-word on the page, and diffs content hashes. The watcher then turns new or changed rows that fit your profile into alerts.</p>
    </main>
  );
}
