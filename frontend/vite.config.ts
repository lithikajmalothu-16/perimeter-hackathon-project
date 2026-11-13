import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// envDir points at the repo root so VITE_API_BASE_URL comes from the same .env as the backend (on Vercel, set it in Project Settings)
export default defineConfig({ plugins: [react()], envDir: "..", server: { port: 5173 } });
