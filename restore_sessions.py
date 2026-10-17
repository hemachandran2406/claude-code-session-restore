#!/usr/bin/env python3
"""
restore_sessions.py — make missing Claude Code sessions show up again in the
Claude Desktop "Code" tab, on Windows and macOS.

Typical causes: you logged into a different Claude account, logged out and back
in, or started sessions from the `claude` CLI / VS Code that never appeared in
the app. The transcripts are never lost; only the app's per-account index is.

What it does (idempotent, reversible):
  1. Backs up the Code-tab card index (claude-code-sessions/).
  2. Copies cards from other account folders into the current account's folder.
  3. Generates cards for transcripts that have no card anywhere (CLI / VS Code).

It never edits or deletes transcripts. DRY RUN BY DEFAULT; pass --apply to write.

  python3 restore_sessions.py                         # dry run
  python3 restore_sessions.py --apply                 # write changes
  python3 restore_sessions.py --apply --existing-cards-only

Python 3.8+, standard library only. Unofficial; not affiliated with Anthropic.
Based on sahol3/claude-code-session-restorer (MIT). See LICENSE.
"""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

HOME = Path.home()
SYSTEM = platform.system()  # "Windows", "Darwin", "Linux"


# --------------------------------------------------------------------------- paths
def default_paths():
    projects = HOME / ".claude" / "projects"
    claude_json = HOME / ".claude.json"
    if SYSTEM == "Windows":
        appdata = Path(os.environ.get("APPDATA", HOME / "AppData" / "Roaming"))
        app_base = appdata / "Claude" / "claude-code-sessions"
    elif SYSTEM == "Darwin":
        app_base = HOME / "Library" / "Application Support" / "Claude" / "claude-code-sessions"
    else:
        app_base = None  # no official Claude Desktop on Linux; pass --app-base
    return projects, claude_json, app_base


def say(msg=""):
    print(msg, flush=True)


def claude_running():
    try:
        if SYSTEM == "Windows":
            r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Claude.exe", "/NH"],
                               capture_output=True, text=True)
            return "Claude.exe" in r.stdout
        r = subprocess.run(["pgrep", "-x", "Claude"], capture_output=True, text=True)
        return bool(r.stdout.strip())
    except FileNotFoundError:
        return False


def read_account(claude_json: Path):
    if not claude_json.exists():
        sys.exit(f"Can't find {claude_json}. Is Claude Code installed and signed in? (run `claude` once)")
    txt = claude_json.read_text(encoding="utf-8", errors="replace")
    acct = org = None
    try:
        oa = json.loads(txt).get("oauthAccount") or {}
        acct, org = oa.get("accountUuid"), oa.get("organizationUuid")
    except Exception:
        pass
    if not (acct and org):
        m = re.search(r'"oauthAccount"\s*:\s*\{[\s\S]*?"accountUuid"\s*:\s*"([0-9a-fA-F-]+)"'
                      r'[\s\S]*?"organizationUuid"\s*:\s*"([0-9a-fA-F-]+)"', txt)
        if not m:
            sys.exit("Couldn't read the logged-in account from .claude.json. Sign in with `claude` first.")
        acct, org = m.group(1), m.group(2)
    return acct, org


# ------------------------------------------------------------------- transcripts
SKIP_PREFIX = re.compile(r"^\s*<|^This session is being continued|^\s*Caveat:|^Base directory for this skill")


def to_ms(iso, fallback_ts):
    if iso:
        try:
            return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)
        except Exception:
            pass
    return int(fallback_ts * 1000)


