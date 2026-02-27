<div align="center">
  <h1>📝 Google Keep Skill</h1>
  <h3>Headless Google Keep Automation via Undetected Chrome</h3>
  <br/>
  <p>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/nodriver-Chrome_Automation-orange.svg" alt="nodriver">
    <img src="https://img.shields.io/badge/Google_Keep-Integration-4285F4.svg?logo=google&logoColor=white" alt="Google Keep">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <img src="https://img.shields.io/badge/version-0.3.0-blueviolet" alt="Version">
  </p>
</div>

🗒️ **Google Keep Skill** is a **CLI automation tool** that interacts with Google Keep through an undetected headless Chrome browser powered by `nodriver`.

⚡️ Create, read, update, delete, and archive notes — all from the command line with **structured JSON output**.

🔒 Bot-proof: uses a real Chrome instance with persistent session, bypassing Google's bot detection entirely.

## 📢 News

- **2026-02-27** 🎉 Released **v0.3.0** — refactored note and list creation with precise DOM selectors, multi-line content support, and robust CDP click interactions.
- **2026-02-27** 🔧 Fixed headless viewport sizing to prevent lazy-loading issues.
- **2026-02-27** ✨ Improved note extraction to handle whitespace-only ghost notes.

## Key Features

🗒️ **Full CRUD Operations**: Create, read, update, delete, and archive notes — text or list type.

📋 **List Support**: Create checklist-style notes with individual items, each properly injected as separate list entries.

🔐 **Persistent Session**: Login once manually; the session is saved and reused across all headless executions.

📄 **Structured JSON Output**: Every command returns clean, parseable JSON for easy integration with bots and automation pipelines.

🖥️ **Headless by Default**: Runs without a visible browser window — perfect for server-side automation and CI/CD.

## 🏗️ Architecture

The skill follows a **CLI → Browser Automation → DOM Interaction** pattern, isolating authentication from note operations.

<table align="center" width="100%">
  <tr>
    <th width="30%">Layer</th>
    <th width="30%">Technology</th>
    <th width="40%">Responsibility</th>
  </tr>
  <tr>
    <td><b>🖥️ CLI Interface</b></td>
    <td>argparse / Python</td>
    <td>Parses commands and arguments, dispatches to async handlers.</td>
  </tr>
  <tr>
    <td><b>🌐 Browser Engine</b></td>
    <td>nodriver (undetected Chrome)</td>
    <td>Launches headless Chrome, manages tabs, executes CDP commands.</td>
  </tr>
  <tr>
    <td><b>🔐 Auth Layer</b></td>
    <td>CDP Cookies / Chrome Profile</td>
    <td>Persists Google session via profile directory and cookie backup.</td>
  </tr>
  <tr>
    <td><b>🎯 DOM Interaction</b></td>
    <td>JavaScript / CDP Input</td>
    <td>Finds elements by aria-label and text content, types via execCommand and CDP key events.</td>
  </tr>
  <tr>
    <td><b>📤 Output</b></td>
    <td>JSON (stdout)</td>
    <td>Returns structured success/error responses for automation consumers.</td>
  </tr>
</table>

## ✨ Commands

All commands are executed via the CLI:

```bash
cd ~/.nanobot/workspace/skills/google-keep-skill && uv run python scripts/keep.py <command>
```

<table align="center" width="100%">
  <tr>
    <th width="35%">Command</th>
    <th width="65%">Description</th>
  </tr>
  <tr>
    <td><code>login</code></td>
    <td>Opens Chrome for manual Google login (one-time setup).</td>
  </tr>
  <tr>
    <td><code>logout</code></td>
    <td>Clears saved session data.</td>
  </tr>
  <tr>
    <td><code>check</code></td>
    <td>Verifies if the saved session is still active.</td>
  </tr>
  <tr>
    <td><code>list [--limit N] [--filter "text"]</code></td>
    <td>Lists all notes with optional limit and text filter.</td>
  </tr>
  <tr>
    <td><code>create --title "T" --content "C"</code></td>
    <td>Creates a plain text note with multi-line support (<code>\n</code>).</td>
  </tr>
  <tr>
    <td><code>create-list --title "T" --items "a, b, c"</code></td>
    <td>Creates a checklist note with comma-separated items.</td>
  </tr>
  <tr>
    <td><code>read --title "T"</code></td>
    <td>Reads a specific note by its exact title.</td>
  </tr>
  <tr>
    <td><code>update --title "T" [--new-title "NT"] [--content "C"]</code></td>
    <td>Updates an existing note's title and/or content.</td>
  </tr>
  <tr>
    <td><code>delete --title "T"</code></td>
    <td>Moves a note to the trash.</td>
  </tr>
  <tr>
    <td><code>archive --title "T"</code></td>
    <td>Archives a note.</td>
  </tr>
