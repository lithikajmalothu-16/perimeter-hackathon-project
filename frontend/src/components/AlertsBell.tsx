import { useEffect, useRef, useState } from "react";
import { api, shortDate } from "../api";
import type { Alert } from "../types";

// Polls /api/alerts?unread=1 every 5s. A new unread alert fires a toast and bumps the count.
export default function AlertsBell({ onNew }: { onNew: (msg: string) => void }) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [open, setOpen] = useState(false);
  const seen = useRef<Set<number> | null>(null);

  useEffect(() => {
    let live = true;
    const tick = () => api.alerts(true).then((a) => {
      if (!live) return;
      if (seen.current) a.filter((x) => !seen.current!.has(x.id)).slice(0, 1).forEach((x) => onNew(x.message));
      seen.current = new Set(a.map((x) => x.id));
      setAlerts(a);
    }).catch(() => {});
    tick();
    const t = window.setInterval(tick, 5000);
    return () => { live = false; window.clearInterval(t); };
  }, [onNew]);

  const markRead = async (id: number) => { await api.readAlert(id); setAlerts((a) => a.filter((x) => x.id !== id)); };

  return (
    <div className="relative">
      <button onClick={() => setOpen((o) => !o)} aria-label={`Alerts, ${alerts.length} unread`} aria-expanded={open}
        className="relative h-[38px] w-[42px] rounded-full border-2.5 border-ink bg-cream flex items-center justify-center">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="#F4F0EA" stroke="#1C2426" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z" /><path d="M10 20a2 2 0 0 0 4 0" fill="none" />
        </svg>
        {alerts.length > 0 && (
          <span className="absolute -top-2 -right-2 min-w-[22px] h-[22px] px-1 rounded-full border-2 border-ink bg-orange text-[12px] font-black font-display flex items-center justify-center">{alerts.length}</span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-3 w-80 z-40 card p-3 flex flex-col gap-2">
          <span className="wide-110 font-extrabold text-[15px] px-1">Alerts</span>
          {alerts.length === 0 && <span className="text-sm text-muted px-1 pb-1">Nothing new. The watcher checks after every source run.</span>}
          {alerts.map((a) => (
            <div key={a.id} className="border-t-[1.5px] border-dashed border-ink pt-2 px-1 flex flex-col gap-1">
              <span className="text-sm font-semibold leading-snug">{a.message}</span>
              <span className="text-xs text-muted">{a.event_start ? `${shortDate(a.event_start)} · ` : ""}{shortDate(a.created_at)}</span>
              <div className="flex gap-2">
                {a.source_url && <a href={a.source_url} target="_blank" rel="noreferrer" className="text-xs font-semibold underline">Open</a>}
                <button onClick={() => markRead(a.id)} className="text-xs font-semibold underline">Mark read</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
