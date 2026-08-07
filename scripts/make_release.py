"""Export a clean, shareable copy of the project.

    .venv/Scripts/python.exe scripts/make_release.py

Copies only what a teammate needs to run the app. Deliberately EXCLUDES every
credential-bearing file, all virtualenvs, caches, and local state.

The result is safe to `git init` and push public, and safe to zip and hand over
directly -- which matters, because a folder copy does NOT respect .gitignore.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT.parent / "Database_Knowledge_Assistant"

# --- things that must never leave this machine -------------------------------
SECRETS = {".env", ".copilot_token", ".copilot_flow.json"}

# --- directories excluded wholesale ------------------------------------------
SKIP_DIRS = {
    ".venv", ".pdfvenv", "venv", "env",          # virtualenvs
    "node_modules",                               # npm (deck build only)
    "__pycache__", ".pytest_cache", ".ruff_cache",
    ".chroma",                                    # rebuilt on first run
    "render",                                     # slide QA screenshots
    ".git",                                       # start history fresh
    ".idea", ".vscode",
}

# --- individual files excluded ------------------------------------------------
SKIP_FILES = {
    ".sessions.db",                  # real chat transcripts
    "docs_starter_kit_README.md",    # starter-kit material, not accepted
    "package-lock.json",
}

SKIP_SUFFIXES = {".pyc", ".pyo", ".log"}
SKIP_PREFIXES = ("~$",)              # Office lock files


def keep(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in SKIP_DIRS for part in rel.parts):
        return False
    if path.name in SECRETS or path.name in SKIP_FILES:
        return False
    if path.suffix in SKIP_SUFFIXES:
        return False
    if path.name.startswith(SKIP_PREFIXES):
        return False
    if path.name.endswith(".sessions.db"):
        return False
    return True


def main() -> int:
    # The destination is a real git repo once you have run `git init` in it.
    # Wiping the whole folder would delete .git along with the history and the
    # configured remote, so preserve it and clear only the tracked content.
    if DEST.exists():
        for item in DEST.iterdir():
            if item.name == ".git":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    else:
        DEST.mkdir(parents=True)

    copied = 0
    for src in ROOT.rglob("*"):
        if not src.is_file() or not keep(src):
            continue
        dst = DEST / src.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1

    # Verify no secret slipped through, by name and by content signature.
    leaked = []
    for f in DEST.rglob("*"):
        if not f.is_file():
            continue
        if f.name in SECRETS:
            leaked.append(f"{f.relative_to(DEST)} (secret filename)")
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        # Built at runtime so this file never contains a literal token prefix
        # -- otherwise the scanner flags itself.
        for marker in ("ghu" + "_", "ghp" + "_", "sk-" + "proj-", "sk-" + "ant-api"):
            if marker in text:
                leaked.append(f"{f.relative_to(DEST)} (contains {marker!r})")
                break

    print(f"Copied {copied} files -> {DEST}")
    if leaked:
        print("\nREFUSING TO SHIP -- credential material found:")
        for item in leaked:
            print(f"  ! {item}")
        return 1

    print("Verified clean: no tokens, keys, or credential files present.")
    print(f"\nNext:\n  cd {DEST}\n  git init && git add -A && git commit -m 'Initial commit'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
