import { useEffect, useState } from "react";
import { api, CAMPUSES, CAMPUS_VALUE } from "../api";
import type { Major, Profile } from "../types";

const TOPICS = ["business", "entrepreneurship", "technology", "health", "science", "research", "career", "clubs", "events", "community", "arts", "transition", "international", "financial_aid"];
const TILTS = [-3, 2, -1.5, 3, -2, 1.5, -2.5, 2.5, -1];

export default function ProfileModal({ profile, onClose, onSaved }: { profile: Profile; onClose: () => void; onSaved: (p: Profile) => void }) {
  const [p, setP] = useState<Profile>(profile);
  const [saving, setSaving] = useState(false);
  const [majors, setMajors] = useState<Major[]>([]);
  useEffect(() => { api.majors().then(setMajors).catch(() => {}); }, []);
  const pickMajor = (name: string) => {
    const m = majors.find((x) => x.name.toLowerCase() === name.trim().toLowerCase());
    setP({ ...p, major: name, ...(m ? { pathway_id: m.pathway_id, topics: Array.from(new Set([...m.topics])) } : {}) });
  };
  const toggle = (t: string) => setP({ ...p, topics: p.topics.includes(t) ? p.topics.filter((x) => x !== t) : [...p.topics, t] });
  const save = async () => { setSaving(true); try { onSaved(await api.saveProfile(p)); } finally { setSaving(false); } };
  return (
    <div role="dialog" aria-modal="true" aria-label="Edit profile" className="fixed inset-0 z-50 bg-ink/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="card shadow-hardlg w-full max-w-lg p-6 flex flex-col gap-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between"><h2 className="wide font-black text-2xl m-0">ABOUT YOU</h2><button onClick={onClose} aria-label="Close" className="text-2xl font-bold">×</button></div>
        <label className="flex flex-col gap-1.5 text-sm font-semibold">Your name
          <input value={p.name} onChange={(e) => setP({ ...p, name: e.target.value })} className="h-12 rounded-[14px] border-2.5 border-ink bg-white px-4 text-[17px] font-normal" /></label>
        <div className="flex flex-col gap-2"><span className="text-sm font-semibold">Campus</span>
          <div className="flex flex-wrap gap-2">{CAMPUSES.map((c) => { const on = (p.campus_name || "") === c; return (
            <button key={c} onClick={() => setP({ ...p, campus: CAMPUS_VALUE[c], campus_name: c })} aria-pressed={on} className={`pill ${on ? "pill-on" : "pill-off"}`}>{c}</button>); })}</div></div>
        <label className="flex flex-col gap-1.5 text-sm font-semibold">Major or pathway
          <input list="pm-majors" value={p.major || ""} onChange={(e) => pickMajor(e.target.value)} placeholder="Start typing: Nursing, Computer Science…" className="h-12 rounded-[14px] border-2.5 border-ink bg-white px-4 text-[16px] font-normal" />
          <datalist id="pm-majors">{majors.map((m) => <option key={m.id} value={m.name}>{m.college}</option>)}</datalist></label>
        <label className="hidden flex-col gap-1.5 text-sm font-semibold">Credits so far
          <input type="number" min={0} max={200} value={p.credits} onChange={(e) => setP({ ...p, credits: Number(e.target.value) })} className="h-12 w-32 rounded-[14px] border-2.5 border-ink bg-white px-4 text-[17px] font-normal" /></label>
        <label className="flex flex-col gap-1.5 text-sm font-semibold">What you want to do (optional)
          <input value={p.interests} onChange={(e) => setP({ ...p, interests: e.target.value })} className="h-12 rounded-[14px] border-2.5 border-ink bg-white px-4 text-[16px] font-normal" /></label>
        <div className="flex flex-col gap-2"><span className="text-sm font-semibold">What you're into</span>
          <div className="flex flex-wrap gap-2.5">{TOPICS.map((t, i) => { const on = p.topics.includes(t); return (
            <button key={t} onClick={() => toggle(t)} aria-pressed={on} style={{ transform: `rotate(${TILTS[i]}deg)` }}
              className={`min-h-[42px] px-3.5 rounded-2xl border-2.5 border-ink font-display font-bold text-sm capitalize ${on ? "bg-orange shadow-hardsm" : "bg-cream"}`}>{t.replace("_", " ")}</button>); })}</div></div>
        <button onClick={save} disabled={saving} className="btn-ink h-14 wide-110 text-[17px]">{saving ? "Saving…" : "Save"}</button>
      </div>
    </div>
  );
}
