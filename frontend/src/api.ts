import type { Alert, ChatResponse, ChatRoadmap, DraftEmail, Health, Major, Profile, Resource, Roadmap, Run, Source } from "./types";

const BASE = (import.meta.env.VITE_API_BASE_URL as string) || "http://localhost:8000/api";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(BASE + path, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers || {}) } });
  if (!r.ok) {
    const t = await r.text();
    let msg = t;
    try { msg = JSON.parse(t).detail || t; } catch { /* not JSON */ }
    throw new Error(typeof msg === "string" ? msg.slice(0, 200) : `Error ${r.status}`);
  }
  return r.json();
}
const post = <T,>(p: string, body?: unknown) => req<T>(p, { method: "POST", body: body ? JSON.stringify(body) : undefined });

export const api = {
  health: () => req<Health>("/health"),
  profile: () => req<Profile>("/profile"),
  saveProfile: (p: Profile) => req<Profile>("/profile", { method: "PUT", body: JSON.stringify(p) }),
  chat: (message: string, history: { role: "user" | "assistant"; content: string }[]) => post<ChatResponse>("/chat", { message, history }),
  draftEmail: (resource_id: string) => post<DraftEmail>("/draft-email", { resource_id }),
  resources: (q: { topic?: string; campus?: string; type?: string } = {}) => req<Resource[]>("/resources?" + new URLSearchParams(q as Record<string, string>)),
  roadmap: (id: string) => req<Roadmap>(`/pathways/${id}/roadmap`),
  sources: () => req<Source[]>("/sources"),
  runSource: (id: string) => post<{ run: Run; alerts_created: number }>(`/sources/${id}/run`),
  runAll: () => post<{ runs: Run[]; alerts_created: number }>("/ingest/run-all"),
  alerts: (unread = true) => req<Alert[]>(`/alerts${unread ? "?unread=1" : ""}`),
  readAlert: (id: number) => post<{ ok: boolean }>(`/alerts/${id}/read`),
  majors: () => req<Major[]>("/majors"),
  onboard: (b: { name: string; email: string; campus_name: string; major: string; topics: string[] }) => post<Profile>("/onboard", b),
  demoProfile: () => post<Profile>("/profile/demo"),
  createRoadmap: (goal: string, resource_ids: string[]) => post<ChatRoadmap>("/roadmaps", { goal, resource_ids }),
  roadmaps: () => req<ChatRoadmap[]>("/roadmaps"),
  deleteRoadmap: (id: number) => req<{ ok: boolean }>(`/roadmaps/${id}`, { method: "DELETE" }),
};

export const CAMPUSES = ["Atlanta", "Alpharetta", "Clarkston", "Decatur", "Dunwoody", "Newton", "Online"];
export const CAMPUS_VALUE: Record<string, string> = { Atlanta: "atlanta_only", Alpharetta: "perimeter_all", Clarkston: "clarkston", Decatur: "perimeter_all",
  Dunwoody: "perimeter_all", Newton: "perimeter_all", Online: "online" };
export const CAMPUS_LABEL: Record<string, string> = { clarkston: "Clarkston", perimeter_all: "All Perimeter campuses", online: "Online", gsu_wide: "All of GSU", atlanta_only: "Atlanta campus" };
export const shortDate = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "");
export const dateTime = (iso?: string | null) => (iso ? new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "");
