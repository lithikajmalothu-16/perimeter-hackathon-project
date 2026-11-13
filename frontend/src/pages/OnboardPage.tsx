import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Major, Profile } from "../types";

// Page 1 · About you (artifact layout): name, verified GSU email, campus, major. Nothing else.
const CAMPUSES = ["Atlanta", "Alpharetta", "Clarkston", "Decatur", "Dunwoody", "Newton", "Online"];
const GSU = /^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?@(?:student\.)?gsu\.edu$/;
const TILTS = [-3, 2, -1.5, 3, -2, 1.5, -2.5, 2.5, -1, 1];
const EXTRA = ["career", "research", "clubs", "events", "community", "entrepreneurship", "transition", "international", "financial_aid", "technology", "health", "arts"];

export default function OnboardPage({ onDone }: { onDone: (p: Profile) => void }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [campus, setCampus] = useState("Clarkston");
  const [majors, setMajors] = useState<Major[]>([]);
  const [majorText, setMajorText] = useState("");
  const [extra, setExtra] = useState<string[]>([]);
  const [err, setErr] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState("");
  useEffect(() => { api.majors().then(setMajors).catch(() => {}); }, []);

  const e = email.trim().toLowerCase();
  const isGsu = GSU.test(e) && !e.includes("..");
  const major = useMemo(() => majors.find((m) => m.name.toLowerCase() === majorText.trim().toLowerCase()), [majors, majorText]);
  const topics = Array.from(new Set([...(major?.topics || []), ...extra]));

  const next = async () => {
    const er: Record<string, string> = {};
    if (!name.trim()) er.name = "Add your name so I know who I'm planning for.";
    if (!isGsu) er.email = "Use your GSU email, like name@student.gsu.edu.";
    if (!major) er.major = "Pick your major from the list (start typing).";
    if (Object.keys(er).length) return setErr(er);
    setBusy("next");
    try { onDone(await api.onboard({ name: name.trim(), email: e, campus_name: campus, major: major!.id, topics: extra })); }
    catch (x) { setErr({ email: String((x as Error).message) }); }
    finally { setBusy(""); }
  };

  const input = "h-[52px] rounded-[14px] border-2.5 border-ink bg-white px-4 text-[17px] text-ink";
  return (
    <main className="mx-auto max-w-[1240px] px-8 pt-12 pb-16 flex flex-wrap gap-10 items-center">
      <div className="flex-[1_1_420px] min-w-0 flex flex-col gap-4">
        <h1 className="wide font-black m-0 leading-[0.95]" style={{ fontSize: "clamp(46px, 7vw, 96px)" }}>LET'S MAP YOUR NEXT MOVE.</h1>
        <p className="m-0 text-xl leading-normal max-w-[520px]">Four quick things. Then ask me anything, and I'll find the real GSU office, program or event for it, with the page it came from.</p>
      </div>

      <div className="flex-[1_1_420px] min-w-0 card !rounded-[26px] shadow-hardlg p-[30px] flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="nm" className="text-sm font-semibold">Your name</label>
          <input id="nm" value={name} onChange={(x) => { setName(x.target.value); setErr({}); }} placeholder="Amara Okafor" autoComplete="name" className={input} />
          {err.name && <span className="text-[13px] text-danger">{err.name}</span>}
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="em" className="text-sm font-semibold">GSU student email</label>
          <div className="flex flex-wrap gap-2">
            <input id="em" type="email" value={email} onChange={(x) => { setEmail(x.target.value); setErr({}); }}
              placeholder="aokafor1@student.gsu.edu" autoComplete="email" className={`${input} flex-[1_1_220px] min-w-0`} />
          </div>
          {isGsu && <span className="self-start text-[13px] font-bold bg-sticky border-2 border-ink rounded-full px-3 py-1">✓ GSU email</span>}
          {err.email && <span className="text-[13px] text-danger">{err.email}</span>}
        </div>

        <div className="flex flex-col gap-2">
          <span className="text-sm font-semibold">Your GSU campus</span>
          <div className="flex flex-wrap gap-2">{CAMPUSES.map((c) => <button key={c} onClick={() => setCampus(c)} aria-pressed={campus === c} className={`pill ${campus === c ? "pill-on" : "pill-off"}`}>{c}</button>)}</div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="mj" className="text-sm font-semibold">Your major or pathway</label>
          <input id="mj" list="majors" value={majorText} onChange={(x) => { setMajorText(x.target.value); setErr({}); }} placeholder="Start typing: Nursing, Computer Science, Undecided…" className={input} />
          <datalist id="majors">{majors.map((m) => <option key={m.id} value={m.name}>{m.college}</option>)}</datalist>
          {major && <span className="text-xs text-muted">{major.degree} · {major.college}</span>}
          {err.major && <span className="text-[13px] text-danger">{err.major}</span>}
        </div>

        <div className="flex flex-col gap-2">
          <span className="text-sm font-semibold">Also into (optional)</span>
          <div className="flex flex-wrap gap-2.5">{EXTRA.map((t, i) => { const on = topics.includes(t); return (
            <button key={t} onClick={() => setExtra(extra.includes(t) ? extra.filter((x) => x !== t) : [...extra, t])} aria-pressed={on} style={{ transform: `rotate(${TILTS[i % 10]}deg)` }}
              className={`min-h-[40px] px-3.5 rounded-2xl border-2.5 border-ink font-display font-bold text-sm capitalize ${on ? "bg-orange shadow-hardsm" : "bg-cream"}`}>{t.replace("_", " ")}</button>); })}</div>
        </div>

        <button onClick={next} disabled={busy === "next"} className="btn-ink h-14 wide-110 text-[17px]">{busy === "next" ? "One sec…" : "Next: ask Pathfinder"}</button>
        <button onClick={async () => onDone(await api.demoProfile())} className="self-center text-xs font-semibold underline">Skip: use the demo student (Jordan)</button>
      </div>
    </main>
  );
}
