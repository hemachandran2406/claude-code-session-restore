#!/usr/bin/env python3
"""
backup_sessions.py — back up and restore everything that matters for Claude Code
session history, on Windows and macOS:

  * transcripts      ~/.claude/projects
  * settings         ~/.claude/settings.json
  * Code-tab index   claude-code-sessions/  (Claude Desktop)

Transcripts carry no account info, so a backup restores under any account, on
any machine. After restoring under a different account, run restore_sessions.py.

  python3 backup_sessions.py                          # back up to ~/claude-code-backup_<timestamp>
  python3 backup_sessions.py --path /Volumes/USB      # back up somewhere else
  python3 backup_sessions.py --restore ~/claude-code-backup_20261018_101500
  python3 backup_sessions.py --restore <dir> --force  # overwrite newer local files too

Restore merges: it never deletes, and skips files where the local copy is newer
unless --force. Standard library only. Unofficial; not affiliated with Anthropic.
"""
import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from restore_sessions import default_paths, claude_running  # noqa: E402

PROJECTS, _, APP_BASE = default_paths()
SETTINGS = Path.home() / ".claude" / "settings.json"


def merge_copy(src: Path, dst: Path, force: bool):
    n = s = 0
    for f in src.rglob("*"):
        if not f.is_file():
            continue
        t = dst / f.relative_to(src)
        if t.exists() and not force and t.stat().st_mtime >= f.stat().st_mtime:
            s += 1
            continue
        t.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, t)
        n += 1
    return n, s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=str(Path.home()), help="where to create the backup folder")
    ap.add_argument("--restore", metavar="BACKUP_DIR", help="restore from this backup folder")
    ap.add_argument("--force", action="store_true", help="on restore, overwrite even newer local files")
    ap.add_argument("--transcripts-only", action="store_true")
    a = ap.parse_args()

    if a.restore:
        src = Path(a.restore).expanduser()
        if not (src / "projects").exists():
            sys.exit(f"{src} doesn't look like a backup made by this script (no projects/ folder).")
        n, s = merge_copy(src / "projects", PROJECTS, a.force)
        print(f"Transcripts: restored {n}, skipped {s} (local newer).")
        if not a.transcripts_only:
            if (src / "settings.json").exists() and (a.force or not SETTINGS.exists()):
                SETTINGS.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src / "settings.json", SETTINGS)
                print("settings.json restored.")
            if (src / "claude-code-sessions").exists() and APP_BASE:
                if claude_running():
                    print("Claude Desktop is running: skipped the Code-tab index. Quit it and re-run to restore that too.")
                else:
                    n, s = merge_copy(src / "claude-code-sessions", APP_BASE, a.force)
                    print(f"Code-tab index: restored {n}, skipped {s}.")
        print("Done. If you're signed into a different account now, run: python3 restore_sessions.py")
        return

    dest = Path(a.path).expanduser() / f"claude-code-backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    dest.mkdir(parents=True)
    if PROJECTS.exists():
        shutil.copytree(PROJECTS, dest / "projects")
        print(f"Transcripts   -> {dest / 'projects'}")
    else:
        print(f"No transcripts at {PROJECTS}")
    if not a.transcripts_only:
        if SETTINGS.exists():
            shutil.copy2(SETTINGS, dest / "settings.json")
            print(f"settings.json -> {dest / 'settings.json'}")
        if APP_BASE and APP_BASE.exists():
            shutil.copytree(APP_BASE, dest / "claude-code-sessions")
            print(f"Code-tab index-> {dest / 'claude-code-sessions'}")
    print(f"\nBackup complete: {dest}")


if __name__ == "__main__":
    main()
