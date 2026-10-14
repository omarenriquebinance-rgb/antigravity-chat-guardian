# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-10-14

### Added
- **1-Click Restart & Restore Coordinator (`REINICIAR_Y_RESTAURAR_ANTIGRAVITY.bat`):** Standalone executable that gracefully terminates `Antigravity IDE.exe`, releases exclusive SQLite database locks, atomic-injects conversations, and automatically reopens Antigravity IDE decoupled.
- **Project Folder-Based Chat Naming:** Automatically names conversation titles after their project folder (e.g., `Banco-Estado-Chile`, `Trabajo de raquel`, `ARREGLO-ANTIGAVITY`, etc.) for immediate visual recognition in the sidebar.
- **Multi-Workspace Storage Propagation:** Automatically scans and updates all 25 `workspaceStorage/<hash>/state.vscdb` databases, ensuring chats appear both globally and when opening individual project folders.
- **Unified Workspace Binding Mode:** Option to bind all conversations to the current active workspace, making all 105 chats immediately visible in the active window.
- **24/7 Autonomous Background Auto-Restoration:** Enhanced `SmartAntigravityWatcher` automatically intercepts IDE close events, waits for lock clearance, and auto-immunizes `state.vscdb` so chats are already restored on next launch.
- **Windows Startup Integration:** Added `Antigravity_Chat_Guardian_Startup.vbs` to Windows Startup (`shell:startup`) for permanent background protection upon system login.
- **CLI Options:** Added `--target` and `--by-project` flags to `cli.py restore-all`.

### Fixed
- **Windows Charmap / cp1252 UnicodeEncodeError:** Replaced console emojis with clean ASCII indicators (`[OPEN]`, `[CLOSED]`, `[SAVE]`, `[SLEEP]`) in `watcher.py` preventing background crashes.
- **Headless `pythonw.exe` Stdout Crash:** Redirected `sys.stdout` and `sys.stderr` to `os.devnull` when running detached without an attached console.

## [1.0.0] - 2026-10-11


### Added
- **Core Recovery Engine:** Protobuf Wire Format parser & writer for `antigravityUnifiedStateSync.trajectorySummaries` and JSON encoder for `chat.ChatSessionStore.index`.
- **Bulk Restorer (`cli.py restore-all`):** Automated recovery and project mapping for 100+ conversations into Antigravity IDE sidebar.
- **Smart Conditional Watcher (`src/backup/watcher.py`):** Ctypes-based Windows process monitor with 0% CPU idle consumption and real-time capture when Antigravity IDE is open.
- **Auto-Immunization:** Automatic repair of `state.vscdb` on IDE termination to prevent session wipes.
- **System Doctor (`cli.py doctor`):** Interactive health check of physical storage, brain logs, and IDE state.
- **Multi-format Exporter (`cli.py export`):** Export full conversation transcripts to Markdown and JSON.
- **Local Web Viewer & Control Hub:** Modern dark-mode SPA at `http://127.0.0.1:7890`.
- **1-Click Windows Launchers:** `setup.bat`, `restaurar_historial_antigravity.bat`, `iniciar_vigilante_silencioso.vbs`, `run_hub.bat`.
