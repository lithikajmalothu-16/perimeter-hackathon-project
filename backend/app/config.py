"""Env + YAML config. Everything else imports settings from here."""
from __future__ import annotations
import json
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]          # repo root (pathfinder/)
BACKEND = ROOT / "backend"
CONFIG_DIR = BACKEND / "config"
PROMPTS_DIR = BACKEND / "app" / "prompts"
DATA_DIR = BACKEND / "data"
load_dotenv(ROOT / ".env")
load_dotenv(BACKEND / ".env")                        # optional override


def _path(v: str) -> Path:
    p = Path(v)
    return p if p.is_absolute() else ROOT / p


class Settings:
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    # live discovery (Google Search grounding) has its own, smaller free quota per model: try these in order
    gemini_search_models = [m.strip() for m in os.getenv("GEMINI_SEARCH_MODEL", "").split(",") if m.strip()]
    groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
    groq_model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b").strip()
    database_path = _path(os.getenv("DATABASE_PATH", "backend/data/pathfinder.db"))
    stale_hours = float(os.getenv("STALE_HOURS", "168"))
    scheduler_enabled = os.getenv("SCHEDULER_ENABLED", "0") == "1"
    cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
    user_agent = os.getenv("HTTP_USER_AGENT", "PathfinderGSU/1.0 (HackPerimeter student project)")
    demo_fallback = os.getenv("DEMO_FALLBACK", "1") == "1"


settings = Settings()


def load_sources() -> dict:
    return yaml.safe_load((CONFIG_DIR / "sources.yaml").read_text(encoding="utf-8"))


def load_pathways() -> list[dict]:
    return yaml.safe_load((CONFIG_DIR / "pathways.yaml").read_text(encoding="utf-8"))


def load_demo_profile() -> dict:
    return json.loads((CONFIG_DIR / "demo_profile.json").read_text(encoding="utf-8"))


def prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")
