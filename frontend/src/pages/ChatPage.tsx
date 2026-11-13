import { useEffect, useRef, useState } from "react";
import { api, CAMPUS_LABEL } from "../api";
import EmailDraftModal from "../components/EmailDraftModal";
import MatchCard from "../components/MatchCard";
import TracePanel from "../components/TracePanel";
import type { ChatResponse, Profile } from "../types";

type Turn = { me: true; text: string } | { me: false; text: string; res?: ChatResponse };
const TILTS = [-3, 2, -1.5, 3, -2, 1.5];
const SUGGEST = ["I want to turn my side hustle into a real business. I'm at Perimeter. Where do I start?",
  "I'm interested in medicine. What can I do at GSU right now?",
  "What does my advisement hold mean and who do I talk to?"];

export default function ChatPage({ profile, onEditProfile }: { profile: Profile | null; onEditProfile: () => void }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [typed, setTyped] = useState("");
  const [thinking, setThinking] = useState(false);
  const [listening, setListening] = useState(false);
  const [micNote, setMicNote] = useState("");
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

  // Voice input: Chrome/Edge Web Speech API (uses Google's speech service, so it needs internet + mic permission).
  // Shows what it hears live, explains every failure, and sends when you stop talking. Pathfinder answers in text.
  const MIC_ERR: Record<string, string> = {
    "not-allowed": "Mic is blocked. Click the icon left of the address bar → Microphone → Allow, then reload.",
    "service-not-allowed": "Mic is blocked for this site. Allow it in the address bar, then reload.",
    "no-speech": "I didn't hear anything. Tap the mic and start talking right away.",
    "audio-capture": "No microphone found. Check Windows Settings → Privacy → Microphone.",
    network: "Chrome's speech service couldn't be reached. Check the Wi-Fi, or type instead.",
    aborted: "",
  };
  const mic = () => {
    if (listening) { rec.current?.stop(); return; }
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) { setMicNote("Voice needs Chrome or Edge. You can type it here too."); return; }
    const r = new SR(); rec.current = r;
    r.lang = "en-US"; r.interimResults = true; r.continuous = false; r.maxAlternatives = 1;
    let finalText = "";
    r.onstart = () => { setListening(true); setMicNote("Listening… speak now"); };
    r.onresult = (e: any) => {
      let fin = "", interim = "";
      for (let i = 0; i < e.results.length; i++) (e.results[i].isFinal ? (fin += e.results[i][0].transcript) : (interim += e.results[i][0].transcript));
      finalText = (fin || finalText).trim();
      setTyped((fin + interim).trim());
      setMicNote(interim ? `Hearing: “${(fin + interim).trim()}”` : "Got it");
    };
    r.onerror = (e: any) => { setListening(false); setMicNote(MIC_ERR[e.error] ?? `Voice error: ${e.error}. Try again or type it.`); };
    r.onend = () => {
      setListening(false);
      const t = finalText || (document.getElementById("ask") as HTMLInputElement | null)?.value || "";
      if (t.trim()) { setMicNote(""); send(t); }
    };
    try { r.start(); } catch { setMicNote("Couldn't start the mic. Reload the page and try again."); }
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
          <span className="text-sm">{profile.campus_name || CAMPUS_LABEL[profile.campus] || profile.campus}</span>
          {profile.major && <span className="text-sm">· {profile.major}</span>}
          {profile.credits > 0 && <span className="text-sm">· {profile.credits} credits</span>}
          {profile.topics.slice(0, 5).map((t, i) => (
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
              {t.res && !t.res.matches.length && !!t.res.unverified?.length && (
                <div className="self-start w-full max-w-[85%] rounded-[18px] border-2.5 border-dashed border-ink bg-cream px-4 py-3 flex flex-col gap-2">
                  <span className="text-sm font-bold">Found on gsu.edu, not verified yet</span>
                  <span className="text-xs text-muted">I found these official pages but couldn't read them to check the details (some GSU sites block automated readers). Open them directly:</span>
                  {t.res.unverified.map((u) => (
                    <a key={u.url} href={u.url} target="_blank" rel="noreferrer" className="text-[14px] font-semibold underline break-all">{u.title || u.url} ↗</a>
                  ))}
                </div>
              )}
              {t.res && <TracePanel trace={t.res.trace} verification={t.res.verification} />}
            </div>
          ))}
          {thinking && (
            <div className="self-start px-4 py-2.5 border-2 border-ink bg-sticky rounded-[18px_18px_18px_4px] text-sm font-semibold" aria-label="Pathfinder is working">
              Planning, searching GSU sources (and gsu.edu live if needed), checking facts {[0, 1, 2].map((d) => <span key={d} style={{ animation: `pfDots 1.2s ${d * 0.2}s infinite` }}>•</span>)}
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
        {micNote && <span role="status" className="text-[13px] font-semibold px-2 -mt-1">{micNote}</span>}
      </section>

      {draftFor && <EmailDraftModal resourceId={draftFor} onClose={() => setDraftFor(null)} />}
    </main>
  );
}
