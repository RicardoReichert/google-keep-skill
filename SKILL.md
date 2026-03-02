---
name: google-keep
description: Integration with Google Keep via nodriver (undetectable Chrome). Creates, reads, updates, and deletes notes.
version: 0.3.0
author: Ricardo Reichert
read_when:
  - Create notes in Google Keep
  - List notes from Google Keep
  - Update notes in Google Keep
  - Delete notes from Google Keep
  - Archive notes in Google Keep
  - Manage notes
---

# Google Keep Skill

Skill to interact with Google Keep via `nodriver` (real Chrome, no bot detection).

## Installation

**Prerequisites**

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (package and environment manager)
- Google Chrome installed on the system (e.g., `sudo apt install google-chrome-stable` on Linux)

**Skill Location**

The skill must be in `~/.nanobot/workspace/skills/google-keep-skill/` (or in the Nanobot `workspace/skills`). Nanobot discovers skills that have `SKILL.md` and `_meta.json` in this tree.

**Install Dependencies**

In the skill root, `uv` uses `pyproject.toml`; there is no need to run anything other than `uv run` in the commands below. On the first run, `uv` creates the environment and installs dependencies.

```bash
cd ~/.nanobot/workspace/skills/google-keep-skill
uv run python scripts/keep.py check   # example; on first run uv installs deps
```

(Optional: `make check` does the same if you use the Makefile.)

## Configuration in Nanobot

1. **Nothing in Nanobot's `config.json`** — there is no need to register the skill in a configuration file; it is used via `exec` commands when the user requests actions in Google Keep.

2. **Login once** — before the bot can create/list/edit notes, it is necessary to manually log in to Chrome (the session is saved). The user or the agent must execute:
   ```bash
   cd ~/.nanobot/workspace/skills/google-keep-skill && uv run python scripts/keep.py login
   ```
   Chrome opens; log in to your Google account, close the browser. The session is saved in `config/` and reused in future calls.

3. **How the bot uses the skill** — the agent calls the `exec` tool with the complete command, for example:
   ```bash
   cd ~/.nanobot/workspace/skills/google-keep-skill && uv run python scripts/keep.py list --limit 5
   ```
   Or to create a note: `... keep.py create --title "Title" --content "Text"`. The output is JSON; if the session has expired, the script returns `"success": false` and a message for the user to run `keep.py login` again.

4. **Summary** — Place the skill in `workspace/skills/google-keep-skill`, run `keep.py login` once, then the bot always uses `exec` with the commands described in the **Commands** section below.

## Initial Setup (login — once)

This step is the **manual login** cited in **Configuration in Nanobot** (item 2). Execute once to save the session.

```bash
cd ~/.nanobot/workspace/skills/google-keep-skill
uv run python scripts/keep.py login
```

Chrome will open with the Google Keep page. Log in normally. After detecting the login, the browser closes and the session is saved.

### Verify session

```bash
cd ~/.nanobot/workspace/skills/google-keep-skill && uv run python scripts/keep.py check
```

### Clear session

```bash
cd ~/.nanobot/workspace/skills/google-keep-skill && uv run python scripts/keep.py logout
```

**Only use `logout` if you want to unlink the account.** After this, you will need to log in again.

## Preserving Authentication (for the bot to always use the same session)

The session is stored in two places and is reused in every execution:

| Where | Path | Use |
|-------|------|-----|
| **Chrome Profile** | `config/chrome-profile/` | Cookies, cache, and browser state (persistent). |
| **Cookie Backup** | `config/cookies.json` | Backup of cookies; restored in every headless session. |

**To not lose authentication:**