def get_meta(path: Path):
    """Return (cwd, created_iso, title) from the first ~400 lines of a transcript."""
    cwd = created = ai = summ = usr = None
    with path.open(encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if i >= 400:
                break
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            if not isinstance(o, dict):
                continue
            created = created or o.get("timestamp")
            cwd = cwd or o.get("cwd")
            if not ai and o.get("type") == "ai-title" and o.get("aiTitle"):
                ai = o["aiTitle"]
            if not summ and o.get("type") == "summary" and o.get("summary"):
                summ = o["summary"]
            if not usr and o.get("type") == "user" and isinstance(o.get("message"), dict):
                c = o["message"].get("content")
                txt = c if isinstance(c, str) else next(
                    (b.get("text") for b in (c or []) if isinstance(b, dict) and b.get("type") == "text"), None)
                if txt and not SKIP_PREFIX.match(txt):
                    usr = txt
            if cwd and created and ai:
                break
    title = ai or summ or usr
    if title:
        title = re.sub(r"\s+", " ", title).strip()[:80]
    return cwd, created, title


def load_card(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def same_dir(a: Path, b: Path):
    try:
        return a.resolve() == b.resolve()
    except Exception:
        return str(a).lower() == str(b).lower()


# -------------------------------------------------------------------------- main
def main():
    projects, claude_json, app_base = default_paths()

    ap = argparse.ArgumentParser(description="Restore missing Claude Code sessions in the Claude Desktop Code tab.")
    ap.add_argument("--apply", action="store_true", help="actually write changes (default: dry run)")
    ap.add_argument("--existing-cards-only", action="store_true",
                    help="only copy cards from other accounts; don't add CLI / VS Code sessions")
    ap.add_argument("--dest-root", help="write cards to this folder instead of the live one (testing)")
    ap.add_argument("--app-base", help="override the claude-code-sessions folder location")
    ap.add_argument("--projects-dir", help="override the transcripts folder (default ~/.claude/projects)")
    ap.add_argument("--ignore-running", action="store_true", help="don't abort if Claude Desktop is running")
    ap.add_argument("--no-backup", action="store_true", help="skip the index backup (testing only)")
    a = ap.parse_args()

    if a.app_base:
        app_base = Path(a.app_base).expanduser()
    if a.projects_dir:
        projects = Path(a.projects_dir).expanduser()
    if app_base is None:
        sys.exit("Unsupported OS for auto-detection. Pass --app-base <path to claude-code-sessions>.")

    dry = not a.apply
    say(f"== Claude Code -> Code-tab session restorer ({SYSTEM}) ==")
    say("DRY RUN: nothing will be written. Re-run with --apply to make changes.\n" if dry else "APPLY mode.\n")

    if not a.ignore_running and claude_running():
        quit_hint = "system tray -> right-click -> Quit" if SYSTEM == "Windows" else "Cmd+Q"
        sys.exit(f"Claude Desktop is still running. Quit it completely ({quit_hint}), then re-run.\n"
                 "(The app rewrites its session folder on exit, so changes made while it runs are lost.)")

    if a.dest_root:
        dest = Path(a.dest_root).expanduser()
    else:
        acct, org = read_account(claude_json)
        dest = app_base / acct / org
        say(f"Logged-in account : {acct}")
        say(f"Organization      : {org}")
    say(f"Card folder       : {dest}")
    say(f"Transcripts       : {projects}\n")

    if not dry:
        dest.mkdir(parents=True, exist_ok=True)
        if not a.no_backup and app_base.exists():
            bk = Path(f"{app_base}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}")
            shutil.copytree(app_base, bk)
            say(f"Backed up Code-tab index -> {bk}")

    all_cards = sorted(app_base.rglob("local_*.json"), key=lambda p: p.stat().st_size) if app_base.exists() else []
    tmpl = (load_card(all_cards[0]) if all_cards else None) or {}
    defaults = {
        "model": tmpl.get("model", "claude-opus-4-8"),
        "effort": tmpl.get("effort", "high"),
        "chromePermissionMode": tmpl.get("chromePermissionMode", "default"),
        "remoteMcpServersConfig": tmpl.get("remoteMcpServersConfig"),
    }

    have = set()
    if dest.exists():
        for f in dest.glob("local_*.json"):
            o = load_card(f)
            if o and o.get("cliSessionId"):
                have.add(str(o["cliSessionId"]).lower())

    # 1) copy cards from other account folders
    copied = 0
    for f in all_cards:
        if dest.exists() and same_dir(f.parent, dest):
            continue
        o = load_card(f)
        if not o or not o.get("cliSessionId"):
            continue
        key = str(o["cliSessionId"]).lower()
        if key in have:
            continue
        target = dest / f.name
        if target.exists():
            target = dest / f"local_{uuid.uuid4()}.json"
        if dry:
            say(f"  would copy : {o.get('title') or f.name}")
        else:
            shutil.copy2(f, target)
        have.add(key)
        copied += 1
    say(f"{'Would copy' if dry else 'Copied'} {copied} card(s) from other account folders.\n")

    # 2) generate cards for transcripts with none
    generated = skipped = 0
    if a.existing_cards_only:
        say("--existing-cards-only: skipping CLI / VS Code sessions.")
    elif not projects.exists():
        say(f"No transcripts found at {projects}.")
    else:
        for t in projects.rglob("*.jsonl"):
            if t.parent.name == "subagents":
                continue
            cli = t.stem
            if cli.lower() in have:
                skipped += 1
                continue
            cwd, created, title = get_meta(t)
            cwd = cwd or ""
            st = t.stat()
            created_ms = to_ms(created, getattr(st, "st_birthtime", st.st_ctime if SYSTEM == "Windows" else st.st_mtime))
            last_ms = int(st.st_mtime * 1000)
            if not title:
                leaf = Path(cwd).name if cwd else "session"
                title = f"{leaf} (recovered)"
            gid = str(uuid.uuid4())
            rec = {
                "sessionId": f"local_{gid}", "cliSessionId": cli, "cwd": cwd, "originCwd": cwd,
                "lastFocusedAt": last_ms, "createdAt": created_ms, "lastActivityAt": last_ms,
                "model": defaults["model"], "effort": defaults["effort"], "isArchived": False,
                "title": title, "titleSource": "auto", "permissionMode": "auto",
                "remoteMcpServersConfig": defaults["remoteMcpServersConfig"],
                "chromePermissionMode": defaults["chromePermissionMode"],
                "completedTurns": 1, "alwaysAllowedReasons": None, "sessionPermissionUpdates": None,
                "classifierSummaryEnabled": True,
            }
            if dry:
                say(f"  would add  : {title}  [{cwd}]")
            else:
                # UTF-8 without BOM
                (dest / f"local_{gid}.json").write_text(json.dumps(rec, separators=(",", ":")), encoding="utf-8")
            have.add(cli.lower())
            generated += 1
        say(f"{'Would generate' if dry else 'Generated'} {generated} new card(s); skipped {skipped} already present.")

    if dry:
        say("\nDry run complete. If this looks right, quit Claude Desktop and re-run with --apply.")
    else:
        total = len(list(dest.glob("local_*.json")))
        say(f"\nDONE. This account's Code tab now has {total} session card(s). Reopen Claude Desktop -> Code tab.")


if __name__ == "__main__":
    main()
