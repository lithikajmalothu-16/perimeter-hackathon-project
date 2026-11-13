import { CAMPUS_LABEL, dateTime, shortDate } from "../api";
import type { Match } from "../types";

const TYPE_ICON: Record<string, string> = { event: "M4 7h16v13H4zM4 11h16M9 4v5M15 4v5", program: "M12 3l9 5-9 5-9-5zM7 11v5c3 2 7 2 10 0v-5",
  office: "M4 21V7l8-4 8 4v14M9 21v-5h6v5", org: "M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM16 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM2 20c0-3 3-5 6-5s6 2 6 5M12 20c0-3 2-5 5-5s5 2 5 5",
  center: "M3 21h18M5 21V10l7-6 7 6v11M10 21v-6h4v6", opportunity: "M12 3l2.6 5.6 6 .7-4.5 4.1 1.2 6L12 16.6 6.7 19.4l1.2-6L3.4 9.3l6-.7z", service: "M12 21s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.6-7 10-7 10z" };

export default function MatchCard({ m, i, onDraft }: { m: Match; i: number; onDraft: (id: string) => void }) {
  const r = m.resource;
  const contact = [r.contact_office, r.contact_email, r.contact_phone].filter(Boolean).join(" · ");
  const where = [r.location_building, r.location_room && `Room ${r.location_room}`].filter(Boolean).join(", ");
  return (
    <article className={`card p-5 flex flex-col gap-3 ${i % 2 ? "bg-sticky" : ""}`} style={{ transform: `rotate(${i % 2 ? 0.5 : -0.5}deg)` }}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="h-10 w-10 shrink-0 rounded-[14px] border-2.5 border-ink bg-orange flex items-center justify-center">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#1C2426" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={TYPE_ICON[r.type || "service"] || TYPE_ICON.service} /></svg>
          </span>
          <div className="min-w-0">
            <h3 className="wide font-black text-[19px] leading-tight m-0">{r.name}</h3>
            <span className="text-[13px] text-muted capitalize">{r.type} · {CAMPUS_LABEL[r.campus || ""] || r.campus}</span>
          </div>
        </div>
        {r.fetched_at && <span className="shrink-0 text-[12px] font-bold bg-sticky border-2 border-ink rounded-full px-2.5 py-1">verified {shortDate(r.fetched_at)}</span>}
      </div>
      <p className="m-0 text-[15px] leading-snug"><b>Why it fits:</b> {m.why}</p>
      <div className="rounded-[14px] border-2 border-ink bg-page px-3 py-2.5 flex items-center gap-3">
        <span className="h-8 w-8 shrink-0 rounded-full border-2.5 border-ink bg-orange flex items-center justify-center font-display font-extrabold text-sm">1</span>
        <span className="text-[15px] font-semibold leading-snug">{m.first_step}</span>
      </div>
      {(contact || where || r.event_start || r.deadline || r.hours) && (
        <dl className="m-0 grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-[13px]">
          {r.event_start && <><dt className="font-semibold">When</dt><dd className="m-0">{dateTime(r.event_start)}</dd></>}
          {r.deadline && <><dt className="font-semibold">Deadline</dt><dd className="m-0">{shortDate(r.deadline)}</dd></>}
          {contact && <><dt className="font-semibold">Contact</dt><dd className="m-0 break-words">{contact}</dd></>}
          {where && <><dt className="font-semibold">Where</dt><dd className="m-0">{where}</dd></>}
          {r.hours && <><dt className="font-semibold">Hours</dt><dd className="m-0">{r.hours}</dd></>}
        </dl>
      )}
      <blockquote className="m-0 border-l-[3px] border-dashed border-ink pl-3 text-[13px] italic text-muted">“{r.evidence}”</blockquote>
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <button onClick={() => onDraft(r.id)} className="btn-ink h-10 px-4 text-sm">Draft email</button>
        {r.source_url && <a href={r.source_url} target="_blank" rel="noreferrer" className="btn-ghost h-10 px-4 text-sm inline-flex items-center no-underline">Source ↗</a>}
      </div>
    </article>
  );
}