1. **Do not delete** the `config/` folder or run `keep.py logout` unless you want to log out on purpose.
2. **Backup (optional):** to store the session elsewhere (e.g., before reinstalling the system), copy the entire `config/` folder to a backup. To restore, return `config/` to the same path inside the skill.
3. **One Chrome at a time:** do not open another Chrome using the same `config/chrome-profile` (e.g., two `keep.py` in parallel). The Makefile and the test script remove `SingletonLock` before running to avoid locking the profile.
4. **If Google asks for login again** (security, password change, etc.), run `uv run python scripts/keep.py login` again and log in manually; the new session will be saved in the same `config/`.
5. **Sensitive files:** `config/.gitignore` already contains `.env`, `cookies.json`, and `chrome-profile/` — they do not go to the repository.

The bot (Nanobot) always uses the same session as long as these files exist and are not removed.

## Commands

All executed via `exec`:

```bash
cd ~/.nanobot/workspace/skills/google-keep-skill && uv run python scripts/keep.py <comando>
```

**ATTENTION AGENT:** You MUST strictly use the parameters below. You can also optionally append `--visible` before the command (e.g., `keep.py --visible create ...`) if visual user verification is required.

* `list [--limit N] [--filter "text"]`: Lists notes in `text` (Normal) or `list` (Checklist) format.
* `read --title "T"`: Returns the structured content of the note and its type. **ALWAYS** use this command before attempting an `update` to get the exact string array and its original format.
* `create --title "T" --content "C"`: Creates a text note. To break lines, use literally the dynamic text `\n` sent via the terminal.
* `create-list --title "T" --items "i1, i2, i3"`: Creates a checklist note. Simulates `Enter` between each comma.
* `update --title "T" [--new-title "NT"] [--content "C"]`: **COMPLETELY REPLACES** the old content with the new.
  * **If List:** Zeroes all old items by simulating clicks on "Delete" and regenerates the list starting from scratch iterating over `--content "New item 1\nNew item 2"`.
  * **If Text:** Triggers `Ctrl+A` and deletes the text, then types the new content.
  * **WARNING (Future Features):** You CANNOT ask the command to edit just 1 checkbox of a `list` note yet. Therefore, you NEED to pull the entire list via `read`, rewrite it internally, and inject it entirely into `--content` separated by spaces/newlines when calling the `update`.
* `delete --title "T"`: Move to trash.
* `archive --title "T"`: Archive note.

## Examples for Nanobot

```bash
# 1. Agent creates a multi-line note
cd ~/.nanobot/workspace/skills/google-keep-skill && uv run python scripts/keep.py create --title "Groceries" --content "- Milk\n- Bread"

# 2. Agent creates a native checklist in list format
cd ~/.nanobot/workspace/skills/google-keep-skill && uv run python scripts/keep.py create-list --title "Groceries" --items "Milk, Bread, Coffee"

# 3. Agent scans for items
cd ~/.nanobot/workspace/skills/google-keep-skill && uv run python scripts/keep.py list --filter "meeting"

# 4. Agent updates an entire list completely rewriting it from scratch on the UI
cd ~/.nanobot/workspace/skills/google-keep-skill && uv run python scripts/keep.py update --title "Groceries" --content "Milk\nBread\nCoffee\nChocolate"
```

## JSON Output

```json
{
  "success": true,
  "message": "Note successfully created",
  "data": { "title": "Groceries" }
}
```

## Pipeline / Tests

The complete CRUD test (create → list → read → edit → list → delete → verify) is embedded in the project.

**Requires active session** (execute `make login` or `uv run python scripts/keep.py login` beforehand).

```bash
cd ~/.nanobot/workspace/skills/google-keep-skill
make test
```

Or without Makefile:

```bash
cd ~/.nanobot/workspace/skills/google-keep-skill
rm -f config/chrome-profile/SingletonLock 2>/dev/null
uv run python scripts/test_crud.py
```

Other useful targets: `make login`, `make check`, `make clean`.

## Limitations

- CSS selectors break if Google changes the UI
- Requires manual login once (persistent session); see **Preserving Authentication** above
- If the session expires, instruct the user to run `keep.py login`
