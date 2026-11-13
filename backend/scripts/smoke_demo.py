"""Runs demo steps 2 and 4 against the running API and writes data/demo_cache.json (used if both LLMs fail).
Start the API first (uvicorn app.main:app --port 8000), then: python scripts/smoke_demo.py"""
import sys
import httpx
import _path  # noqa: F401
from app.agents.router import save_to_cache

API = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/api"
STEPS = {
    "step 2": "I want to turn my side hustle into a real business. I'm at Perimeter. Where do I start?",
    "step 4": "What does my advisement hold mean and who do I talk to?",
}
ok = True
for name, msg in STEPS.items():
    r = httpx.post(f"{API}/chat", json={"message": msg, "history": []}, timeout=90)
    r.raise_for_status()
    data = r.json()
    good = bool(data["answer"]) and len(data["matches"]) >= 1
    ok &= good
    print(f"{name}: {'PASS' if good else 'FAIL'} · {len(data['matches'])} matches · checker={data['verification']['checker']}")
    for m in data["matches"]:
        print("   -", m["resource"]["name"], "|", m["resource"].get("source_url"))
    if good:
        save_to_cache(msg, data)
print("demo_cache.json written" if ok else "Some steps failed; fix sources before the demo.")
sys.exit(0 if ok else 1)
