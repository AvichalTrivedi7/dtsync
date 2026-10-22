# Evening run guide (Windows, HP Victus)

This folder is the complete handoff from the claude.ai chat:
- CONTEXT.md: everything decided in the chat (venue, design, pilot results, paper status, rules)
- CLAUDE.md: Claude Code's rules and its task list for tonight (loaded automatically)
- paper/draft.md: snapshot of the paper (the master copy stays in the chat's doc)
- the code: dtsync.py, run_all.py, analyze.py and the figure scripts
- .claude/settings.json: pre-approved permissions so Claude Code does not stall at night

## One-time setup (about 15 minutes)
1. Install Python 3.12 from python.org (tick "Add python.exe to PATH") and Git for Windows.
2. Install the GitHub CLI: `winget install --id GitHub.cli`. Open a new PowerShell window and run
   `gh auth login` (GitHub.com, HTTPS, log in with a web browser).
3. Unzip this folder to `C:\research\dtsync` (not inside OneDrive).
4. In PowerShell:
   ```
   cd C:\research\dtsync
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
5. Install Claude Code: `irm https://claude.ai/install.ps1 | iex`, open a new window, check `claude --version`.

## Each time you run it
1. Plug in the charger. Settings > System > Power: sleep "Never" when plugged in, Best performance.
   Keep the lid open.
2. Window 1 (experiments, 1.5 to 2 hours):
   ```
   cd C:\research\dtsync
   .venv\Scripts\python.exe run_all.py
   ```
   Wait until it prints `smoke: OK`, then leave it running.
3. Window 2 (Claude Code):
   ```
   cd C:\research\dtsync
   git init
   git add -A
   git commit -m "Handoff from chat, 22 Oct"
   claude
   ```
   Log in if asked, then paste the prompt below. Watch the first 10 minutes: if Claude Code asks for a
   permission anyway, choose the "don't ask again" option.
4. In the morning, upload `upload_bundle.zip` in the chat.

## Prompt to paste into Claude Code
```
Read CONTEXT.md and CLAUDE.md completely before doing anything. You are the engineering assistant for
this paper; the prose belongs to the claude.ai chat. The experiments were started by Avi in another
window with run_all.py: do not start, stop or edit them. Work through tasks A to H in CLAUDE.md in order
and commit after each one. Do A and B while the experiments run; start C only when logs/run_all.log shows
every job finished, using sleep 540 between checks. Nobody will answer questions tonight: if something
blocks you, write it in RUNLOG.md and continue with the next task. Never invent numbers or references.
```

## If something goes wrong
- `smoke: FAILED`: upload `logs\smoke.log` in the chat.
- Laptop restarted: run the same command in Window 1 again; finished patients are skipped.
- Too hot or slow: Ctrl+C, then `$env:DTSYNC_WORKERS=6; .venv\Scripts\python.exe run_all.py`.
- Claude Code paused at a usage limit: the experiments still finish. Later, type `continue` in Claude Code.
