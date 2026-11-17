"""Diagnose a Copilot HTTP 400.

urllib raises HTTPError without surfacing the response body, so
"HTTP Error 400: Bad Request" hides GitHub's actual complaint. This reads the
body, then tries each entitled model to find which ones the account can really
use for chat.

Never prints the OAuth or API token.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factory_knowledge.providers import CopilotProvider  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def load_token() -> None:
    """Mirror run_app.sh: .copilot_token -> GITHUB_COPILOT_TOKEN."""
    if os.getenv("GITHUB_COPILOT_TOKEN"):
        return
    f = ROOT / ".copilot_token"
    if f.exists():
        os.environ["GITHUB_COPILOT_TOKEN"] = f.read_text(encoding="utf-8").strip()


def post(url: str, payload: dict, headers: dict) -> tuple[int, str]:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()[:400]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]
    except Exception as e:  # noqa: BLE001
        return -1, str(e)[:200]


def main() -> None:
    load_token()
    p = CopilotProvider()
    if not p.oauth_token:
        print("No OAuth token found - sign in first.")
        return
    print(f"oauth token present: yes ({len(p.oauth_token)} chars)")

    try:
        api_token = p._api_token()
    except Exception as exc:  # noqa: BLE001
        print(f"TOKEN EXCHANGE FAILED: {exc}")
        return
    print("token exchange: ok")

    models = p._models(api_token)
    print(f"entitled chat models: {len(models)}")
    print(f"  {', '.join(models[:12])}{' ...' if len(models) > 12 else ''}")
    print(f"configured default  : {p.model}")
    print(f"default is entitled : {p.model in models}")
    print()

    hdrs = {"Authorization": f"Bearer {api_token}", **p._EDITOR_HEADERS}
    url = f"{p._API}/chat/completions"
    msgs = [{"role": "user", "content": "Reply with the single word: ok"}]

    # 1. exactly what the app sends, with the configured model
    print("--- as the app sends it ---")
    code, body = post(url, {"model": p.model, "temperature": 0.1, "messages": msgs}, hdrs)
    print(f"  HTTP {code}  {body[:260]}")
    print()

    # 2. without temperature (some models reject sampling knobs)
    print("--- same model, no temperature ---")
    code, body = post(url, {"model": p.model, "messages": msgs}, hdrs)
    print(f"  HTTP {code}  {body[:200]}")
    print()

    # 3. sweep the entitled models
    print("--- per-model sweep (with temperature) ---")
    ok, bad = [], []
    for m in models[:14]:
        code, body = post(url, {"model": m, "temperature": 0.1, "messages": msgs}, hdrs)
        flag = "OK " if code == 200 else f"{code}"
        (ok if code == 200 else bad).append(m)
        print(f"  [{flag}] {m:34s} {'' if code == 200 else body[:110]}")
    print()
    print(f"WORKING : {len(ok)} -> {', '.join(ok[:10])}")
    print(f"FAILING : {len(bad)} -> {', '.join(bad[:10])}")


if __name__ == "__main__":
    main()
