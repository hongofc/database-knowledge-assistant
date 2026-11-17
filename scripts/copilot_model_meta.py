"""Show the raw Copilot /models metadata so the chat filter can be fixed.

GitHub lists models on /models that are NOT usable via /chat/completions
(they return 400 "not accessible via the /chat/completions endpoint"). This
prints the fields that distinguish them so the provider can filter properly.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factory_knowledge.providers import CopilotProvider, _http_json  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KNOWN_BAD = {
    "gpt-5.3-codex", "gpt-5.4-nano", "gpt-5.6-luna", "gpt-5.6-sol",
    "gpt-6.1-sol", "gpt-6.1-terra", "gpt-6-luna",
}
KNOWN_GOOD = {
    "claude-haiku-5.5", "claude-opus-5.5", "claude-opus-5",
    "claude-sonnet-5.5", "claude-sonnet-5", "gemini-3.8-flash", "gemini-4-argon",
}


def main() -> None:
    if not os.getenv("GITHUB_COPILOT_TOKEN"):
        f = ROOT / ".copilot_token"
        if f.exists():
            os.environ["GITHUB_COPILOT_TOKEN"] = f.read_text(encoding="utf-8").strip()

    p = CopilotProvider()
    api_token = p._api_token()
    data = _http_json(
        f"{p._API}/models",
        headers={"Authorization": f"Bearer {api_token}", **p._EDITOR_HEADERS},
        timeout=20.0,
    )

    print(f"total entries: {len(data.get('data', []))}\n")
    for item in data.get("data", []):
        mid = item.get("id", "?")
        if mid not in KNOWN_BAD and mid not in KNOWN_GOOD:
            continue
        tag = "GOOD" if mid in KNOWN_GOOD else "BAD "
        caps = item.get("capabilities", {}) or {}
        print(f"[{tag}] {mid}")
        print(f"        model_picker_enabled : {item.get('model_picker_enabled')}")
        print(f"        capabilities.type    : {caps.get('type')}")
        print(f"        supported_endpoints  : {item.get('supported_endpoints')}")
        print(f"        capabilities.supports: {json.dumps(caps.get('supports', {}))[:90]}")
        print(f"        other keys           : {sorted(k for k in item if k not in ('id','capabilities'))}")
        print()


if __name__ == "__main__":
    main()