</table>

## 📦 Install

```bash
git clone git@github.com:RicardoReichert/google-keep-skill.git
cd google-keep-skill

# First run installs dependencies automatically via uv
uv run python scripts/keep.py check
```

### Prerequisites

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** — fast Python package manager
- **Google Chrome** installed (`sudo apt install google-chrome-stable` on Ubuntu/Debian)

### Initial Login (one-time)

```bash
uv run python scripts/keep.py login
```

Chrome opens → login to your Google account → close the browser. Session is saved persistently.

## 🔧 Usage Examples

```bash
# Create a text note with multi-line content
uv run python scripts/keep.py create --title "Meeting Notes" --content "Discuss roadmap\nReview budget\nAssign tasks"

# Create a checklist
uv run python scripts/keep.py create-list --title "Groceries" --items "Milk, Bread, Coffee, Eggs"

# List all notes
uv run python scripts/keep.py list

# List with filter
uv run python scripts/keep.py list --filter "meeting" --limit 5

# Read a specific note
uv run python scripts/keep.py read --title "Meeting Notes"

# Update a note
uv run python scripts/keep.py update --title "Meeting Notes" --new-title "Sprint Planning" --content "Updated content"

# Delete a note
uv run python scripts/keep.py delete --title "Old Note"

# Archive a note
uv run python scripts/keep.py archive --title "Completed Task"
```

## 📤 JSON Output

Every command returns structured JSON:

```json
{
  "success": true,
  "message": "Nota criada com sucesso",
  "data": { "title": "Groceries" }
}
```

```json
{
  "success": true,
  "message": "8 nota(s) encontrada(s)",
  "data": {
    "notes": [
      {
        "id": "1",
        "title": "Meeting Notes",
        "content": ["Discuss roadmap", "Review budget", "Assign tasks"],
        "type": "text"
      },
      {
        "id": "2",
        "title": "Groceries",
        "content": ["Milk", "Bread", "Coffee"],
        "type": "list"
      }
    ]
  }
}
```

## 🔐 Session Persistence

<table align="center" width="100%">
  <tr>
    <th width="25%">Storage</th>
    <th width="40%">Path</th>
    <th width="35%">Purpose</th>
  </tr>
  <tr>
    <td><b>Chrome Profile</b></td>
    <td><code>config/chrome-profile/</code></td>
    <td>Full browser state (cookies, cache, localStorage).</td>
  </tr>
  <tr>
    <td><b>Cookie Backup</b></td>
    <td><code>config/cookies.json</code></td>
    <td>CDP cookie backup restored on each headless session.</td>
  </tr>
</table>

> [!IMPORTANT]
> These files are excluded from git via `.gitignore`. Never commit session data.

## 🧪 Testing

```bash
# Run the minimal test suite (requires active session)
uv run python scripts/test_list.py
```

Or via Makefile:

```bash
make test
make check
make login
```

## ⚠️ Limitations

- CSS selectors may break if Google updates the Keep UI
- Requires one-time manual login (session is persistent afterward)
- Only one Chrome instance can use the profile at a time
- If Google requires re-authentication, run `keep.py login` again

## 📁 Project Structure

```
google-keep-skill/
├── .gitignore
├── Makefile
├── SKILL.md              # Nanobot skill documentation
├── _meta.json             # Skill metadata
├── pyproject.toml         # Python dependencies (nodriver)
├── uv.lock                # Locked dependencies
├── config/
│   ├── .gitignore         # Excludes sensitive session files
│   ├── chrome-profile/    # Persistent Chrome profile (gitignored)
│   └── cookies.json       # Cookie backup (gitignored)
└── scripts/
    ├── __init__.py
    ├── auth.py            # Session management (login, logout, check)
    ├── keep.py            # Main CLI — all CRUD operations
    └── test_list.py       # Minimal test suite
```

## 👤 Author

**Ricardo Reichert**

## 📜 License

This project is released under the [MIT License](LICENSE).
