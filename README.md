# 💡 IdeaVault

A clean, local-first idea notebook for Windows 10/11, built with Python + CustomTkinter + SQLite.
Your notes never leave your machine.

## ⬇ Download
**[Download IdeaVault.exe (latest release)](https://github.com/swarnim-das/ideavault/releases/latest)**: a single file for Windows 10/11, no Python or installer needed.

## Features
- **Three-pane dashboard**: category sidebar · searchable idea list · editor
- **Categories**: All Ideas, General, Projects, Writing, Code, To-Do (with live counts)
- **Live search** across title, content and tags. Prefix a word with `#` to search tags only (`#python api`)
- **Auto-save**: changes are written ~0.6 s after you stop typing (and on switching ideas or closing)
- **Markdown-friendly** monospaced editor with undo/redo (Ctrl+Z / Ctrl+Y)
- **Export** everything to `.json` or `.md`, **import** a JSON export, or **back up** the raw SQLite database
- Dark mode by default, light mode toggle; window size and theme are remembered
- Empty "new ideas" you never typed into are discarded automatically

## Where your data lives
```
%LOCALAPPDATA%\IdeaVault\ideas.db        ← your ideas (SQLite)
%LOCALAPPDATA%\IdeaVault\settings.json   ← theme, window size, last export folder
%LOCALAPPDATA%\IdeaVault\ideavault.log   ← error log
```
Click **Open data folder** in the sidebar to jump there.
For a portable copy (e.g. on a USB stick) set `IDEAVAULT_DATA_DIR` to any folder before launching.

## Just want to use it?
Download `IdeaVault.exe` from the [Releases page](https://github.com/swarnim-das/ideavault/releases/latest). It's a single file that needs no Python or installation, so you can copy it to any Windows 10/11 PC.
Windows may show **"Windows protected your PC"** the first time, because the exe isn't code-signed. Click **More info → Run anyway**.
Each person's ideas are stored on their own PC (see below), never inside the exe.

## Install & run from source (Windows)
Requires **Python 3.9+** from python.org (tick *"Add python.exe to PATH"* during install).
`sqlite3` and `tkinter` ship with Python. Don't `pip install` them.

**Easiest:** double-click `setup.bat` once, then `run.bat` from then on.

**Manual (PowerShell or Command Prompt), from this folder:**
```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```
> If PowerShell blocks `activate`, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**Run the tests:**
```powershell
python -m unittest discover -s tests -v
```

**Rebuild the .exe after changing code:** double-click `build_exe.bat`, or:
```powershell
pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name IdeaVault --icon assets\ideavault.ico --add-data "assets\ideavault.ico;assets" --version-file version_info.txt --collect-data customtkinter main.py
```
Output: `dist\IdeaVault.exe`. Attach it to a new GitHub Release to share it.

## Keyboard shortcuts
| Shortcut | Action |
|---|---|
| Ctrl+N | New idea (in the current category) |
| Ctrl+F | Focus search · Esc clears it |
| Ctrl+S | Save now (auto-save is always on) |
| Ctrl+E | Export JSON |
| Ctrl+Shift+E | Export Markdown |
| Ctrl+Shift+D | Delete current idea |
| Alt+↑ / Alt+↓ | Previous / next idea in the list |
| Enter (in title) | Jump to the body |

## Project structure
```
main.py                  entry point
ideavault/
  config.py              constants, data-folder paths, settings store
  database.py            SQLite schema, migrations, CRUD, search, backup
  exporter.py            JSON / Markdown export, JSON import
  utils.py               date formatting, open-in-Explorer
  app.py                 main window and controller (auto-save, shortcuts, dialogs)
  ui/
    theme.py             colours and fonts (light, dark)
    sidebar.py           categories, actions, theme switch
    idea_list.py         search box and pooled idea cards
    editor.py            title, category, tags, body, save status
assets/ideavault.ico     app icon
tests/test_core.py       repository and export tests
setup.bat · run.bat · build_exe.bat · version_info.txt
```

## Data model
```sql
CREATE TABLE ideas (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  title       TEXT NOT NULL DEFAULT '',
  content     TEXT NOT NULL DEFAULT '',   -- Markdown-friendly
  category    TEXT NOT NULL DEFAULT 'General',
  tags        TEXT NOT NULL DEFAULT '',   -- comma-separated, normalised
  created_at  TEXT NOT NULL,              -- ISO-8601 UTC
  updated_at  TEXT NOT NULL
);
```
Schema version is tracked with `PRAGMA user_version`, so future columns can be added as migrations in `database.py`.
