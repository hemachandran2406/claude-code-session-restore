# Claude Code Session Restore (Windows + macOS)

Your Claude Code sessions disappeared from the **Claude Desktop "Code" tab** after you
switched accounts, logged out and back in, or reinstalled. Or sessions you started in the
`claude` CLI or VS Code never showed up in the app at all.

**Your conversations aren't deleted.** The Code tab just can't see them. This tool makes
them visible again, safely and reversibly, on **Windows and macOS**.

![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

> Unofficial community tool, not affiliated with or endorsed by Anthropic.
> It works with app files whose format was determined by observation and may change.
> It is dry-run by default, backs up before writing, and never touches your transcripts.

---

## Quick start

**1. Download** this repo (green **Code** button → **Download ZIP**, then unzip), or:

```bash
git clone https://github.com/hemachandran2406/claude-code-session-restore.git
cd claude-code-session-restore
```

**2. Back up** your transcripts (takes seconds, strongly recommended):

| macOS | Windows (PowerShell) |
|---|---|
| `python3 backup_sessions.py` | `py backup_sessions.py` |

**3. Quit Claude Desktop completely.**
macOS: **Cmd+Q** (closing the window isn't enough).
Windows: system tray → right-click **Claude** → **Quit**.

**4. Dry run.** Nothing is written; it lists what it *would* add:

| macOS | Windows |
|---|---|
| `python3 restore_sessions.py` | `py restore_sessions.py` |

**5. Apply**, then reopen Claude Desktop → **Code** tab:

| macOS | Windows |
|---|---|
| `python3 restore_sessions.py --apply` | `py restore_sessions.py --apply` |

That's it. Re-running is safe; it never creates duplicates.

---

## Why sessions go missing

Claude Code saves every conversation as a transcript file:

| | Transcripts (never account-bound) |
|---|---|
| macOS | `~/.claude/projects/<encoded-folder>/<sessionId>.jsonl` |
| Windows | `%USERPROFILE%\.claude\projects\<encoded-folder>\<sessionId>.jsonl` |

But the Desktop **Code tab doesn't read those directly**. It reads small "card" files, one
per session, stored **per account**:

| | Code-tab cards (per account) |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude-code-sessions/<accountId>/<orgId>/local_*.json` |
| Windows | `%APPDATA%\Claude\claude-code-sessions\<accountId>\<orgId>\local_*.json` |

Each card links to a transcript through its `cliSessionId` field. So:

- sessions created under **another account** have cards in *that* account's folder → invisible now;
- sessions started from the **CLI / VS Code** often have **no card at all** → never listed.

## What the tool does

`restore_sessions.py` (with Claude Desktop closed):

1. **Backs up** the whole card index to `claude-code-sessions_backup_<timestamp>`.
2. **Copies** cards from other account folders into your current account's folder.
3. **Generates** new cards for transcripts that have none, using each session's real
   title from the transcript.

It detects the signed-in account from `~/.claude.json` automatically.

### Options

| Flag | Effect |
|---|---|
| `--apply` | Actually write changes. Without it, the script only shows what it would do. |
| `--existing-cards-only` | Only bring over sessions originally created in the Code tab; skip CLI / VS Code sessions. |
| `--app-base <path>` | Use a different `claude-code-sessions` folder (if your app version stores it elsewhere). |
| `--projects-dir <path>` | Use a different transcripts folder. |
| `--dest-root <path>` | Write cards to a test folder instead of the live one. |
| `--ignore-running` | Don't abort if Claude Desktop seems to be running (not recommended). |
| `--no-backup` | Skip the index backup (testing only). |

## Undo

With Claude Desktop quit, delete the `claude-code-sessions` folder and rename the newest
`claude-code-sessions_backup_<timestamp>` folder to `claude-code-sessions`. Reopen the app.

## Full backup and restore

`backup_sessions.py` saves your transcripts, `settings.json` and the Code-tab index into one
folder. It's useful before reinstalling, when moving to a new machine, or to protect against
Claude Code's automatic cleanup.

```bash
python3 backup_sessions.py                                   # → ~/claude-code-backup_<timestamp>
python3 backup_sessions.py --path /Volumes/MyDrive           # somewhere else
python3 backup_sessions.py --restore ~/claude-code-backup_20261018_101500
```

Restore **merges**: it never deletes, and won't overwrite a newer local file unless you pass
`--force`. After restoring under a different account, run `restore_sessions.py`.

## Keep transcripts longer

Claude Code deletes transcripts older than `cleanupPeriodDays` (**30 days by default**).
To keep them much longer, add this to `~/.claude/settings.json`
(Windows: `%USERPROFILE%\.claude\settings.json`):

```json
{ "cleanupPeriodDays": 3650 }
```

## Troubleshooting

**macOS: `Operation not permitted`.** Terminal isn't allowed into Downloads, Desktop or
Documents. Move the repo folder into your home folder, or enable Terminal under
*System Settings → Privacy & Security → Files and Folders*.

**Windows: `python` opens the Microsoft Store / isn't found.** Install Python from
[python.org](https://www.python.org/downloads/) and use `py`.

**"Claude Desktop is still running".** Quit it fully (see step 3). The app rewrites its
session folder when it exits, so changes made while it's open would be lost.

**"Couldn't read the logged-in account".** Run `claude` in a terminal and sign in once.

**No `claude-code-sessions` folder.** Your app version may store it elsewhere. Look inside
`~/Library/Application Support/Claude/` or `%APPDATA%\Claude\`, then pass the folder with
`--app-base`. Please open an issue with what you find.

**Some old sessions are missing.** If the transcript `.jsonl` file is gone (e.g. auto-cleanup),
the session can only come back from a backup.

## Resume without the app

You can always continue a session from a terminal, in the project's folder:

```bash
claude --resume              # pick from a list (Ctrl+A to show all projects)
claude --resume <sessionId>
claude --continue            # most recent session in this folder
```

## Use it as a Claude skill

The repo includes [`SKILL.md`](SKILL.md). Put this folder in your Claude Code skills directory:

```bash
# macOS / Linux
mkdir -p ~/.claude/skills
cp -R claude-code-session-restore ~/.claude/skills/
```

```powershell
# Windows (PowerShell)
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills" | Out-Null
Copy-Item -Recurse claude-code-session-restore "$env:USERPROFILE\.claude\skills\"
```

Then in the `claude` CLI (in a normal terminal, with Claude Desktop quit) say something like
*"my Claude Code sessions disappeared after I switched accounts."* Claude will back up,
dry-run, show you the list, and apply after you confirm.

## Requirements

- Python 3.8+ (standard library only, no `pip install`)
- macOS or Windows with Claude Desktop and Claude Code

## Tested on

- **macOS**: tested on a real machine (Apple Silicon).
- **Windows**: not yet tested on real hardware. Reports welcome; please [open an issue](https://github.com/hemachandran2406/claude-code-session-restore/issues).

## Credits

Based on [sahol3/claude-code-session-restorer](https://github.com/sahol3/claude-code-session-restorer)
(MIT), which first documented the Code-tab card format and shipped the Windows PowerShell
version. This project ports it to Python for macOS and Windows, adds a dry-run default,
and adds cross-platform backup/restore.

## Contributing

Issues and PRs are welcome, especially reports of new app versions that change folder
locations or the card format. Please include your OS, Claude Desktop version and the
output of the dry run (remove account IDs if you prefer).

## License

[MIT](LICENSE)
