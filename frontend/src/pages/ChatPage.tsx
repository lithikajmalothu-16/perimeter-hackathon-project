import { useEffect, useRef, useState } from "react";
import { api, CAMPUS_LABEL } from "../api";
import EmailDraftModal from "../components/EmailDraftModal";
import MatchCard from "../components/MatchCard";
import TracePanel from "../components/TracePanel";
import type { ChatResponse, Profile } from "../types";

type Turn = { me: true; text: string } | { me: false; text: string; res?: ChatResponse };
const TILTS = [-3, 2, -1.5, 3, -2, 1.5];
const SUGGEST = ["I want to turn my side hustle into a real business. I'm at Perimeter. Where do I start?",
  "What does my advisement hold mean and who do I talk to?"];

export default function ChatPage({ profile, onEditProfile }: { profile: Profile | null; onEditProfile: () => void }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [typed, setTyped] = useState("");
  const [thinking, setThinking] = useState(false);
  const [listening, setListening] = useState(false);
  const [draftFor, setDraftFor] = useState<string | null>(null);
  const rec = useRef<any>(null);
  const end = useRef<HTMLDivElement>(null);
  const first = (profile?.name || "friend").split(" ")[0];

  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns, thinking]);

  const send = async (raw = typed) => {
    const text = raw.trim();
    if (!text || thinking) return;
    setTyped("");
    const history = turns.map((t) => ({ role: t.me ? "user" as const : "assistant" as const, content: t.text }));
    setTurns((t) => [...t, { me: true, text }]);
    setThinking(true);
    try {
      const res = await api.chat(text, history);
      setTurns((t) => [...t, { me: false, text: res.answer, res }]);
    } catch {
      setTurns((t) => [...t, { me: false, text: "I couldn't reach the Pathfinder API. Is the backend running on port 8000?" }]);
    } finally { setThinking(false); }
  };

  // Voice input (Web Speech API in Chrome/Edge/Safari). Pathfinder answers in text.
  const mic = () => {
    if (listening) { rec.current?.stop(); return; }
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) { setTurns((t) => [...t, { me: false, text: "Voice works in Chrome or Safari. You can type it here too." }]); return; }
    const r = new SR(); rec.current = r; r.lang = "en-US"; r.interimResults = true;
    let finalText = "";
    r.onresult = (e: any) => { let s = ""; for (const x of e.results) s += x[0].transcript; finalText = s; setTyped(s); };
    r.onend = () => { setListening(false); if (finalText.trim()) send(finalText); };
    r.onerror = () => setListening(false);
    setListening(true); r.start();
  };

  return (
    <main className="mx-auto max-w-[1240px] px-8 pt-9 pb-16 flex flex-col gap-6">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="wide font-black m-0 leading-[0.95]" style={{ fontSize: "clamp(44px, 8vw, 110px)" }}>HEY, {first.toUpperCase()}.</h1>
        <p className="m-0 tracking-wide" style={{ fontSize: "clamp(18px, 2.2vw, 24px)" }}>Ask anything. I only answer from verified GSU pages, and I show you where.</p>
      </div>

      {profile && (
        <button onClick={onEditProfile} aria-label="Edit your profile" className="self-center card !rounded-full px-5 py-2.5 flex flex-wrap items-center justify-center gap-x-3 gap-y-2 text-left">
          <span className="font-display font-extrabold">{profile.name}</span>
          <span className="text-sm">{CAMPUS_LABEL[profile.campus] || profile.campus}</span>
          <span className="text-sm">· Business Administration · {profile.credits} credits</span>
          {profile.topics.map((t, i) => (
            <span key={t} className="text-[13px] font-display font-bold capitalize rounded-xl border-2 border-ink bg-orange px-2.5 py-0.5" style={{ transform: `rotate(${TILTS[i % 6]}deg)` }}>{t.replace("_", " ")}</span>
          ))}
          <span className="text-xs font-semibold underline">edit</span>
        </button>
      )}

      <section className="card !rounded-[24px] p-5 flex flex-col gap-3">
        <span className="wide-110 font-extrabold text-lg">Tell me</span>
        <div aria-live="polite" className="flex flex-col gap-3 min-h-[240px]">
          {turns.length === 0 && (
            <div className="self-start max-w-[85%] px-3.5 py-2.5 text-[15px] leading-snug border-2 border-ink bg-sticky rounded-[18px_18px_18px_4px]">
              Hey {first}! Tell me what you're trying to do: start something, fix a hold, plan your move downtown, anything. I'll find the real GSU office, program or event for it.
            </div>
          )}
          {turns.map((t, i) => t.me ? (
            <div key={i} className="self-end max-w-[85%] px-3.5 py-2.5 text-[15px] leading-snug border-2 border-ink bg-ink text-cream rounded-[18px_18px_4px_18px]">{t.text}</div>
          ) : (
            <div key={i} className="flex flex-col gap-3">
              <div className="self-start max-w-[85%] px-3.5 py-2.5 text-[15px] leading-snug border-2 border-ink bg-sticky rounded-[18px_18px_18px_4px]">{t.text}</div>
              {t.res && t.res.matches.length > 0 && (
                <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3 pt-1 pb-2">
                  {t.res.matches.map((m, j) => <MatchCard key={m.resource.id} m={m} i={j} onDraft={setDraftFor} />)}
                </div>
              )}
              {t.res && <TracePanel trace={t.res.trace} verification={t.res.verification} />}
            </div>
          ))}
          {thinking && (
            <div className="self-start px-4 py-2.5 border-2 border-ink bg-sticky rounded-[18px_18px_18px_4px] text-sm font-semibold" aria-label="Pathfinder is working">
              Planning, searching GSU sources, checking facts {[0, 1, 2].map((d) => <span key={d} style={{ animation: `pfDots 1.2s ${d * 0.2}s infinite` }}>•</span>)}
            </div>
          )}
          <div ref={end} />
        </div>

        {turns.length === 0 && (
          <div className="flex flex-wrap gap-2">
            {SUGGEST.map((s) => <button key={s} onClick={() => send(s)} className="pill pill-off text-left !text-[13px] py-1.5">{s}</button>)}
          </div>
        )}

        <div className="flex items-center gap-2 rounded-full border-2.5 border-ink bg-white pl-4 pr-1.5 py-1.5">
          <label htmlFor="ask" className="sr-only">Tell Pathfinder what you want</label>
          <input id="ask" value={typed} onChange={(e) => setTyped(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder={listening ? "Listening…" : "I want to turn my side hustle into a real business. Where do I start?"}
            className="flex-1 min-w-0 h-11 bg-transparent outline-none text-base" />
          <button onClick={mic} aria-label="Say it out loud" aria-pressed={listening}
            className={`h-[46px] w-[46px] rounded-full border-2.5 border-ink flex items-center justify-center ${listening ? "bg-ink text-cream" : "bg-orange text-ink"}`}
            style={listening ? { animation: "pfPulse 1.2s infinite" } : undefined}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0" /><path d="M12 18v3" /></svg>
          </button>
          <button onClick={() => send()} disabled={thinking} className="btn-ink h-[46px] px-5 text-[15px] font-semibold">Send</button>
        </div>
      </section>

      {draftFor && <EmailDraftModal resourceId={draftFor} onClose={() => setDraftFor(null)} />}
    </main>
  );
}
