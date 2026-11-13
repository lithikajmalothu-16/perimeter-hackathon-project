import { useEffect, useState } from "react";
import { api, shortDate } from "../api";
import type { ChatRoadmap, Profile, Roadmap } from "../types";

// Pathway from pathways.yaml. Each step links to its source row(s). Tap a step to check it off (+10, last step +50).
export default function RoadmapPage({ profile }: { profile: Profile | null }) {
  const [rm, setRm] = useState<Roadmap | null>(null);
  const [err, setErr] = useState("");
  const [mine, setMine] = useState<ChatRoadmap[]>([]);
  const [doneC, setDoneC] = useState<Record<string, boolean>>(() => { try { return JSON.parse(localStorage.getItem("pf_done_chat") || "{}"); } catch { return {}; } });
  useEffect(() => { api.roadmaps().then(setMine).catch(() => {}); }, []);
  useEffect(() => { try { localStorage.setItem("pf_done_chat", JSON.stringify(doneC)); } catch { /* private mode */ } }, [doneC]);
  const remove = async (id: number) => { await api.deleteRoadmap(id); setMine((m) => m.filter((x) => x.id !== id)); };
  const [done, setDone] = useState<Record<number, boolean>>(() => { try { return JSON.parse(localStorage.getItem("pf_done") || "{}"); } catch { return {}; } });
  useEffect(() => {
    if (!profile) return;
    if (!profile.pathway_id) { setRm(null); setErr(`No roadmap for ${profile.major || "your major"} yet. Pathways are added in pathways.yaml; ask in Chat meanwhile.`); return; }
    setErr(""); api.roadmap(profile.pathway_id).then(setRm).catch((e) => setErr(String(e.message || e)));
  }, [profile?.pathway_id, profile]);
  useEffect(() => { try { localStorage.setItem("pf_done", JSON.stringify(done)); } catch { /* private mode */ } }, [done]);

  const first = (profile?.name || "Your").split(" ")[0];
  const n = rm?.steps.length || 0;
  const chatPts = mine.reduce((s, r) => s + r.steps.reduce((a, _, i) => a + (doneC[`${r.id}:${i}`] ? (i === r.steps.length - 1 ? 50 : 10) : 0), 0), 0);
  const pts = (rm ? rm.steps.reduce((s, _, i) => s + (done[i] ? (i === n - 1 ? 50 : 10) : 0), 0) : 0) + chatPts;
  const count = Object.values(done).filter(Boolean).length + Object.values(doneC).filter(Boolean).length;
  const totalSteps = n + mine.reduce((s, r) => s + r.steps.length, 0);

  return (
    <div className="bg-orange border-t-2.5 border-ink mt-6 min-h-[calc(100vh-90px)]">
      <main className="mx-auto max-w-[1240px] px-8 pt-10 pb-16 flex flex-col gap-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="wide font-black m-0 leading-[0.95] text-cream" style={{ fontSize: "clamp(40px, 6vw, 80px)" }}>{first.toUpperCase()}&apos;S ROADMAPS</h1>
            {rm && <p className="m-0 mt-2 text-[17px] font-semibold">{rm.pathway.name}: {rm.pathway.start} → {rm.pathway.destination}</p>}
          </div>
          <span className="text-sm border-2 border-dashed border-ink rounded-full px-4 py-2 bg-cream">Every step links to the GSU page it came from</span>
        </div>
        <div className="flex flex-wrap gap-6 items-start">
          <div className="flex-[999_1_620px] min-w-0 flex flex-col gap-6">
          {mine.length === 0 && <div className="card p-5 text-[16px]">Ask something in Chat, then tap <b>Make this my roadmap</b> under the answer (or ask "make me a roadmap to …"). Your roadmaps land here.</div>}
          {mine.map((r, ri) => {
            const dc = r.steps.filter((_, i) => doneC[`${r.id}:${i}`]).length;
            return (
              <section key={r.id} className={`card p-6 flex flex-col ${ri % 2 ? "bg-sticky" : ""}`} style={{ transform: `rotate(${ri % 2 ? 0.4 : -0.4}deg)` }}>
                <div className="flex items-start justify-between gap-3 mb-1">
                  <div>
                    <span className="wide font-black text-2xl leading-none block">{r.title.toUpperCase()}</span>
                    <span className="text-sm text-muted">From your chat: “{r.goal}”</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[13px] font-bold bg-ink text-cream rounded-full px-3 py-1">{dc} of {r.steps.length}</span>
                    <button onClick={() => remove(r.id)} aria-label="Delete roadmap" className="text-lg font-bold leading-none px-1">×</button>
                  </div>
                </div>
                <div className="mt-3 flex flex-col">
                  {r.steps.map((s, i) => {
                    const k = `${r.id}:${i}`, d = !!doneC[k], last = i === r.steps.length - 1;
                    return (
                      <div key={k} className="flex flex-col">
                        <div className={`rounded-[14px] px-3 py-2.5 border-2 ${d ? "border-solid border-ink bg-page" : "border-dashed border-dash"}`}>
                          <button onClick={() => setDoneC({ ...doneC, [k]: !d })} aria-pressed={d} className="w-full flex items-center gap-3 text-left">
                            <span className={`h-[34px] w-[34px] shrink-0 rounded-full border-2.5 border-ink flex items-center justify-center font-display font-extrabold text-sm ${d ? "bg-ink text-cream" : "bg-orange text-ink"}`}>{d ? "✓" : i + 1}</span>
                            <span className="flex-1 flex flex-col"><span className="text-[15px] font-semibold leading-snug">{s.title}</span><span className="text-xs text-muted">{s.when}</span></span>
                            <span className="text-xs font-bold">+{last ? 50 : 10}</span>
                          </button>
                          {s.resource && (
                            <div className="ml-[46px] mt-2 flex flex-wrap gap-2">
                              <a href={s.resource.source_url} target="_blank" rel="noreferrer" title={s.resource.evidence}
                                className="no-underline text-xs font-semibold border-2 border-ink rounded-full px-2.5 py-1 bg-page">{s.resource.name}{s.resource.fetched_at ? ` · verified ${shortDate(s.resource.fetched_at)}` : ""} ↗</a>
                            </div>
                          )}
                        </div>
                        {!last && <div className="h-3 ml-[30px] border-l-2.5 border-dashed border-ink" />}
                      </div>
                    );
                  })}
                </div>
              </section>
            );
          })}
          {err && <div className="card p-5 text-[16px] font-semibold">{err}</div>}
          {rm && <section className="card p-6 flex flex-col" style={{ transform: "rotate(-0.4deg)" }}>
            <div className="flex items-center justify-between gap-3 mb-3">
              <span className="wide font-black text-2xl leading-none">TRANSFER ROADMAP</span>
              <span className="text-[13px] font-bold bg-ink text-cream rounded-full px-3 py-1">{count} of {n}</span>
            </div>
            {rm?.steps.map((s, i) => {
              const d = !!done[i];
              return (
                <div key={i} className="flex flex-col">
                  <div className={`rounded-[14px] px-3 py-2.5 border-2 ${d ? "border-solid border-ink bg-page" : "border-dashed border-dash"}`}>
                    <button onClick={() => setDone({ ...done, [i]: !d })} aria-pressed={d} className="w-full flex items-center gap-3 text-left">
                      <span className={`h-[34px] w-[34px] shrink-0 rounded-full border-2.5 border-ink flex items-center justify-center font-display font-extrabold text-sm ${d ? "bg-ink text-cream" : "bg-orange text-ink"}`}>{d ? "✓" : i + 1}</span>
                      <span className="flex-1 text-[15px] font-semibold leading-snug">{s.title}</span>
                      <span className="text-xs font-bold">+{i === n - 1 ? 50 : 10}</span>
                    </button>
                    <div className="ml-[46px] mt-2 flex flex-wrap gap-2">
                      {s.resources.map((r) => (
                        <a key={r.id} href={r.source_url || s.source_url} target="_blank" rel="noreferrer" title={r.evidence}
                          className="no-underline text-xs font-semibold border-2 border-ink rounded-full px-2.5 py-1 bg-page">{r.name}{r.fetched_at ? ` · verified ${shortDate(r.fetched_at)}` : ""}</a>
                      ))}
                      {s.source_url && <a href={s.source_url} target="_blank" rel="noreferrer" className="text-xs font-semibold underline">{s.source_label || s.source_id} ↗</a>}
                      {s.resources.length === 0 && <span className="text-xs text-muted">Run {s.source_id} on the Sources page to pull its details.</span>}
                    </div>
                  </div>
                  {i < n - 1 && <div className="h-3 ml-[30px] border-l-2.5 border-dashed border-ink" />}
                </div>
              );
            })}
          </section>}
          </div>

          <aside className="flex-[1_1_300px] min-w-0 flex flex-col gap-5">
            <div className="flex items-center gap-4">
              <div className="h-[110px] w-[110px] shrink-0 rounded-full bg-cream border-2.5 border-dashed border-ink flex flex-col items-center justify-center" style={{ transform: "rotate(-6deg)" }}>
                <span className="wide font-black text-3xl">{pts}</span><span className="text-[11px] font-bold tracking-wider">POINTS</span>
              </div>
              <span className="text-[15px] font-semibold">{count} of {totalSteps} steps done</span>
            </div>
            <div className="card p-5 flex flex-col gap-2">
              <span className="wide-110 font-extrabold text-[17px]">Heads up</span>
              <p className="m-0 text-sm leading-relaxed">Perimeter students apply to move downtown with the Transition Application after advising, and can't live in Atlanta campus housing. Both facts come from the Perimeter College source on this list.</p>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
