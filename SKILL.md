---
name: claude-code-session-restore
description: Restore Claude Code sessions missing from the Claude Desktop "Code" tab on Windows or macOS — after switching or re-logging into a Claude account, reinstalling, or for sessions started in the claude CLI or VS Code that never appeared in the app. Also backs up and restores session transcripts. Use when the user says their Claude Code sessions/chats disappeared, are missing from the Code tab, or don't show up after changing accounts.
---

# Claude Code session restore

Claude Code transcripts live on disk and are never tied to an account. The Desktop
Code tab only lists small per-account "card" files, so sessions from another account
(or from the CLI / VS Code) don't appear. `restore_sessions.py` rebuilds those cards
for the account that is currently signed in. Nothing is deleted.

| | Transcripts | Code-tab cards |
|---|---|---|
| macOS | `~/.claude/projects/` | `~/Library/Application Support/Claude/claude-code-sessions/<account>/<org>/` |
| Windows | `%USERPROFILE%\.claude\projects\` | `%APPDATA%\Claude\claude-code-sessions\<account>\<org>\` |

## Important: where to run this

The restore must run while **Claude Desktop is fully quit**, because the app rewrites
its session folder on exit. So run it from the `claude` CLI in a normal terminal,
not from inside the Desktop app's Code tab. If you are running inside Claude Desktop,
stop and give the user the commands to run in a terminal instead.

## Workflow

Follow these steps in order. Ask the user before every step that writes anything.

1. **Confirm the situation.** Check that transcripts exist:
   - macOS: `ls ~/.claude/projects`
   - Windows (PowerShell): `Get-ChildItem $env:USERPROFILE\.claude\projects`
   If the folder is empty or missing, the restore can't help; say so.

2. **Back up first** (ask before running):
   `python3 backup_sessions.py` (on Windows, `python` or `py` instead of `python3`).

3. **Make sure Claude Desktop is quit.** macOS: Cmd+Q. Windows: system tray → right-click Claude → Quit.
   The script refuses to run if it detects the app.

4. **Dry run** and show the user the output:
   `python3 restore_sessions.py`
   It prints the detected account, the target folder, and every session it would add.
   If the user only wants sessions originally created in the Code tab (not CLI / VS Code
   ones), add `--existing-cards-only`.

5. **Apply** only after the user confirms the list:
   `python3 restore_sessions.py --apply`

6. Tell the user to reopen Claude Desktop → Code tab.

## Troubleshooting

- **macOS `Operation not permitted` when reading the script**: Terminal lacks access to
  Downloads/Desktop/Documents. Move the files to the home folder, or enable Terminal in
  System Settings → Privacy & Security → Files and Folders.
- **"Couldn't read the logged-in account"**: run `claude` once and sign in.
- **`claude-code-sessions` folder missing**: the app version may store cards elsewhere.
  Do not guess. Ask the user to list `Application Support/Claude/` (macOS) or
  `%APPDATA%\Claude\` (Windows) and pass the right folder with `--app-base`.
- **Sessions older than ~30 days are gone**: Claude Code deletes old transcripts
  (`cleanupPeriodDays`, default 30). Suggest adding `"cleanupPeriodDays": 3650` to
  `~/.claude/settings.json`. Lost transcripts can only come back from a backup.

## Undo

Each `--apply` writes a `claude-code-sessions_backup_<timestamp>` folder next to the
index. With Claude Desktop quit, delete `claude-code-sessions` and rename the backup
folder back to `claude-code-sessions`.

## Without the app

Sessions can always be resumed from a terminal in the project folder:
`claude --resume` (picker; Ctrl+A shows all projects), `claude --resume <id>`, or `claude --continue`.
