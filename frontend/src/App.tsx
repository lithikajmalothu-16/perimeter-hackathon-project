import { useCallback, useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { api } from "./api";
import AlertsBell from "./components/AlertsBell";
import ProfileModal from "./components/ProfileModal";
import ChatPage from "./pages/ChatPage";
import RoadmapPage from "./pages/RoadmapPage";
import SourcesPage from "./pages/SourcesPage";
import type { Profile } from "./types";

export default function App() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [editing, setEditing] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [apiDown, setApiDown] = useState(false);

  useEffect(() => { api.profile().then(setProfile).catch(() => setApiDown(true)); }, []);
  const showToast = useCallback((m: string) => { setToast(m); window.setTimeout(() => setToast(null), 6000); }, []);

  const tabs: [string, string][] = [["/", "Chat"], ["/roadmap", "Roadmap"], ["/sources", "Sources"]];
  return (
    <div className="min-h-screen bg-page text-ink font-body">
      <header className="mx-auto max-w-[1240px] px-8 pt-6 flex flex-wrap items-center justify-between gap-3.5">
        <span className="wide-110 font-bold text-xl">Pathfinder · Georgia State</span>
        <div className="flex flex-wrap items-center gap-2">
          <nav aria-label="Pages" className="flex flex-wrap gap-2">
            {tabs.map(([to, label]) => (
              <NavLink key={to} to={to} end className={({ isActive }) => `pill inline-flex items-center ${isActive ? "pill-on" : "pill-off"}`}>{label}</NavLink>
            ))}
          </nav>
          <AlertsBell onNew={showToast} />
        </div>
      </header>

      {apiDown && (
        <div className="mx-auto max-w-[1240px] px-8 mt-4">
          <div className="card !shadow-none bg-sticky px-4 py-3 text-sm font-semibold">
            Can't reach the API. Start it from backend/: <code>uvicorn app.main:app --reload --port 8000</code>
          </div>
        </div>
      )}

      <Routes>
        <Route path="/" element={<ChatPage profile={profile} onEditProfile={() => setEditing(true)} />} />
        <Route path="/roadmap" element={<RoadmapPage profile={profile} />} />
        <Route path="/sources" element={<SourcesPage onAlerts={(n) => n > 0 && showToast(`${n} new alert${n === 1 ? "" : "s"} for you`)} />} />
      </Routes>

      {editing && profile && <ProfileModal profile={profile} onClose={() => setEditing(false)} onSaved={(p) => { setProfile(p); setEditing(false); }} />}
      {toast && (
        <div role="status" className="fixed bottom-6 right-6 z-50 max-w-sm card bg-sticky px-5 py-4 flex gap-3 items-start" style={{ animation: "pfToast .25s ease" }}>
          <span className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2.5 border-ink bg-orange font-display font-black">!</span>
          <span className="text-[15px] font-semibold leading-snug">{toast}</span>
          <button aria-label="Dismiss" onClick={() => setToast(null)} className="ml-auto text-lg font-bold leading-none">×</button>
        </div>
      )}
    </div>
  );
}
